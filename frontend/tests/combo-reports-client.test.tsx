import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const push = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push })
}))

vi.mock('@/lib/research/api', () => ({
  generateComboResearchReport: vi.fn(),
  getLatestResearchRun: vi.fn()
}))

import { ComboReportsClient } from '@/app/combo-reports/combo-reports-client'
import { generateComboResearchReport, getLatestResearchRun } from '@/lib/research/api'

const mockGenerate = vi.mocked(generateComboResearchReport)
const mockLatestResearch = vi.mocked(getLatestResearchRun)

describe('ComboReportsClient', () => {
  beforeEach(() => {
    push.mockReset()
    mockGenerate.mockReset()
    mockLatestResearch.mockReset()
  })

  it('renders latest combo report summary with detail link', async () => {
    mockLatestResearch.mockResolvedValue({
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
    })

    render(<ComboReportsClient />)

    await waitFor(() => expect(mockLatestResearch).toHaveBeenCalled())
    expect(screen.getByText('二串一测试报告')).toBeInTheDocument()
    expect(screen.getByText(/最佳策略：frequency_selector/)).toBeInTheDocument()
    expect(screen.getByText('49.72%')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看明细报告' })).toHaveAttribute(
      'href',
      '/combo-reports/5'
    )
    expect(screen.getByRole('link', { name: '返回历史回测' })).toHaveAttribute(
      'href',
      '/backtest'
    )
  })

  it('renders empty state when there is no report', async () => {
    mockLatestResearch.mockResolvedValue(null)

    render(<ComboReportsClient />)

    await waitFor(() => expect(mockLatestResearch).toHaveBeenCalled())
    expect(screen.getByText('暂无研究报告。')).toBeInTheDocument()
  })

  it('generates a report and redirects to detail page', async () => {
    mockLatestResearch.mockResolvedValue(null)
    mockGenerate.mockResolvedValue({
      run_id: 10,
      report_path: 'docs/analysis/generated/x.md',
      score_summary: {
        rows: 10,
        candidates: 4,
        portfolio: 4,
        scored_matches: 4,
        recommended_scores: 4,
        draw_scores: 3,
        handicap_draw_scores: 1,
        replaced_old_scores: 0
      },
      research_summary: { best_strategy: 'frequency_selector' }
    })

    render(<ComboReportsClient />)

    await waitFor(() => expect(mockLatestResearch).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('开始日期'), { target: { value: '2026-01-01' } })
    fireEvent.change(screen.getByLabelText('结束日期'), { target: { value: '2026-01-31' } })
    fireEvent.click(screen.getByRole('button', { name: '生成报告' }))

    await waitFor(() => expect(mockGenerate).toHaveBeenCalled())
    expect(mockGenerate).toHaveBeenCalledWith(
      expect.objectContaining({
        date_from: '2026-01-01',
        date_to: '2026-01-31',
        model_name: 'empirical-v32-filtered-candidate'
      })
    )
    expect(push).toHaveBeenCalledWith('/combo-reports/10')
  })
})
