'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

import { ApiError } from '@/lib/auth/api'
import { useAuthStore } from '@/lib/auth/store'
import { listReviews, updateReview } from '@/lib/reviews/api'
import type { ReviewItem, ReviewUpdatePayload } from '@/lib/reviews/types'

import { ScoreDetail } from '../dashboard/score-detail'
import styles from './review-client.module.css'

interface Props {
  initialDateFrom?: string
  initialDateTo?: string
  embedded?: boolean
}

type HitFilter = 'all' | 'hit' | 'miss' | 'pending'

function daysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

function toNumber(v: string | number | null | undefined): number {
  if (v === null || v === undefined) return 0
  const n = typeof v === 'string' ? Number(v) : v
  return Number.isFinite(n) ? n : 0
}

function formatPct(v: number): string {
  return `${(v * 100).toFixed(2)}%`
}

function formatBetType(t: ReviewItem['bet_type']): string {
  if (t === 'draw') return '平'
  if (t === 'handicap_draw') return '让平'
  return '-'
}

function formatOdds(v: ReviewItem['bet_odds']): string {
  if (v === null || v === undefined) return '-'
  const n = typeof v === 'string' ? Number(v) : v
  return Number.isFinite(n) && n > 0 ? n.toFixed(2) : '-'
}

function formatResult(v: string | null): string {
  if (v === 'home_win') return '主胜'
  if (v === 'away_win') return '客胜'
  if (v === 'win') return '胜'
  if (v === 'draw') return '平'
  if (v === 'lose') return '负'
  return '-'
}

function suggestedBasis(it: ReviewItem): string {
  if (it.bet_type === 'draw') return `全场赛果 ${formatResult(it.result)}`
  if (it.bet_type === 'handicap_draw') return `让球赛果 ${formatResult(it.handicap_result)}`
  return '无推荐项'
}

function MatchLink({ item }: { item: ReviewItem }) {
  const label = `${item.home_team} vs ${item.away_team}`
  if (!item.sporttery_url) return <>{label}</>
  return (
    <a
      className={styles.matchLink}
      href={item.sporttery_url}
      target="_blank"
      rel="noreferrer"
      title="打开竞彩网固定奖金页面"
    >
      {label}
    </a>
  )
}

function HitBadge({ value }: { value: boolean | null }) {
  if (value === null) return <span className={styles.hitNull}>待复盘</span>
  return value ? (
    <span className={styles.hitYes}>命中</span>
  ) : (
    <span className={styles.hitNo}>未中</span>
  )
}

