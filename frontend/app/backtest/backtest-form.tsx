'use client'

import { useState } from 'react'

import { InfoTooltip } from '@/components/info-tooltip/info-tooltip'
import { TOOLTIPS } from '@/lib/backtest/tooltips'
import type { BacktestCreatePayload, BacktestMode } from '@/lib/backtest/types'
import type { ModelConfig } from '@/lib/model-config/types'

import styles from './backtest-client.module.css'

interface BacktestFormProps {
  onSubmit: (payload: BacktestCreatePayload) => Promise<void> | void
  loading?: boolean
  modelConfigs: ModelConfig[]
  selectedModelConfigId: number | null
  onModelConfigChange: (id: number | null) => void
}

function defaultDateFrom(): string {
  const d = new Date()
  d.setDate(d.getDate() - 30)
  return d.toISOString().slice(0, 10)
}

function defaultDateTo(): string {
  return new Date().toISOString().slice(0, 10)
}

export function BacktestForm({
  onSubmit,
  loading,
  modelConfigs,
  selectedModelConfigId,
  onModelConfigChange
}: BacktestFormProps) {
  const [dateFrom, setDateFrom] = useState(defaultDateFrom())
  const [dateTo, setDateTo] = useState(defaultDateTo())
  const [mode, setMode] = useState<BacktestMode>('both')
  const [fixedStake, setFixedStake] = useState('100')
  const [initialCapital, setInitialCapital] = useState('10000')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const payload: BacktestCreatePayload = {
      date_from: dateFrom,
      date_to: dateTo,
      mode,
      initial_capital: Number(initialCapital) || 10000,
      fixed_stake: Number(fixedStake) || 100
    }
    if (selectedModelConfigId != null) payload.model_config_id = selectedModelConfigId
    await onSubmit(payload)
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} aria-label="backtest-form">
      <label className={styles.formField}>
        起始日期
        <input
          className={styles.input}
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          required
        />
      </label>
      <label className={styles.formField}>
        结束日期
        <input
          className={styles.input}
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          required
        />
      </label>
      <label className={styles.formField}>
        <span>
          资金模式
          <InfoTooltip text={TOOLTIPS.mode} />
        </span>
        <select
          className={styles.select}
          value={mode}
          onChange={(e) => setMode(e.target.value as BacktestMode)}
        >
          <option value="both">两者兼顾</option>
          <option value="fixed">固定单位</option>
          <option value="kelly">Kelly</option>
        </select>
      </label>
      <label className={styles.formField}>
        <span>
          每场固定投注金额（元）
          <InfoTooltip text={TOOLTIPS.fixed_stake} />
        </span>
        <input
          className={styles.input}
          type="number"
          min="10"
          step="10"
          value={fixedStake}
          onChange={(e) => setFixedStake(e.target.value)}
        />
      </label>
      <label className={styles.formField}>
        <span>
          初始本金（元）
          <InfoTooltip text={TOOLTIPS.initial_capital} />
        </span>
        <input
          className={styles.input}
          type="number"
          min="0"
          step="100"
          value={initialCapital}
          onChange={(e) => setInitialCapital(e.target.value)}
        />
      </label>
      <label className={styles.formField}>
        <span>
          模型配置
          <InfoTooltip text={TOOLTIPS.model_config_id} />
        </span>
        <select
          className={styles.select}
          value={selectedModelConfigId ?? ''}
          onChange={(e) => {
            const value = e.target.value
            onModelConfigChange(value ? Number(value) : null)
          }}
          disabled={modelConfigs.length === 0}
        >
          {modelConfigs.length === 0 ? (
            <option value="">暂无模型配置</option>
          ) : (
            modelConfigs.map((cfg) => (
              <option key={cfg.id} value={cfg.id}>
                {cfg.name}
                {cfg.is_active ? '（激活）' : ''}
              </option>
            ))
          )}
        </select>
      </label>
      <div className={styles.actions}>
        <button className={styles.buttonPrimary} type="submit" disabled={loading}>
          {loading ? '回测中…' : '开始回测'}
        </button>
      </div>
    </form>
  )
}
