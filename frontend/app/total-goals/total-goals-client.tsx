'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Calculator, CalendarDays, RefreshCw } from 'lucide-react'

import {
  computeTotalGoals,
  computeUpcomingTotalGoals,
  getTodayTotalGoals,
  getTotalGoalsByDate,
  snapshotTodayTotalGoalCombos
} from '@/lib/total-goals/api'
import type { TotalGoalCombo, TotalGoalItem } from '@/lib/total-goals/types'

import styles from './total-goals.module.css'

type Scope = 'upcoming' | 'date'

function toDateInput(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function formatDecimal(v: string | number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return '-'
  const n = typeof v === 'string' ? parseFloat(v) : v
  return Number.isFinite(n) ? n.toFixed(digits) : '-'
}

function formatPct(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return '-'
  const n = typeof v === 'string' ? parseFloat(v) : v
  return Number.isFinite(n) ? `${n.toFixed(1)}%` : '-'
}

function oddsText(item: TotalGoalItem): string {
  return item.odds_label || formatDecimal(item.bet_odds)
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

function resultText(item: TotalGoalItem): string {
  if (item.home_score === null || item.away_score === null) return '未完赛'
  return `${item.home_score}-${item.away_score} / ${item.actual_total_goals}球`
}

function statusText(item: TotalGoalItem): string {
  if (item.hit === null) return '待开奖'
  return item.hit ? '命中' : '未中'
}

function comboStatusText(combo: TotalGoalCombo): string {
  if (combo.status === 'won') return '中奖'
  if (combo.status === 'lost') return '未中'
  return '待开奖'
}

function comboOddsText(combo: TotalGoalCombo): string {
  return combo.combo_odds_label || formatDecimal(combo.combo_odds)
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

function scoreTone(score: number): string {
  if (score >= 84) return styles.scoreElite
  if (score >= 78) return styles.scoreStrong
  if (score >= 68) return styles.scoreWatch
  return styles.scoreMuted
}

export function TotalGoalsClient() {
  const today = useMemo(() => toDateInput(new Date()), [])
  const [scope, setScope] = useState<Scope>('upcoming')
  const [date, setDate] = useState(today)
  const [items, setItems] = useState<TotalGoalItem[]>([])
  const [combos, setCombos] = useState<TotalGoalCombo[]>([])
  const [loading, setLoading] = useState(true)
  const [computing, setComputing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const recommended = useMemo(() => items.filter((item) => item.is_recommended).length, [items])
  const avgScore = useMemo(() => {
    if (items.length === 0) return 0
    return Math.round(items.reduce((sum, item) => sum + item.total_score, 0) / items.length)
  }, [items])
  const topScore = items[0]?.total_score ?? 0

  const load = useCallback(async (nextScope: Scope, targetDate: string) => {
    setLoading(true)
    try {
      if (nextScope === 'upcoming') {
        const res = await getTodayTotalGoals()
        setItems(res.items)
        setCombos(res.combos)
        if (res.combos.length > 0) {
          try {
            await snapshotTodayTotalGoalCombos()
          } catch {
            // Snapshot is a convenience write; live recommendations can still render.
          }
        }
      } else {
        const res = await getTotalGoalsByDate(targetDate)
        setItems(res.items)
        setCombos([])
      }
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(scope, date)
  }, [scope, date, load])

  const handleCompute = async () => {
    setComputing(true)
    try {
      if (scope === 'upcoming') {
        await computeUpcomingTotalGoals()
      } else {
        await computeTotalGoals(date)
      }
      await load(scope, date)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setComputing(false)
    }
  }

  return (
    <div className={styles.container}>
      <section className={styles.hero}>
        <div>
          <div className={styles.kicker}>Total Goals Model</div>
          <h1>总进球数推荐</h1>
          <p>独立 tg-v1 模型：优先做 1,2球 这种容错组合，再结合近期进球、主客场走势、交锋进球和赔率价值打分。</p>
        </div>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <span>比赛</span>
            <strong>{items.length}</strong>
          </div>
          <div className={styles.metric}>
            <span>推荐</span>
            <strong>{recommended}</strong>
          </div>
          <div className={styles.metric}>
            <span>均分</span>
            <strong>{avgScore}</strong>
          </div>
          <div className={styles.metric}>
            <span>最高</span>
            <strong>{topScore}</strong>
          </div>
        </div>
      </section>

      {scope === 'upcoming' && (
        <section className={styles.comboPanel}>
          <div className={styles.comboHeader}>
            <div>
              <div className={styles.sectionEyebrow}>串关候选</div>
              <div className={styles.sectionTitle}>总进球数 2串1</div>
            </div>
            <div className={styles.comboHint}>优先用 1,2球 串 1,2球；不足两场时仅展示观察组合。</div>
          </div>
          {combos.length === 0 ? (
            <div className={styles.emptyInline}>暂无可组合场次，点击立即计算刷新。</div>
          ) : (
            <div className={styles.comboGrid}>
              {combos.map((combo) => (
                <article key={combo.title} className={styles.comboCard}>
                  <div className={styles.comboTopline}>
                    <span>{combo.title}</span>
                    <strong>折算赔率范围 {comboOddsText(combo)}</strong>
                  </div>
                  <div className={styles.comboMeta}>
                    <span>均分 {combo.avg_score}</span>
                    <span>{comboStatusText(combo)}</span>
                  </div>
                  {combo.items.map((item) => (
                    <div key={item.id} className={styles.comboLeg}>
                      <div>
                        <MatchLink item={item} />
                        <span>
                          {item.match_round ?? '-'} · {item.league_name ?? '-'} · {formatDateTime(item.match_date)}
                        </span>
                      </div>
                      <div className={styles.legSignal}>
                        <span>{item.target_label}球</span>
                        <em>{oddsText(item)}</em>
                        <b>{item.total_score}</b>
                      </div>
                    </div>
                  ))}
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      <section className={styles.toolbar}>
        <div className={styles.controls}>
          <label className={styles.dateControl}>
            <CalendarDays size={16} aria-hidden="true" />
            <input
              type="date"
              value={date}
              onChange={(e) => {
                setScope('date')
                setDate(e.target.value)
              }}
            />
          </label>
          <button
            className={scope === 'upcoming' ? styles.buttonPrimary : styles.button}
            onClick={() => {
              setScope('upcoming')
              setDate(today)
            }}
          >
            未开赛池
          </button>
          <button className={styles.buttonPrimary} onClick={handleCompute} disabled={computing}>
            <Calculator size={16} aria-hidden="true" />
            {computing ? '计算中…' : '立即计算'}
          </button>
          <button className={styles.button} onClick={() => void load(scope, date)}>
            <RefreshCw size={16} aria-hidden="true" />
            刷新
          </button>
        </div>
      </section>

      {error && <div className={styles.errorBanner}>{error}</div>}

      {loading ? (
        <div className={styles.emptyState}>加载中…</div>
      ) : items.length === 0 ? (
        <div className={styles.emptyState}>暂无总进球数评分，点击「立即计算」生成。</div>
      ) : (
        <section className={styles.tableShell}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>场次</th>
                <th>比赛</th>
                <th>总进球</th>
                <th>分数</th>
                <th>置信</th>
                <th>赔率</th>
                <th>盘口/预期</th>
                <th>赛果</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className={item.is_recommended ? styles.recommendedRow : styles.tableRow}>
                  <td>
                    <div className={styles.matchNo}>
                      <span>{item.match_round ?? '-'}</span>
                      <small>{formatDateTime(item.match_date)}</small>
                    </div>
                  </td>
                  <td>
                    <div className={styles.teams}>
                      <MatchLink item={item} />
                      <small>{item.league_name ?? '-'}</small>
                    </div>
                  </td>
                  <td>
                    <span className={styles.goalPill}>{item.target_label}球</span>
                  </td>
                  <td>
                    <span className={`${styles.scorePill} ${scoreTone(item.total_score)}`}>
                      {item.total_score}
                    </span>
                  </td>
                  <td>{formatPct(item.confidence_pct)}</td>
                  <td>{oddsText(item)}</td>
                  <td>
                    <div className={styles.expectation}>
                      <span>盘口 {formatDecimal(item.explanation?.market_line ?? null, 1)}</span>
                      <span>预期 {formatDecimal(item.explanation?.expected_goals ?? null, 2)}</span>
                    </div>
                  </td>
                  <td>{resultText(item)}</td>
                  <td>
                    <span className={item.hit === true ? styles.hit : item.hit === false ? styles.miss : styles.pending}>
                      {statusText(item)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