export function ReviewClient({ initialDateFrom, initialDateTo, embedded = false }: Props) {
  const user = useAuthStore((s) => s.user)
  const canEdit = user?.role === 'admin'

  const defaultFrom = useMemo(() => initialDateFrom ?? daysAgo(14), [initialDateFrom])
  const defaultTo = useMemo(() => initialDateTo ?? daysAgo(0), [initialDateTo])

  const [dateFrom, setDateFrom] = useState(defaultFrom)
  const [dateTo, setDateTo] = useState(defaultTo)
  const [onlyRecommended, setOnlyRecommended] = useState(false)
  const [hitFilter, setHitFilter] = useState<HitFilter>('all')
  const [leagueFilter, setLeagueFilter] = useState<string>('all')

  const [items, setItems] = useState<ReviewItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [openedScoreId, setOpenedScoreId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await listReviews({
        date_from: dateFrom,
        date_to: dateTo,
        only_recommended: onlyRecommended
      })
      setItems(res.items)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [dateFrom, dateTo, onlyRecommended])

  useEffect(() => {
    void load()
  }, [load])

  const leagues = useMemo(() => {
    const set = new Set<string>()
    items.forEach((it) => {
      if (it.league_name) set.add(it.league_name)
    })
    return Array.from(set).sort()
  }, [items])

  const filteredItems = useMemo(() => {
    return items.filter((it) => {
      if (leagueFilter !== 'all' && it.league_name !== leagueFilter) return false
      if (hitFilter === 'hit' && it.actual_hit !== true) return false
      if (hitFilter === 'miss' && it.actual_hit !== false) return false
      if (hitFilter === 'pending' && it.actual_hit !== null) return false
      return true
    })
  }, [items, leagueFilter, hitFilter])

  const summary = useMemo(() => {
    let total = 0
    let hits = 0
    let stake = 0
    let pnl = 0
    filteredItems.forEach((it) => {
      if (it.actual_hit === null) return
      total += 1
      if (it.actual_hit) hits += 1
      stake += toNumber(it.bet_amount)
      pnl += it.actual_hit ? toNumber(it.bet_amount) : -toNumber(it.bet_amount)
    })
    return {
      total,
      hits,
      hitRate: total > 0 ? hits / total : 0,
      stake,
      pnl
    }
  }, [filteredItems])

  const applyLocalUpdate = (updated: ReviewItem) => {
    setItems((prev) => prev.map((it) => (it.score_id === updated.score_id ? updated : it)))
  }

  const patchRow = async (scoreId: number, patch: ReviewUpdatePayload) => {
    if (!canEdit) return
    const current = items.find((it) => it.score_id === scoreId)
    const payload: ReviewUpdatePayload = {
      ...patch,
      expected_updated_at: patch.expected_updated_at ?? current?.updated_at ?? null
    }
    setSavingId(scoreId)
    try {
      const res = await updateReview(scoreId, payload)
      applyLocalUpdate(res)
      setError(null)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError('该行已被其他管理员更新，已自动刷新最新数据，请重新提交。')
        void load()
      } else {
        setError((e as Error).message)
      }
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className={styles.container}>
      {!embedded && (
        <div className={styles.header}>
          <div>
            <div className={styles.title}>复盘</div>
            <div className={styles.subtitle}>
              已结束场次的实盘命中与资金曲线记录{!canEdit && ' · 只读'}
            </div>
          </div>
        </div>
      )}

      <div className={styles.filters}>
        <label className={styles.checkbox}>
          起
          <input
            type="date"
            className={styles.input}
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            aria-label="复盘-起始日期"
          />
        </label>
        <label className={styles.checkbox}>
          止
          <input
            type="date"
            className={styles.input}
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            aria-label="复盘-结束日期"
          />
        </label>
        <label className={styles.checkbox}>
          <input
            type="checkbox"
            checked={onlyRecommended}
            onChange={(e) => setOnlyRecommended(e.target.checked)}
            aria-label="仅推荐"
          />
          仅推荐
        </label>
        <select
          className={styles.select}
          value={leagueFilter}
          onChange={(e) => setLeagueFilter(e.target.value)}
          aria-label="联赛过滤"
        >
          <option value="all">全部联赛</option>
          {leagues.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          value={hitFilter}
          onChange={(e) => setHitFilter(e.target.value as HitFilter)}
          aria-label="命中过滤"
        >
          <option value="all">全部状态</option>
          <option value="hit">命中</option>
          <option value="miss">未中</option>
          <option value="pending">待复盘</option>
        </select>
        <button className={styles.button} onClick={() => void load()} disabled={loading}>
          刷新
        </button>
      </div>

      <div className={styles.summary} aria-label="复盘汇总">
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>已复盘</span>
          <span className={styles.summaryValue}>{summary.total}</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>命中率</span>
          <span className={styles.summaryValue}>{formatPct(summary.hitRate)}</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>投注金额</span>
          <span className={styles.summaryValue}>¥{summary.stake.toFixed(2)}</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>净盈亏</span>
          <span className={styles.summaryValue}>¥{summary.pnl.toFixed(2)}</span>
        </div>
      </div>

      {error && <div className={styles.errorBanner}>{error}</div>}

      {loading ? (
        <div className={styles.empty}>加载中…</div>
      ) : filteredItems.length === 0 ? (
        <div className={styles.empty}>暂无可复盘的场次</div>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>日期</th>
              <th>联赛</th>
              <th>模型</th>
              <th>比赛</th>
              <th>比分</th>
              <th>总分</th>
              <th>推荐项</th>
              <th>建议命中</th>
              <th>命中</th>
              <th>投注</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((it) => {
              const isSaving = savingId === it.score_id
              return (
                <tr key={it.score_id} aria-label={`row-${it.score_id}`}>
                  <td>
                    <div className={styles.dateCell}>
                      <span>{it.match_date.slice(0, 10)}</span>
                      <small>{it.match_round ?? '-'}</small>
                    </div>
                  </td>
                  <td>{it.league_name ?? '-'}</td>
                  <td>
                    <div className={styles.modelCell}>
                      <span>{it.model_name ?? `模型 ${it.model_config_id}`}</span>
                      <small>ID {it.model_config_id}</small>
                    </div>
                  </td>
                  <td>
                    <MatchLink item={it} />
                  </td>
                  <td>
                    {it.home_score != null && it.away_score != null
                      ? `${it.home_score}-${it.away_score}`
                      : '-'}
                  </td>
                  <td>
                    <button
                      type="button"
                      className={styles.scoreButton}
                      onClick={() => setOpenedScoreId(it.score_id)}
                      aria-label={`score-detail-${it.score_id}`}
                    >
                      {it.total_score}
                    </button>
                  </td>
                  <td>
                    <div className={styles.pickCell}>
                      <span className={it.is_recommended ? styles.pickStrong : styles.pickMuted}>
                        {formatBetType(it.bet_type)}
                      </span>
                      <small>赔率 {formatOdds(it.bet_odds)}</small>
                    </div>
                  </td>
                  <td>
                    <div className={styles.hitCell}>
                      <HitBadge value={it.suggested_actual_hit} />
                      <small>{suggestedBasis(it)}</small>
                    </div>
                  </td>
                  <td>
                    <select
                      className={styles.tableInput}
                      value={it.actual_hit === null ? '' : it.actual_hit ? 'hit' : 'miss'}
                      onChange={(e) => {
                        const v = e.target.value
                        void patchRow(it.score_id, {
                          actual_hit: v === '' ? null : v === 'hit'
                        })
                      }}
                      disabled={!canEdit || isSaving}
                      aria-label={`actual-hit-${it.score_id}`}
                    >
                      <option value="">待定</option>
                      <option value="hit">命中</option>
                      <option value="miss">未中</option>
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      min={0}
                      step={0.01}
                      className={styles.tableInput}
                      defaultValue={it.bet_amount ?? ''}
                      disabled={!canEdit || isSaving}
                      onBlur={(e) => {
                        const raw = e.target.value
                        const next = raw === '' ? null : Number(raw)
                        if (next !== null && !Number.isFinite(next)) return
                        if (String(it.bet_amount ?? '') === raw) return
                        void patchRow(it.score_id, { bet_amount: next })
                      }}
                      aria-label={`bet-amount-${it.score_id}`}
                    />
                  </td>
                  <td>
                    <input
                      className={styles.tableInput}
                      defaultValue={it.notes ?? ''}
                      disabled={!canEdit || isSaving}
                      onBlur={(e) => {
                        const v = e.target.value
                        if ((it.notes ?? '') === v) return
                        void patchRow(it.score_id, { notes: v === '' ? null : v })
                      }}
                      aria-label={`notes-${it.score_id}`}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      {openedScoreId != null && (
        <ScoreDetail
          scoreId={openedScoreId}
          onClose={() => setOpenedScoreId(null)}
          onUpdated={() => {
            void load()
          }}
        />
      )}
    </div>
  )
}
