import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/scores/api', () => ({
  getTodayScores: vi.fn(),
  getScoresByDate: vi.fn(),
  computeScores: vi.fn(),
  computeUpcomingScores: vi.fn(),
  getScoreBreakdown: vi.fn(),
  updateScore: vi.fn()
}))

vi.mock('@/lib/model-config/api', () => ({
  listModelConfigs: vi.fn()
}))

vi.mock('@/lib/reviews/api', () => ({
  listReviews: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  getReview: vi.fn(),
  updateReview: vi.fn()
}))

import { DashboardClient } from '@/app/dashboard/dashboard-client'
import { listModelConfigs } from '@/lib/model-config/api'
import {
  computeScores,
  computeUpcomingScores,
  getScoreBreakdown,
  getScoresByDate,
  getTodayScores,
  updateScore
} from '@/lib/scores/api'

const mockToday = vi.mocked(getTodayScores)
const mockByDate = vi.mocked(getScoresByDate)
const mockCompute = vi.mocked(computeScores)
const mockComputeUpcoming = vi.mocked(computeUpcomingScores)
const mockBreakdown = vi.mocked(getScoreBreakdown)
const mockUpdate = vi.mocked(updateScore)
const mockListConfigs = vi.mocked(listModelConfigs)

function configFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    name: 'default',
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
    created_at: '2026-04-01T00:00:00',
    updated_at: '2026-04-01T00:00:00',
    ...overrides
  }
}

function scoreFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    match_id: 10,
    model_config_id: 1,
    user_id: null,
    euro_score: 20,
    asian_score: 20,
    goals_score: 20,
    intent_score: 5,
    compression_score: 20,
    team_stats_score: 15,
    total_score: 100,
    bet_type: 'draw',
    kelly_pct: 0.015,
    is_recommended: true,
    actual_hit: null,
    bet_amount: null,
    notes: null,
    match_date: '2026-05-01T14:00:00',
    home_team: '阿森纳',
    away_team: '切尔西',
    league_name: '英超',
    match_round: '周五001',
    had_draw_odds: 3.2,
    hhad_draw_odds: 3.55,
    bet_odds: 3.2,
    ...overrides
  }
}

describe('DashboardClient', () => {
  beforeEach(() => {
    mockToday.mockReset()
    mockByDate.mockReset()
    mockCompute.mockReset()
    mockComputeUpcoming.mockReset()
    mockBreakdown.mockReset()
    mockUpdate.mockReset()
    mockListConfigs.mockReset()
    mockListConfigs.mockResolvedValue({
      items: [configFixture() as never],
      total: 1
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders score rows for today', async () => {
    mockToday.mockResolvedValue({ total: 1, items: [scoreFixture() as never] })

    render(<DashboardClient />)

    await waitFor(() => expect(screen.getByText('阿森纳 vs 切尔西')).toBeInTheDocument())
    expect(screen.getAllByText('推荐').length).toBeGreaterThan(0)
    expect(screen.getByText('1.50%')).toBeInTheDocument()
  })

  it('compute button calls api and reloads', async () => {
    mockToday.mockResolvedValue({ total: 0, items: [] })
    mockComputeUpcoming.mockResolvedValue({
      model_config_id: 1,
      dates: ['2026-05-01'],
      computed: 2,
      skipped: 0
    })

    render(<DashboardClient />)
    await waitFor(() => expect(mockToday).toHaveBeenCalled())

    fireEvent.click(screen.getByText('立即计算'))
    await waitFor(() => expect(mockComputeUpcoming).toHaveBeenCalled())
    await waitFor(() => expect(mockToday).toHaveBeenCalledTimes(2))
  })

  it('date picker switches to date-scoped scores', async () => {
    mockToday.mockResolvedValue({ total: 0, items: [] })
    mockByDate.mockResolvedValue({ total: 1, items: [scoreFixture({ match_date: '2026-05-16T02:00:00' }) as never] })

    render(<DashboardClient />)
    await waitFor(() => expect(mockToday).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('选择日期'), {
      target: { value: '2026-05-16' }
    })

    await waitFor(() => expect(mockByDate).toHaveBeenCalledWith('2026-05-16', 1))
    expect(await screen.findByText('阿森纳 vs 切尔西')).toBeInTheDocument()
  })

  it('opens detail drawer and can save updates', async () => {
    const score = scoreFixture() as never
    mockToday.mockResolvedValue({ total: 1, items: [score] })
    mockBreakdown.mockResolvedValue({
      score,
      parts: [
        { dimension: 'euro_score', score: 20, max_score: 25, explanation: '欧赔' },
        { dimension: 'asian_score', score: 20, max_score: 20, explanation: '亚盘' },
        { dimension: 'goals_score', score: 20, max_score: 20, explanation: '进球' },
        { dimension: 'intent_score', score: 5, max_score: 15, explanation: '战意' },
        { dimension: 'compression_score', score: 20, max_score: 20, explanation: '压缩' },
        { dimension: 'team_stats_score', score: 15, max_score: 20, explanation: '球队' }
      ]
    })
    mockUpdate.mockResolvedValue({ ...(score as Record<string, unknown>), notes: 'hi' } as never)

    render(<DashboardClient />)
    await waitFor(() => screen.getByText('阿森纳 vs 切尔西'))

    fireEvent.click(screen.getByText('阿森纳 vs 切尔西'))
    await waitFor(() => expect(mockBreakdown).toHaveBeenCalledWith(1))

    expect(screen.getByText('euro_score')).toBeInTheDocument()

    const textarea = screen.getByPlaceholderText('记录本场分析')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.click(screen.getByText('保存'))

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled())
    expect(mockUpdate.mock.calls[0][1].notes).toBe('hi')
  })

  it('displays active model name in header', async () => {
    mockToday.mockResolvedValue({ total: 0, items: [] })
    mockListConfigs.mockResolvedValue({
      items: [configFixture({ id: 9, name: 'v2', is_active: true }) as never],
      total: 1
    })

    render(<DashboardClient />)
    await waitFor(() => expect(screen.getByTestId('active-config-name')).toHaveTextContent('v2'))
  })

  it('switching model dropdown passes model_config_id to scores api', async () => {
    mockToday.mockResolvedValue({ total: 0, items: [] })
    mockListConfigs.mockResolvedValue({
      items: [
        configFixture({ id: 1, name: 'default', is_active: true }) as never,
        configFixture({ id: 2, name: 'challenger', is_active: false }) as never
      ],
      total: 2
    })

    render(<DashboardClient />)
    await waitFor(() => expect(mockListConfigs).toHaveBeenCalled())
    await waitFor(() => expect(mockToday).toHaveBeenCalledWith(1))

    fireEvent.change(screen.getByLabelText('切换评分模型'), {
      target: { value: '2' }
    })

    await waitFor(() => expect(mockToday).toHaveBeenCalledWith(2))
  })

  it('switches to finished tab and shows review panel', async () => {
    mockToday.mockResolvedValue({ total: 0, items: [] })
    render(<DashboardClient />)
    await waitFor(() => expect(mockToday).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('tab', { name: '已结束 · 复盘' }))
    await waitFor(() => expect(screen.getByLabelText('复盘汇总')).toBeInTheDocument())
  })
})
