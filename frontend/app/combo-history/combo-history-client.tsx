'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'

import {
  listComboRecommendationHistory,
  snapshotTodayCombos
} from '@/lib/combo-recommendations/api'
import type {
  ComboRecommendation,
  ComboRecommendationLeg
} from '@/lib/combo-recommendations/types'
import { listModelConfigs } from '@/lib/model-config/api'
import type { ModelConfig } from '@/lib/model-config/types'

import styles from './combo-history.module.css'

function formatBetType(t: ComboRecommendationLeg['bet_type']): string {
  if (t === 'draw') return '平'
  if (t === 'handicap_draw') return '让平'
  return '-'
}

function formatOdds(v: ComboRecommendation['combo_odds'] | ComboRecommendationLeg['bet_odds']): string {
  if (v === null || v === undefined) return '-'
  const n = typeof v === 'string' ? parseFloat(v) : v
  return Number.isFinite(n) && n > 0 ? n.toFixed(2) : '-'
}

function formatStatus(item: ComboRecommendation): string {
  if (item.status === 'won') return '中奖'
  if (item.status === 'lost') return '未中'
  return '待开奖'
}

function resultText(leg: ComboRecommendationLeg): string {
  if (leg.home_score === null || leg.away_score === null) return '未完赛'
  return `${leg.home_score}-${leg.away_score}`
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

function ComboLegLink({ leg }: { leg: ComboRecommendationLeg }) {
  const label = `${leg.home_team} vs ${leg.away_team}`
  if (!leg.sporttery_url) return <strong>{label}</strong>
  return (
    <a
      className={styles.matchLink}
      href={leg.sporttery_url}
      target="_blank"
      rel="noreferrer"
      title="打开竞彩网固定奖金页面"
    >
      {label}
    </a>
  )
}

export function ComboHistoryClient() {
  const [configs, setConfigs] = useState<ModelConfig[]>([])
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null)
  const [items, setItems] = useState<ComboRecommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [configsReady, setConfigsReady] = useState(false)

  const activeConfig = useMemo(() => configs.find((c) => c.is_active) ?? null, [configs])
  const selectedConfig = useMemo(
    () => configs.find((c) => c.id === selectedConfigId) ?? activeConfig,
    [configs, selectedConfigId, activeConfig]
  )
  const effectiveConfigId = selectedConfig?.id ?? null
  const wonCount = useMemo(() => items.filter((item) => item.status === 'won').length, [items])
  const pendingCount = useMemo(
    () => items.filter((item) => item.status === 'pending').length,
    [items]
  )
  const avgOdds = useMemo(() => {
    const odds = items
      .map((item) => (typeof item.combo_odds === 'string' ? parseFloat(item.combo_odds) : item.combo_odds))
      .filter((v): v is number => v != null && Number.isFinite(v) && v > 0)
    if (odds.length === 0) return '-'
    return (odds.reduce((sum, v) => sum + v, 0) / odds.length).toFixed(2)
  }, [items])

  const load = useCallback(async (cfgId: number | null) => {
    setLoading(true)
    try {
      const res = await listComboRecommendationHistory(cfgId ?? undefined)
      setItems(res.items)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

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

  useEffect(() => {
    if (!configsReady) return
    void load(effectiveConfigId)
  }, [configsReady, effectiveConfigId, load])

  const handleSnapshot = async () => {
    setSyncing(true)
    try {
      await snapshotTodayCombos(effectiveConfigId ?? undefined)
      await load(effectiveConfigId)
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
          <div className={styles.kicker}>Combo Ledger</div>
          <h1>往日推荐</h1>
          <p>
            记录每日 2串1 组合，开奖后按推荐方向自动回填中奖状态。
            {activeConfig && <span> 当前激活模型：{activeConfig.name}</span>}
          </p>
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
          <div className={styles.metric}>
            <span>均赔率</span>
            <strong>{avgOdds}</strong>
          </div>
        </div>
      </section>

      <section className={styles.toolbar}>
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
        <div className={styles.actions}>
          <button className={styles.button} onClick={() => void load(effectiveConfigId)}>
            <RefreshCw size={16} aria-hidden="true" />
            刷新
          </button>
          <button className={styles.buttonPrimary} onClick={handleSnapshot} disabled={syncing}>
            {syncing ? '记录中…' : '记录今日组合'}
          </button>
        </div>
      </section>

      {error && <div className={styles.errorBanner}>{error}</div>}

      {loading ? (
        <div className={styles.emptyState}>加载中…</div>
      ) : items.length === 0 ? (
        <div className={styles.emptyState}>暂无往日推荐记录，今日推荐生成后会自动记录。</div>
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
                    {item.model_name ?? `模型 ${item.model_config_id}`} · 均分 {item.avg_score}
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
                    {formatStatus(item)}
                  </span>
                  <strong>总赔率 {formatOdds(item.combo_odds)}</strong>
                </div>
              </div>
              <div className={styles.historyLegs}>
                {item.legs.map((leg) => (
                  <div key={`${item.id}-${leg.score_id}`} className={styles.historyLeg}>
                    <div>
                      <ComboLegLink leg={leg} />
                      <span>
                        {leg.match_round ?? '-'} · {leg.league_name ?? '-'} ·{' '}
                        {formatDateTime(leg.match_date)}
                      </span>
                    </div>
                    <div className={styles.historyLegSignal}>
                      <span>{formatBetType(leg.bet_type)}</span>
                      <em>{formatOdds(leg.bet_odds)}</em>
                      <b>{resultText(leg)}</b>
                      <strong>{leg.hit === null ? '待定' : leg.hit ? '命中' : '未中'}</strong>
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
