'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import { generateComboResearchReport, getLatestResearchRun } from '@/lib/research/api'
import type { ResearchRun } from '@/lib/research/types'

import styles from './combo-reports.module.css'
import { GenerateReportForm } from './generate-report-form'
import { ResearchSummary } from './research-summary'

export function ComboReportsClient() {
  const router = useRouter()
  const [run, setRun] = useState<ResearchRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        setLoading(true)
        const latest = await getLatestResearchRun()
        if (cancelled) return
        setRun(latest)
        setError(null)
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main className={styles.container}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>二串一测试报告</div>
          <div className={styles.subtitle}>查看组合策略、随机对照、投入收益和明细方案</div>
        </div>
        <Link className={styles.backLink} href="/backtest">
          返回历史回测
        </Link>
      </div>

      <GenerateReportForm
        onGenerate={async (payload) => {
          const result = await generateComboResearchReport(payload)
          router.push(`/combo-reports/${result.run_id}`)
          return result
        }}
      />

      {error ? <div className={styles.errorBanner}>报告加载失败：{error}</div> : null}
      {loading ? (
        <div className={styles.hint}>正在加载二串一测试报告...</div>
      ) : (
        <ResearchSummary run={run} />
      )}
    </main>
  )
}
