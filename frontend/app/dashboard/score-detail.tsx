'use client'

import { useEffect, useState } from 'react'

import { getScoreBreakdown, updateScore } from '@/lib/scores/api'
import type { Score, ScoreBreakdown } from '@/lib/scores/types'

import styles from './dashboard-client.module.css'

interface Props {
  scoreId: number
  onClose: () => void
  onUpdated: (score: Score) => void
}

function formatBetType(t: Score['bet_type']): string {
  if (t === 'draw') return '平'
  if (t === 'handicap_draw') return '让平'
  return '-'
}

function formatKelly(v: Score['kelly_pct']): string {
  if (v === null || v === undefined) return '-'
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (!Number.isFinite(n) || n === 0) return '-'
  return `${(n * 100).toFixed(2)}%`
}

function formatScoreMode(score: Score): string {
  return score.score_mode === 'rule' ? '规则分' : '6维分'
}

function MatchTitle({ score }: { score: Score }) {
  const label = `${score.home_team ?? '-'} vs ${score.away_team ?? '-'}`
  if (!score.sporttery_url) return <>{label}</>
  return (
    <a
      className={styles.matchLink}
      href={score.sporttery_url}
      target="_blank"
      rel="noreferrer"
      title="打开竞彩网固定奖金页面"
    >
      {label}
    </a>
  )
}

export function ScoreDetail({ scoreId, onClose, onUpdated }: Props) {
  const [data, setData] = useState<ScoreBreakdown | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const [notes, setNotes] = useState('')
  const [betAmount, setBetAmount] = useState('')
  const [actualHit, setActualHit] = useState<boolean | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setLoading(true)
    getScoreBreakdown(scoreId)
      .then((res) => {
        setData(res)
        setNotes(res.score.notes ?? '')
        setBetAmount(res.score.bet_amount != null ? String(res.score.bet_amount) : '')
        setActualHit(res.score.actual_hit)
        setError(null)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [scoreId])

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await updateScore(scoreId, {
        notes: notes || null,
        bet_amount: betAmount ? Number(betAmount) : null,
        actual_hit: actualHit
      })
      onUpdated(updated)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className={styles.backdrop}
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <aside className={styles.drawer}>
        <div className={styles.drawerHeader}>
          <div className={styles.title}>评分详情</div>
          <button className={styles.close} onClick={onClose} aria-label="关闭">
            x
          </button>
        </div>

        {error && <div className={styles.errorBanner}>{error}</div>}

        {loading && <div className={styles.emptyState}>加载中…</div>}

        {data && (
          <>
            {(() => {
              const dimensionTotal = data.parts.reduce((sum, p) => sum + p.score, 0)
              const dimensionMax = data.parts.reduce((sum, p) => sum + p.max_score, 0)

              return (
                <>
                  <div className={styles.subtitle}>
                    <MatchTitle score={data.score} /> · {formatScoreMode(data.score)} {data.score.total_score}
                  </div>
                  <div className={styles.metaGrid}>
                    <div>
                      <span>推荐</span>
                      <strong>{data.score.is_recommended ? '是' : '否'}</strong>
                    </div>
                    <div>
                      <span>下注方向</span>
                      <strong>{formatBetType(data.score.bet_type)}</strong>
                    </div>
                    <div>
                      <span>Kelly</span>
                      <strong>{formatKelly(data.score.kelly_pct)}</strong>
                    </div>
                    <div>
                      <span>规则分</span>
                      <strong>
                        {data.score.rule_score === null || data.score.rule_score === undefined
                          ? '-'
                          : data.score.rule_score}
                      </strong>
                    </div>
                    <div>
                      <span>6维解释分</span>
                      <strong>
                        {data.score.diagnostic_score ?? dimensionTotal} / {dimensionMax}
                      </strong>
                    </div>
                  </div>
                  {data.score.rule_explanation && (
                    <div className={styles.ruleExplain}>
                      <strong>{data.score.rule_name ?? '规则命中'}</strong>
                      <span>{data.score.rule_explanation}</span>
                    </div>
                  )}
                </>
              )
            })()}
            <ul className={styles.breakdownList}>
              {data.parts.map((p) => (
                <li key={p.dimension} className={styles.breakdownItem}>
                  <div className={styles.dimLine}>
                    <span>{p.dimension}</span>
                    <span>
                      {p.score} / {p.max_score}
                    </span>
                  </div>
                  <div
                    className={styles.scoreTrack}
                    aria-label={`${p.dimension} ${p.score} of ${p.max_score}`}
                  >
                    <div
                      className={styles.scoreFill}
                      style={{ width: `${Math.min(100, (p.score / p.max_score) * 100)}%` }}
                    />
                  </div>
                  <div className={styles.dimExplain}>{p.explanation}</div>
                </li>
              ))}
            </ul>

            <div className={styles.form}>
              <label className={styles.label}>
                备注
                <textarea
                  className={styles.textarea}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="记录本场分析"
                />
              </label>
              <label className={styles.label}>
                下注金额
                <input
                  className={styles.input}
                  type="number"
                  min="0"
                  step="0.01"
                  value={betAmount}
                  onChange={(e) => setBetAmount(e.target.value)}
                />
              </label>
              <div className={styles.checkboxRow}>
                <label className={styles.label} htmlFor="hit-select">
                  实际命中
                </label>
                <select
                  id="hit-select"
                  className={styles.input}
                  value={actualHit === null ? '' : actualHit ? 'y' : 'n'}
                  onChange={(e) => {
                    const v = e.target.value
                    setActualHit(v === '' ? null : v === 'y')
                  }}
                >
                  <option value="">未知</option>
                  <option value="y">命中</option>
                  <option value="n">未中</option>
                </select>
              </div>
              <button className={styles.buttonPrimary} onClick={handleSave} disabled={saving}>
                {saving ? '保存中…' : '保存'}
              </button>
            </div>
          </>
        )}
      </aside>
    </div>
  )
}
