'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import {
  compareBacktests,
  createBacktest,
  deleteBacktest,
  getBacktest,
  listBacktests
} from '@/lib/backtest/api'
import type {
  BacktestCompareResponse,
  BacktestCreatePayload,
  BacktestSummary as BacktestSummaryData
} from '@/lib/backtest/types'
import { listModelConfigs } from '@/lib/model-config/api'
import type { ModelConfig } from '@/lib/model-config/types'
import Link from 'next/link'

import { BacktestBetsTable } from './backtest-bets-table'
import { BacktestForm } from './backtest-form'
import { BacktestSummary } from './backtest-summary'
import styles from './backtest-client.module.css'

export function BacktestClient() {
  const [history, setHistory] = useState<BacktestSummaryData[]>([])
  const [selected, setSelected] = useState<BacktestSummaryData | null>(null)
  const [compareIds, setCompareIds] = useState<number[]>([])
  const [compareData, setCompareData] = useState<BacktestCompareResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([])
  const [selectedModelConfigId, setSelectedModelConfigId] = useState<number | null>(null)
  const pickTokenRef = useRef(0)
  const resultRef = useRef<HTMLDivElement | null>(null)

  const scrollToResult = useCallback(() => {
    window.requestAnimationFrame(() => {
      window.history.replaceState(null, '', '#backtest-result')
      resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }, [])

  const reloadHistory = useCallback(async () => {
    try {
      const res = await listBacktests(20, 0)
      setHistory(res.items)
      return res.items
    } catch (e) {
      setError((e as Error).message)
      return []
    }
  }, [])

  useEffect(() => {
    void reloadHistory()
  }, [reloadHistory])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const res = await listModelConfigs()
        if (cancelled) return
        setModelConfigs(res.items)
        setSelectedModelConfigId((current) => current ?? res.items[0]?.id ?? null)
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const handleSubmit = async (payload: BacktestCreatePayload) => {
    setLoading(true)
    setError(null)
    pickTokenRef.current += 1
    try {
      const created = await createBacktest(payload)
      setSelected(created)
      setCompareIds([])
      setCompareData(null)
      await reloadHistory()
      scrollToResult()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handlePickHistory = async (id: number) => {
    const token = ++pickTokenRef.current
    try {
      const data = await getBacktest(id)
      if (token !== pickTokenRef.current) return
      setSelected(data)
      setCompareData(null)
      scrollToResult()
    } catch (e) {
      if (token !== pickTokenRef.current) return
      setError((e as Error).message)
    }
  }

  const handleToggleComparePick = (id: number) => {
    setCompareData(null)
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      if (prev.length >= 2) return [prev[1], id]
      return [...prev, id]
    })
  }

  const handleClearCompare = () => {
    setCompareIds([])
    setCompareData(null)
  }

  const handleStartCompare = async () => {
    if (compareIds.length !== 2) return
    const token = ++pickTokenRef.current
    setError(null)
    try {
      const cmp = await compareBacktests(compareIds[0], compareIds[1])
      if (token !== pickTokenRef.current) return
      setCompareData(cmp)
      scrollToResult()
    } catch (e) {
      if (token !== pickTokenRef.current) return
      setError((e as Error).message)
    }
  }

  const handleDeleteHistory = async (item: BacktestSummaryData) => {
    const ok = window.confirm(`确认删除回测 #${item.id}？此操作不会删除比赛数据。`)
    if (!ok) return
    pickTokenRef.current += 1
    setError(null)
    try {
      await deleteBacktest(item.id)
      setHistory((prev) => prev.filter((h) => h.id !== item.id))
      setCompareIds((prev) => prev.filter((id) => id !== item.id))
      setCompareData(null)
      if (selected?.id === item.id) setSelected(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const compareItems = compareIds
    .map((id) => history.find((h) => h.id === id))
    .filter((h): h is BacktestSummaryData => h != null)

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>历史回测</div>
          <div className={styles.subtitle}>基于最新赔率重跑推荐场，评估模型表现</div>
        </div>
        <Link className={styles.detailLink} href="/combo-reports">
          查看二串一测试报告
        </Link>
      </div>

      <BacktestForm
        onSubmit={handleSubmit}
        loading={loading}
        modelConfigs={modelConfigs}
        selectedModelConfigId={selectedModelConfigId}
        onModelConfigChange={setSelectedModelConfigId}
      />

      {error && <div className={styles.errorBanner}>{error}</div>}

      <section>
        <div className={styles.sectionTitle}>历史回测列表</div>
        <div className={styles.compareTray}>
          <div>
            <div className={styles.compareTrayTitle}>对比篮</div>
            <div className={styles.compareTrayHint}>选择两条历史回测后开始对比。</div>
          </div>
          <div className={styles.compareSlots}>
            {[0, 1].map((idx) => {
              const item = compareItems[idx]
              return (
                <div key={idx} className={styles.compareSlot}>
                  <span className={styles.pill}>{idx === 0 ? 'A' : 'B'}</span>
                  {item ? (
                    <>
                      #{item.id} · {modelNameFor(item, modelConfigs)}
                      <button
                        type="button"
                        className={styles.inlineButton}
                        onClick={() => handleToggleComparePick(item.id)}
                      >
                        移除
                      </button>
                    </>
                  ) : (
                    <span className={styles.muted}>待选择</span>
                  )}
                </div>
              )
            })}
          </div>
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.buttonPrimary}
              onClick={() => void handleStartCompare()}
              disabled={compareIds.length !== 2}
            >
              开始对比
            </button>
            <button
              type="button"
              className={styles.button}
              onClick={handleClearCompare}
              disabled={compareIds.length === 0}
            >
              清空
            </button>
          </div>
        </div>
        {history.length === 0 ? (
          <div className={styles.hint}>暂无历史回测，请通过上方表单发起一次回测。</div>
        ) : (
          <div className={styles.historyList}>
            {history.map((h) => {
              const isSel = selected?.id === h.id
              const compareIndex = compareIds.indexOf(h.id)
              const isCmp = compareIndex >= 0
              const modelName = modelNameFor(h, modelConfigs)
              return (
                <div
                  key={h.id}
                  className={`${styles.historyRow} ${isSel || isCmp ? styles.selected : ''}`}
                  onClick={() => void handlePickHistory(h.id)}
                >
                  <div>
                    <div>
                      <span className={styles.pill}>#{h.id}</span>
                      {h.date_from} → {h.date_to}
                    </div>
                    <div className={styles.historyMeta}>
                      回测时间：{formatDateTime(h.created_at)} · 模型：{modelName}
                    </div>
                  </div>
                  <div>
                    <span className={styles.pill}>{formatBacktestMode(h.mode)}</span>
                    {h.total_bets} 场 · 命中 {h.hit_count}
                  </div>
                  <div className={styles.historyActions}>
                    <button
                      type="button"
                      className={styles.button}
                      onClick={(e) => {
                        e.stopPropagation()
                        void handlePickHistory(h.id)
                      }}
                    >
                      查看
                    </button>
                    <button
                      type="button"
                      className={isCmp ? styles.buttonPrimary : styles.button}
                      onClick={(e) => {
                        e.stopPropagation()
                        handleToggleComparePick(h.id)
                      }}
                    >
                      {isCmp ? `已选 ${compareIndex === 0 ? 'A' : 'B'}` : '加入对比'}
                    </button>
                    <button
                      type="button"
                      className={styles.dangerButton}
                      onClick={(e) => {
                        e.stopPropagation()
                        void handleDeleteHistory(h)
                      }}
                    >
                      删除
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {compareData ? (
        <section id="backtest-result" ref={resultRef} className={styles.anchorSection}>
          <div className={styles.sectionTitle}>双模型对比</div>
          <div className={styles.compareGrid}>
            <div>
              <div className={styles.chartTitle}>A：#{compareData.a.id}</div>
              <BacktestSummary data={compareData.a} />
            </div>
            <div>
              <div className={styles.chartTitle}>B：#{compareData.b.id}</div>
              <BacktestSummary data={compareData.b} />
            </div>
          </div>
        </section>
      ) : selected ? (
        <div id="backtest-result" ref={resultRef} className={styles.anchorSection}>
          <section>
            <div className={styles.sectionTitle}>
              回测概览 <span className={styles.pill}>#{selected.id}</span>
            </div>
            <BacktestSummary data={selected} />
          </section>
          <section>
            <BacktestBetsTable bets={selected.bets_detail} />
          </section>
        </div>
      ) : null}
    </div>
  )
}

function modelNameFor(item: BacktestSummaryData, configs: ModelConfig[]): string {
  return (
    configs.find((cfg) => cfg.id === item.model_config_id)?.name ?? `模型 #${item.model_config_id}`
  )
}

function formatBacktestMode(mode: BacktestSummaryData['mode']): string {
  if (mode === 'both') return '固定+Kelly'
  if (mode === 'fixed') return '固定投注'
  if (mode === 'kelly') return 'Kelly'
  return mode
}

function formatDateTime(value?: string | null): string {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}`
}
