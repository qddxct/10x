'use client'

import { FormEvent, useState } from 'react'

import type {
  GenerateComboResearchPayload,
  GenerateComboResearchResponse
} from '@/lib/research/types'

import styles from './combo-reports.module.css'

const MODEL_NAME = 'empirical-v32-filtered-candidate'

interface Props {
  onGenerate: (payload: GenerateComboResearchPayload) => Promise<GenerateComboResearchResponse>
}

export function GenerateReportForm({ onGenerate }: Props) {
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [randomTrials, setRandomTrials] = useState(1000)
  const [randomSeed, setRandomSeed] = useState(20260426)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    if (!dateFrom || !dateTo) {
      setError('请选择开始日期和结束日期')
      return
    }
    try {
      setLoading(true)
      await onGenerate({
        date_from: dateFrom,
        date_to: dateTo,
        model_name: MODEL_NAME,
        random_trials: randomTrials,
        random_seed: randomSeed
      })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className={styles.generatorCard}>
      <div>
        <div className={styles.sectionTitle}>生成研究报告</div>
        <p className={styles.hint}>
          选择历史区间后，系统会重算 V3.2 候选 score，并生成二串一研究报告。
        </p>
      </div>
      {error ? <div className={styles.errorBanner}>报告生成失败：{error}</div> : null}
      <form className={styles.generatorForm} onSubmit={handleSubmit}>
        <label>
          开始日期
          <input
            aria-label="开始日期"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </label>
        <label>
          结束日期
          <input
            aria-label="结束日期"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </label>
        <label>
          模型
          <input aria-label="模型" value={MODEL_NAME} disabled />
        </label>
        <button
          type="button"
          className={styles.secondaryButton}
          onClick={() => setShowAdvanced((value) => !value)}
        >
          {showAdvanced ? '收起高级参数' : '展开高级参数'}
        </button>
        {showAdvanced ? (
          <>
            <label>
              随机试验次数
              <input
                aria-label="随机试验次数"
                type="number"
                min={100}
                max={5000}
                value={randomTrials}
                onChange={(e) => setRandomTrials(Number(e.target.value))}
              />
            </label>
            <label>
              随机种子
              <input
                aria-label="随机种子"
                type="number"
                min={1}
                max={999999999}
                value={randomSeed}
                onChange={(e) => setRandomSeed(Number(e.target.value))}
              />
            </label>
          </>
        ) : null}
        <button className={styles.primaryButton} disabled={loading} type="submit">
          {loading ? '正在生成研究报告...' : '生成报告'}
        </button>
      </form>
    </section>
  )
}
