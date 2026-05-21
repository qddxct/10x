import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ResearchSummary } from '@/app/combo-reports/research-summary'

describe('ResearchSummary', () => {
  it('renders empty state', () => {
    render(<ResearchSummary run={null} />)
    expect(screen.getByText('暂无研究报告。')).toBeInTheDocument()
  })

  it('renders research metrics', () => {
    render(
      <ResearchSummary
        run={{
          id: 1,
          name: 'v33-single-factor-combo-diagnostic',
          base_model_config_id: 8,
          date_from: '2024-09-28',
          date_to: '2026-04-22',
          random_seed: 20260426,
          random_trials: 1000,
          status: 'succeeded',
          summary_json: {
            candidates: 561,
            same_day_combo_count: 120,
            same_day_combo_roi: 0.12,
            random_roi_avg: -0.08,
            model_roi_percentile_vs_random: 0.91
          },
          report_path: 'docs/analysis/report.md',
          created_at: '2026-04-26T14:30:00'
        }}
      />
    )
    expect(
      screen.getByText('v33-single-factor-combo-diagnostic · 2024-09-28 → 2026-04-22')
    ).toBeInTheDocument()
    expect(screen.getByText('12.00%')).toBeInTheDocument()
    expect(screen.getByText('91.00%')).toBeInTheDocument()
  })

  it('renders v34 best strategy metrics', () => {
    render(
      <ResearchSummary
        run={{
          id: 5,
          name: 'v34-combo-selector',
          base_model_config_id: 8,
          date_from: '2024-09-28',
          date_to: '2026-04-22',
          random_seed: 20260426,
          random_trials: 1000,
          status: 'succeeded',
          summary_json: {
            candidates: 561,
            best_strategy: 'frequency_selector',
            best_strategy_combo_count: 139,
            best_strategy_roi: 0.4972388489,
            random_label: '候选池约束随机',
            random_roi_avg: 0.2375,
            model_roi_percentile_vs_random: 0.819
          },
          report_path: 'docs/analysis/v34.md',
          created_at: '2026-04-26T14:50:00'
        }}
      />
    )
    expect(screen.getByText(/最佳策略：frequency_selector/)).toBeInTheDocument()
    expect(screen.getByText('49.72%')).toBeInTheDocument()
    expect(screen.getByText('随机均值 ROI（候选池约束随机）')).toBeInTheDocument()
    expect(screen.getByText('23.75%')).toBeInTheDocument()
    expect(screen.getByText('81.90%')).toBeInTheDocument()
    expect(screen.getByText('139')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看明细报告' })).toHaveAttribute(
      'href',
      '/combo-reports/5'
    )
  })
})
