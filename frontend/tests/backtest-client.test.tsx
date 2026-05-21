import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
  Pie: () => null,
  Cell: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  CartesianGrid: () => null
}))

vi.mock('@/lib/backtest/api', () => ({
  createBacktest: vi.fn(),
  listBacktests: vi.fn(),
  getBacktest: vi.fn(),
  compareBacktests: vi.fn(),
  deleteBacktest: vi.fn()
}))

vi.mock('@/lib/model-config/api', () => ({
  listModelConfigs: vi.fn()
}))

vi.mock('@/lib/research/api', () => ({
  getLatestResearchRun: vi.fn()
}))

import { BacktestClient } from '@/app/backtest/backtest-client'
import {
  compareBacktests,
  createBacktest,
  deleteBacktest,
  getBacktest,
  listBacktests
} from '@/lib/backtest/api'
import type { BacktestSummary as BacktestSummaryData } from '@/lib/backtest/types'
import { listModelConfigs } from '@/lib/model-config/api'
import { getLatestResearchRun } from '@/lib/research/api'

const mockCreate = vi.mocked(createBacktest)
const mockList = vi.mocked(listBacktests)
const mockGet = vi.mocked(getBacktest)
const mockCompare = vi.mocked(compareBacktests)
const mockDelete = vi.mocked(deleteBacktest)
const mockListConfigs = vi.mocked(listModelConfigs)
const mockLatestResearch = vi.mocked(getLatestResearchRun)

function summary(overrides: Partial<BacktestSummaryData> = {}): BacktestSummaryData {
  return {
    id: 1,
    model_config_id: 1,
    date_from: '2026-04-01',
    date_to: '2026-04-30',
    total_bets: 10,
    hit_count: 6,
    hit_rate: 0.6,
    roi: 0.18,
    profit_loss: 180,
    kelly_profit_loss: 150,
    kelly_roi: 0.015,
    mode: 'both',
    initial_capital: 10000,
    fixed_stake: 100,
    bets_detail: null,
    results_by_score: {
      '78-84': {
        bets: 3,
        hits: 2,
        hit_rate: 0.66,
        profit_loss_fixed: 2,
        profit_loss_kelly: 20,
        roi_fixed: 0.1,
        roi_kelly: 0.02
      }
    },
    results_by_league: null,
    equity_curve: [{ date: '2026-04-01', cumulative_pnl_fixed: 2, cumulative_pnl_kelly: 20 }],
    created_at: null,
    ...overrides
  }
}

