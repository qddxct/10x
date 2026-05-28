'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'

import {
  listTotalGoalComboHistory,
  snapshotTodayTotalGoalCombos
} from '@/lib/total-goals/api'
import type { TotalGoalComboHistoryItem, TotalGoalItem } from '@/lib/total-goals/types'

import styles from './total-goals-history.module.css'

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

function resultText(item: TotalGoalItem): string {
  if (item.home_score === null || item.away_score === null) return '未完赛'
  return `${item.home_score}-${item.away_score} / ${item.actual_total_goals}球`
}

function statusText(hit: boolean | null): string {
  if (hit === null) return '待开奖'
  return hit ? '命中' : '未中'
}

function comboStatusText(item: TotalGoalComboHistoryItem): string {
  if (item.status === 'won') return '中奖'
  if (item.status === 'lost') return '未中'
  return '待开奖'
}

function MatchLink({ item }: { item: TotalGoalItem }) {
  const label = `${item.home_team ?? '-'} vs ${item.away_team ?? '-'}`
  if (!item.sporttery_url) return <strong>{label}</strong>
  return (
    <a href={item.sporttery_url} target="_blank" rel="noreferrer" className={styles.matchLink}>
      {label}
    </a>
  )
}

export function TotalGoalsHistoryClient() {
  const [items, setItems] = useState<TotalGoalComboHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const wonCount = useMemo(() => items.filter((item) => item.status === 'won').length, [items])
  const pendingCount = useMemo(
    () => items.filter((item) => item.status === 'pending').length,
    [items]
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await listTotalGoalComboHistory()
      setItems(res.items)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleSnapshot = async () => {
    setSyncing(true)
    try {
      await snapshotTodayTotalGoalCombos()
      await load()
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className={styles.container}>
      <section className={styles.hero}>
        <div>
          <div className={styles.kicker}>Total Goals Ledger</div>
          <h1>总进球往日推荐</h1>
          <p>记录每日总进球数 2串1，开奖后按 1,2球 等候选集合自动判断命中。</p>
        </div>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <span>记录</span>
            <strong>{items.length}</strong>
          </div>
          <div className={styles.metric}>
            <span>中奖</span>
            <strong>{wonCount}</strong>
          </div>
          <div className={styles.metric}>
            <span>待开奖</span>
            <strong>{pendingCount}</strong>
          </div>
        </div>
      </section>

      <section className={styles.toolbar}>
        <button className={styles.button} onClick={() => void load()}>
          <RefreshCw size={16} aria-hidden="true" />
          刷新
        </button>
        <button className={styles.buttonPrimary} onClick={handleSnapshot} disabled={syncing}>
          {syncing ? '记录中…' : '记录今日组合'}
        </button>
      </section>

      {error && <div className={styles.errorBanner}>{error}</div>}

      {loading ? (
        <div className={styles.emptyState}>加载中…</div>
      ) : items.length === 0 ? (
        <div className={styles.emptyState}>暂无总进球往日推荐，今日总进球数生成后会自动记录。</div>
      ) : (
        <section className={styles.historyPanel}>
          {items.map((item) => (
            <article key={item.id} className={styles.historyCard}>
              <div className={styles.historyTopline}>
                <div>
                  <div className={styles.historyDate}>
                    {item.recommendation_date} · {item.title}
                  </div>
                  <div className={styles.historyModel}>
                    {item.model_version} · 均分 {item.avg_score}
                  </div>
                </div>
                <div className={styles.historySignal}>
                  <span
                    className={
                      item.status === 'won'
                        ? styles.historyWon
                        : item.status === 'lost'
                          ? styles.historyLost
                          : styles.historyPending
                    }
                  >
                    {comboStatusText(item)}
                  </span>
                  <strong>折算赔率 {item.combo_odds_label ?? '-'}</strong>
                </div>
              </div>
              <div className={styles.historyLegs}>
                {item.items.map((leg) => (
                  <div key={`${item.id}-${leg.match_id}`} className={styles.historyLeg}>
                    <div>
                      <MatchLink item={leg} />
                      <span>
                        {leg.match_round ?? '-'} · {leg.league_name ?? '-'} ·{' '}
                        {formatDateTime(leg.match_date)}
                      </span>
                    </div>
                    <div className={styles.historyLegSignal}>
                      <span>{leg.target_label}球</span>
                      <em>{leg.odds_label ?? '-'}</em>
                      <b>{resultText(leg)}</b>
                      <strong>{statusText(leg.hit)}</strong>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  )
}
