import type { ResearchRun } from '@/lib/research/types'
import Link from 'next/link'

import styles from './combo-reports.module.css'

interface ResearchSummaryProps {
  run: ResearchRun | null
}

function formatPct(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return `${(value * 100).toFixed(2)}%`
}

export function ResearchSummary({ run }: ResearchSummaryProps) {
  if (!run) {
    return <div className={styles.hint}>暂无研究报告。</div>
  }
  const summary = run.summary_json ?? {}
  const comboCount = summary.same_day_combo_count ?? summary.best_strategy_combo_count
  const modelRoi = summary.same_day_combo_roi ?? summary.best_strategy_roi
  const strategyLabel = summary.best_strategy ? ` · 最佳策略：${summary.best_strategy}` : ''
  const randomLabel = summary.random_label
    ? `随机均值 ROI（${summary.random_label}）`
    : '随机均值 ROI'
  return (
    <section className={styles.researchCard} aria-label="research-summary">
      <div>
        <div className={styles.sectionTitle}>研究报告</div>
        <div className={styles.historyMeta}>
          {run.name} · {run.date_from} → {run.date_to}
          {strategyLabel}
        </div>
      </div>
      <div className={styles.researchMetrics}>
        <div>
          <span className={styles.cardLabel}>候选场次</span>
          <strong>{summary.candidates ?? '-'}</strong>
        </div>
        <div>
          <span className={styles.cardLabel}>同日二串一</span>
          <strong>{comboCount ?? '-'}</strong>
        </div>
        <div>
          <span className={styles.cardLabel}>模型 ROI</span>
          <strong>{formatPct(modelRoi)}</strong>
        </div>
        <div>
          <span className={styles.cardLabel}>{randomLabel}</span>
          <strong>{formatPct(summary.random_roi_avg)}</strong>
        </div>
        <div>
          <span className={styles.cardLabel}>超过随机百分位</span>
          <strong>{formatPct(summary.model_roi_percentile_vs_random)}</strong>
        </div>
      </div>
      <div className={styles.researchFooter}>
        {run.report_path ? <div className={styles.historyMeta}>报告：{run.report_path}</div> : null}
        <Link className={styles.detailLink} href={`/combo-reports/${run.id}`}>
          查看明细报告
        </Link>
      </div>
    </section>
  )
}