describe('BacktestClient', () => {
  beforeEach(() => {
    mockCreate.mockReset()
    mockList.mockReset()
    mockGet.mockReset()
    mockCompare.mockReset()
    mockDelete.mockReset()
    mockDelete.mockResolvedValue(undefined)
    mockListConfigs.mockReset()
    mockLatestResearch.mockReset()
    mockLatestResearch.mockResolvedValue(null)
    mockListConfigs.mockResolvedValue({
      items: [
        {
          id: 5,
          name: 'empirical-v32-filtered-candidate',
          created_by: null,
          parent_id: null,
          is_active: true,
          weights_json: {
            euro: 25,
            asian: 20,
            goals: 20,
            intent: 15,
            compression: 20,
            team_stats: 20
          },
          thresholds_json: {},
          kelly_bands_json: {},
          scrape_schedule_json: null,
          created_at: '2026-04-24T00:00:00',
          updated_at: '2026-04-24T00:00:00'
        },
        {
          id: 1,
          name: 'default',
          created_by: null,
          parent_id: null,
          is_active: false,
          weights_json: {
            euro: 25,
            asian: 20,
            goals: 20,
            intent: 15,
            compression: 20,
            team_stats: 20
          },
          thresholds_json: {},
          kelly_bands_json: {},
          scrape_schedule_json: null,
          created_at: '2026-04-24T00:00:00',
          updated_at: '2026-04-24T00:00:00'
        }
      ],
      total: 2
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })



  it('keeps combo reports out of the backtest page', async () => {
    mockList.mockResolvedValue({ items: [], total: 0 })
    mockLatestResearch.mockResolvedValue({
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
    })
    render(<BacktestClient />)
    await waitFor(() => expect(mockList).toHaveBeenCalled())
    expect(mockLatestResearch).not.toHaveBeenCalled()
    expect(screen.queryByText('研究报告')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看二串一测试报告' })).toHaveAttribute(
      'href',
      '/combo-reports'
    )
  })

  it('loads history on mount and lists items', async () => {
    mockList.mockResolvedValue({ items: [summary({ id: 7 })], total: 1 })
    render(<BacktestClient />)
    await waitFor(() => expect(mockList).toHaveBeenCalled())
    expect(screen.getByText(/#7/)).toBeInTheDocument()
  })

  it('submit form creates backtest and shows summary', async () => {
    mockList.mockResolvedValue({ items: [], total: 0 })
    mockCreate.mockResolvedValue(summary({ id: 11 }))

    render(<BacktestClient />)
    await waitFor(() => expect(mockList).toHaveBeenCalled())

    fireEvent.click(screen.getByText('开始回测'))
    await waitFor(() => expect(mockCreate).toHaveBeenCalled())
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ model_config_id: 5 })
    )
    await waitFor(() => expect(screen.getByText(/#11/)).toBeInTheDocument())
  })

  it('lists model name and created time in history', async () => {
    mockList.mockResolvedValue({
      items: [summary({ id: 7, model_config_id: 5, created_at: '2026-04-24T13:53:00' })],
      total: 1
    })
    render(<BacktestClient />)
    await waitFor(() => expect(mockList).toHaveBeenCalled())
    expect(screen.getByText(/模型：empirical-v32-filtered-candidate/)).toBeInTheDocument()
    expect(screen.getByText(/回测时间：2026-04-24 13:53/)).toBeInTheDocument()
    expect(screen.getByText('固定+Kelly')).toBeInTheDocument()
  })

  it('deletes a history item after confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValueOnce(true)
    mockList.mockResolvedValue({ items: [summary({ id: 7 })], total: 1 })
    render(<BacktestClient />)
    await waitFor(() => expect(mockList).toHaveBeenCalled())

    fireEvent.click(screen.getByText('删除'))

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith(7))
    expect(screen.queryByText(/#7/)).not.toBeInTheDocument()
  })

  it('clears compare state after submitting a new backtest', async () => {
    const a = summary({ id: 1 })
    const b = summary({ id: 2 })
    const fresh = summary({ id: 99 })
    mockList.mockResolvedValue({ items: [a, b], total: 2 })
    mockGet.mockImplementation(async (id) => (id === 1 ? a : b))
    mockCompare.mockResolvedValue({ a, b })
    mockCreate.mockResolvedValue(fresh)

    render(<BacktestClient />)
    await waitFor(() => expect(mockList).toHaveBeenCalled())

    const addButtons = screen.getAllByText('加入对比')
    fireEvent.click(addButtons[0])
    fireEvent.click(addButtons[1])
    fireEvent.click(screen.getByText('开始对比'))
    await waitFor(() => expect(screen.getByText('A：#1')).toBeInTheDocument())

    fireEvent.click(screen.getByText('开始回测'))
    await waitFor(() => expect(mockCreate).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByText(/#99/)).toBeInTheDocument())

    expect(screen.queryByText('A：#1')).not.toBeInTheDocument()
    expect(screen.getAllByText('待选择')).toHaveLength(2)
  })

  it('ignores stale getBacktest response when a newer pick arrives', async () => {
    const a = summary({ id: 1 })
    const b = summary({ id: 2 })
    mockList.mockResolvedValue({ items: [a, b], total: 2 })

    let resolveFirst: (v: BacktestSummaryData) => void = () => {}
    const firstPromise = new Promise<BacktestSummaryData>((res) => {
      resolveFirst = res
    })
    mockGet.mockImplementationOnce(() => firstPromise).mockImplementationOnce(async () => b)

    render(<BacktestClient />)
    await waitFor(() => expect(mockList).toHaveBeenCalled())

    fireEvent.click(screen.getByText(/#1/))
    fireEvent.click(screen.getByText(/#2/))
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.getByText(/回测概览/)).toBeInTheDocument())
    expect(screen.getAllByText('#2')).toHaveLength(2)
    expect(screen.getAllByText('#1')).toHaveLength(1)

    resolveFirst(a)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getAllByText('#2')).toHaveLength(2)
    expect(screen.getAllByText('#1')).toHaveLength(1)
  })

  it('compare tray loads comparison after choosing two sessions', async () => {
    const a = summary({ id: 1 })
    const b = summary({ id: 2 })
    mockList.mockResolvedValue({ items: [a, b], total: 2 })
    mockCompare.mockResolvedValue({ a, b })

    render(<BacktestClient />)
    await waitFor(() => expect(mockList).toHaveBeenCalled())

    const addButtons = screen.getAllByText('加入对比')
    fireEvent.click(addButtons[0])
    fireEvent.click(addButtons[1])
    fireEvent.click(screen.getByText('开始对比'))

    await waitFor(() => expect(mockCompare).toHaveBeenCalledWith(1, 2))
    expect(screen.getByText('A：#1')).toBeInTheDocument()
    expect(screen.getByText('B：#2')).toBeInTheDocument()
  })
})
