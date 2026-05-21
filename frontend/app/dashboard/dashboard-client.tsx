'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { CalendarDays, Calculator, RefreshCw } from 'lucide-react'

import { ReviewClient } from '@/app/review/review-client'
import { listModelConfigs } from '@/lib/model-config/api'
import type { ModelConfig } from '@/lib/model-config/types'
import { computeScores, computeUpcomingScores, getScoresByDate, getTodayScores } from '@/lib/scores/api'
import type { Score } from '@/lib/scores/types'

import styles from './dashboard-client.module.css'
import { ScoreDetail } from './score-detail'

type DashTab = 'upcoming' | 'finished'
type ScoreScope = 'upcoming' | 'date'
type ComboTicket = {
  title: string
  tone: string
  legs: Score[]
  avgScore: number
  kellyText: string
  comboOdds: number | null
}

function toDateInput(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function formatKelly(v: Score['kelly_pct']): string {
  if (v === null || v === undefined) return '-'
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (!Number.isFinite(n)) return '-'
  return `${(n * 100).toFixed(2)}%`
}

function kellyValue(v: Score['kelly_pct']): number {
  if (v === null || v === undefined) return 0
  const n = typeof v === 'string' ? parseFloat(v) : v
  return Number.isFinite(n) ? n : 0
}

function oddsValue(v: Score['bet_odds']): number | null {
  if (v === null || v === undefined) return null
  const n = typeof v === 'string' ? parseFloat(v) : v
  return Number.isFinite(n) && n > 0 ? n : null
}

function formatOdds(v: Score['bet_odds']): string {
  const n = oddsValue(v)
  if (n === null) return '-'
  return n.toFixed(2)
}

function formatBetType(t: Score['bet_type']): string {
  if (t === 'draw') return '平'
  if (t === 'handicap_draw') return '让平'
  return '-'
}

function MatchLink({ score, compact = false }: { score: Score; compact?: boolean }) {
  const label = `${score.home_team ?? '-'} vs ${score.away_team ?? '-'}`
  if (!score.sporttery_url) {
    return compact ? <strong>{label}</strong> : <span>{label}</span>
  }
  return (
    <a
      className={compact ? styles.comboMatchLink : styles.matchLink}
      href={score.sporttery_url}
      target="_blank"
      rel="noreferrer"
      title="打开竞彩网固定奖金页面"
      onClick={(e) => e.stopPropagation()}
    >
      {label}
    </a>
  )
}

function formatScoreKind(score: Score): string {
  return score.score_mode === 'rule' ? '规则分' : '6维分'
}

function scoreTone(score: number): string {
  if (score >= 100) return styles.scoreElite
  if (score >= 80) return styles.scoreStrong
  if (score >= 60) return styles.scoreWatch
  return styles.scoreMuted
}

function formatTime(value: string | null): string {
  if (!value) return '--:--'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '--:--'
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatDateTime(value: string | null): string {
  if (!value) return '--'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
}

export function DashboardClient() {
  const today = useMemo(() => toDateInput(new Date()), [])
  const [date, setDate] = useState(today)
  const [items, setItems] = useState<Score[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [computing, setComputing] = useState(false)
  const [openedScoreId, setOpenedScoreId] = useState<number | null>(null)
  const [configs, setConfigs] = useState<ModelConfig[]>([])
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null)
  const [configsReady, setConfigsReady] = useState(false)
  const [tab, setTab] = useState<DashTab>('upcoming')
  const [scoreScope, setScoreScope] = useState<ScoreScope>('upcoming')

  const activeConfig = useMemo(() => configs.find((c) => c.is_active) ?? null, [configs])
  const selectedConfig = useMemo(
    () => configs.find((c) => c.id === selectedConfigId) ?? activeConfig,
    [configs, selectedConfigId, activeConfig]
  )
  const effectiveConfigId = selectedConfig?.id ?? null
  const recommendedCount = useMemo(() => items.filter((s) => s.is_recommended).length, [items])
  const averageScore = useMemo(() => {
    if (items.length === 0) return 0
    return Math.round(items.reduce((sum, s) => sum + s.total_score, 0) / items.length)
  }, [items])
  const topScore = items[0]?.total_score ?? 0
  const comboTickets = useMemo<ComboTicket[]>(() => {
    const ranked = [...items]
      .filter((s) => s.bet_type != null)
      .sort((a, b) => {
        if (a.is_recommended !== b.is_recommended) return a.is_recommended ? -1 : 1
        return b.total_score - a.total_score
      })
    if (ranked.length < 2) return []

    const makeTicket = (title: string, tone: string, legs: Score[]): ComboTicket => {
      const avg = Math.round(legs.reduce((sum, s) => sum + s.total_score, 0) / legs.length)
      const maxKelly = Math.max(...legs.map((s) => kellyValue(s.kelly_pct)))
      const odds = legs.map((s) => oddsValue(s.bet_odds))
      const comboOdds =
        odds.length === 2 && odds.every((v): v is number => v !== null)
          ? odds.reduce((product, v) => product * v, 1)
          : null
      return {
        title,
        tone,
        legs,
        avgScore: avg,
        kellyText: maxKelly > 0 ? `${(maxKelly * 100).toFixed(2)}%` : '观察',
        comboOdds
      }
    }

    const tickets: ComboTicket[] = [makeTicket('2串1 首选', styles.comboPrimary, ranked.slice(0, 2))]
    const secondLegs = ranked.slice(1, 3)
    if (secondLegs.length === 2) {
      tickets.push(makeTicket('2串1 备选', styles.comboSecondary, secondLegs))
    }
    return tickets
  }, [items])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const res = await listModelConfigs()
        if (cancelled) return
        setConfigs(res.items)
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      } finally {
        if (!cancelled) setConfigsReady(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const load = useCallback(
    async (target: string, cfgId: number | null, scope: ScoreScope) => {
      setLoading(true)
      try {
        const res =
          scope === 'upcoming'
            ? await getTodayScores(cfgId ?? undefined)
            : await getScoresByDate(target, cfgId ?? undefined)
        setItems(res.items)
        setError(null)
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    if (!configsReady) return
    void load(date, effectiveConfigId, scoreScope)
  }, [configsReady, date, effectiveConfigId, scoreScope, load])

  const handleCompute = async () => {
    setComputing(true)
    try {
      if (tab === 'upcoming' && scoreScope === 'upcoming') {
        await computeUpcomingScores(effectiveConfigId ?? undefined)
      } else {
        await computeScores(date, effectiveConfigId ?? undefined)
      }
      await load(date, effectiveConfigId, scoreScope)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setComputing(false)
    }
  }

  const handleUpdated = (updated: Score) => {
    setItems((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
  }

  return (
    <div className={styles.container}>
      <section className={styles.hero}>
        <div className={styles.heroMain}>
          <div className={styles.kicker}>Sporttery 10x 投研台</div>
          <div className={styles.title}>
            {scoreScope === 'upcoming' ? '今日推荐' : '按日期查看'}
          </div>
          <div className={styles.subtitle}>
            {activeConfig && (
              <span data-testid="active-config-name">当前激活模型：{activeConfig.name}</span>
            )}
            {' · '}
            {scoreScope === 'upcoming' ? '未开赛 / 进行中' : date}
          </div>
        </div>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <span>比赛</span>
            <strong>{items.length}</strong>
          </div>
          <div className={styles.metric}>
            <span>推荐</span>
            <strong>{recommendedCount}</strong>
          </div>
          <div className={styles.metric}>
            <span>均分</span>
            <strong>{averageScore}</strong>
          </div>
          <div className={styles.metric}>
            <span>最高</span>
            <strong>{topScore}</strong>
          </div>
        </div>
      </section>

      {tab === 'upcoming' && (
        <section className={styles.comboPanel}>
          <div className={styles.comboHeader}>
            <div>
              <div className={styles.sectionEyebrow}>2串1 推荐</div>
              <div className={styles.sectionTitle}>组合候选</div>
            </div>
            <div className={styles.comboHint}>优先推荐信号，其次按总分补位</div>
          </div>

          {comboTickets.length === 0 ? (
            <div className={styles.comboEmpty}>当前可组合场次不足，重新计算后会自动更新。</div>
          ) : (
            <div className={styles.comboGrid}>
              {comboTickets.map((ticket) => (
                <div
                  key={ticket.title}
                  className={`${styles.comboCard} ${ticket.tone}`}
                  onClick={() => setOpenedScoreId(ticket.legs[0]?.id ?? null)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setOpenedScoreId(ticket.legs[0]?.id ?? null)
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <div className={styles.comboTopline}>
                    <span>{ticket.title}</span>
                    <div>
                      <small>总赔率</small>
                      <strong>{ticket.comboOdds === null ? '-' : ticket.comboOdds.toFixed(2)}</strong>
                    </div>
                  </div>
                  <div className={styles.comboMetaStrip}>
                    <span>组合均分 {ticket.avgScore}</span>
                    <span>参考 Kelly {ticket.kellyText}</span>
                  </div>
                  <div className={styles.comboLegs}>
                    {ticket.legs.map((leg) => (
                      <div key={leg.id} className={styles.comboLeg}>
                        <div>
                          <MatchLink score={leg} compact />
                          <span>
                            {leg.match_round ?? '-'} · {leg.league_name ?? '-'} ·{' '}
                            {formatDateTime(leg.match_date)}
                          </span>
                        </div>
                        <div className={styles.comboLegSignal}>
                          <span>{formatBetType(leg.bet_type)}</span>
                          <em>{formatOdds(leg.bet_odds)}</em>
                          <b title={formatScoreKind(leg)}>{leg.total_score}</b>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className={styles.comboFooter}>
                    <span>竞彩赔率按下注方向读取</span>
                    <strong>平 / 让平</strong>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section className={styles.toolbar}>
        <div className={styles.tabs} role="tablist" aria-label="dashboard-tabs">
          <button
            className={tab === 'upcoming' ? styles.tabActive : styles.tab}
            role="tab"
            aria-selected={tab === 'upcoming'}
            onClick={() => setTab('upcoming')}
          >
            未开始 / 进行中
          </button>
          <button
            className={tab === 'finished' ? styles.tabActive : styles.tab}
            role="tab"
            aria-selected={tab === 'finished'}
            onClick={() => setTab('finished')}
          >
            已结束 · 复盘
          </button>
        </div>

        <div className={styles.controls}>
          {configs.length > 0 && (
            <select
              className={styles.input}
              aria-label="切换评分模型"
              value={effectiveConfigId ?? ''}
              onChange={(e) => {
                const v = e.target.value
                setSelectedConfigId(v === '' ? null : Number(v))
              }}
            >
              {configs.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.is_active ? '（激活）' : ''}
                </option>
              ))}
            </select>
          )}
          <label className={styles.dateControl}>
            <CalendarDays size={16} aria-hidden="true" />
            <input
              type="date"
              value={date}
              onChange={(e) => {
                setScoreScope('date')
                setDate(e.target.value)
              }}
              aria-label="选择日期"
            />
          </label>
          <button
            className={scoreScope === 'upcoming' ? styles.buttonPrimary : styles.button}
            onClick={() => {
              setScoreScope('upcoming')
              setDate(today)
            }}
          >
            未开赛池
          </button>
          <button className={styles.buttonPrimary} onClick={handleCompute} disabled={computing}>
            <Calculator size={16} aria-hidden="true" />
            {computing ? '计算中…' : '立即计算'}
          </button>
          <button className={styles.button} onClick={() => void load(date, effectiveConfigId, scoreScope)}>
            <RefreshCw size={16} aria-hidden="true" />
            刷新
          </button>
        </div>
      </section>

      {tab === 'finished' ? (
        <ReviewClient embedded />
      ) : (
        <>
          {error && <div className={styles.errorBanner}>{error}</div>}

          {loading ? (
            <div className={styles.emptyState}>加载中…</div>
          ) : items.length === 0 ? (
            <div className={styles.emptyState}>暂无评分数据，点击「立即计算」生成</div>
          ) : (
            <div className={styles.tableShell}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>场次</th>
                    <th>比赛</th>
                    <th>联赛</th>
                    <th>总分</th>
                    <th>信号</th>
                    <th>Kelly</th>
                    <th>下注方向</th>
                    <th>命中</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((s, index) => (
                    <tr
                      key={s.id}
                      className={s.is_recommended ? styles.recommendedRow : styles.tableRow}
                      onClick={() => setOpenedScoreId(s.id)}
                    >
                      <td>
                        <div className={styles.matchNo}>
                          <span>{s.match_round ?? String(index + 1).padStart(2, '0')}</span>
                          <small>{formatDateTime(s.match_date)}</small>
                        </div>
                      </td>
                      <td>
                        <div className={styles.teams}>
                          <span className={styles.srOnly}>
                            {s.home_team} vs {s.away_team}
                          </span>
                          <MatchLink score={s} />
                        </div>
                      </td>
                      <td>{s.league_name ?? '-'}</td>
                      <td>
                        <div className={styles.scoreCell}>
                          <span className={`${styles.scorePill} ${scoreTone(s.total_score)}`}>
                            {s.total_score}
                          </span>
                          <small>{formatScoreKind(s)}</small>
                        </div>
                      </td>
                      <td>
                        {s.is_recommended ? (
                          <span className={styles.recommend}>推荐</span>
                        ) : (
                          <span className={styles.neutral}>观察</span>
                        )}
                      </td>
                      <td>{formatKelly(s.kelly_pct)}</td>
                      <td>
                        <span className={styles.betType}>{formatBetType(s.bet_type)}</span>
                      </td>
                      <td>{s.actual_hit === null ? '-' : s.actual_hit ? '命中' : '未中'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {openedScoreId != null && (
        <ScoreDetail
          scoreId={openedScoreId}
          onClose={() => setOpenedScoreId(null)}
          onUpdated={handleUpdated}
        />
      )}
    </div>
  )
}
