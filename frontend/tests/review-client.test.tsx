import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ReviewClient } from '@/app/review/review-client'
import { useAuthStore } from '@/lib/auth/store'

vi.mock('@/lib/reviews/api', () => ({
  listReviews: vi.fn(),
  getReview: vi.fn(),
  updateReview: vi.fn()
}))

import { listReviews, updateReview } from '@/lib/reviews/api'

const mockList = listReviews as unknown as ReturnType<typeof vi.fn>
const mockUpdate = updateReview as unknown as ReturnType<typeof vi.fn>

function stubAuth(role: 'admin' | 'member') {
  useAuthStore.setState({
    user: { id: 1, email: 't@t', role, created_at: new Date().toISOString() },
    accessToken: 't',
    refreshToken: 'r',
    isHydrated: true
  } as never)
}

function makeItem(overrides: Record<string, unknown> = {}) {
  return {
    score_id: 10,
    match_id: 100,
    match_date: '2026-04-15T12:00:00+00:00',
    league_name: '英超',
    home_team: 'HT',
    away_team: 'AT',
    home_score: 2,
    away_score: 1,
    result: 'H',
    handicap_result: 'H',
    total_score: 73,
    bet_type: 'HOME',
    kelly_pct: '0.05',
    is_recommended: true,
    actual_hit: null,
    suggested_actual_hit: true,
    bet_amount: null,
    notes: null,
    model_config_id: 1,
    user_id: null,
    updated_at: '2026-04-16T00:00:00+00:00',
    ...overrides
  }
}

describe('ReviewClient', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders items and summary', async () => {
    stubAuth('member')
    mockList.mockResolvedValue({
      items: [
        makeItem({ score_id: 1, actual_hit: true, bet_amount: '100' }),
        makeItem({ score_id: 2, actual_hit: false, bet_amount: '50' })
      ],
      total: 2
    })
    render(<ReviewClient />)
    await waitFor(() => expect(screen.getAllByText('HT vs AT').length).toBe(2))
    expect(screen.getByLabelText('复盘汇总')).toBeInTheDocument()
    expect(screen.getByText('¥50.00')).toBeInTheDocument()
  })

  it('member cannot edit', async () => {
    stubAuth('member')
    mockList.mockResolvedValue({ items: [makeItem()], total: 1 })
    render(<ReviewClient />)
    await waitFor(() => expect(screen.getByText('HT vs AT')).toBeInTheDocument())
    const hitSelect = screen.getByLabelText('actual-hit-10') as HTMLSelectElement
    expect(hitSelect.disabled).toBe(true)
  })

  it('admin patches actual_hit via select', async () => {
    stubAuth('admin')
    const item = makeItem()
    mockList.mockResolvedValue({ items: [item], total: 1 })
    mockUpdate.mockResolvedValue({ ...item, actual_hit: true })
    render(<ReviewClient />)
    await waitFor(() => expect(screen.getByText('HT vs AT')).toBeInTheDocument())
    const hitSelect = screen.getByLabelText('actual-hit-10') as HTMLSelectElement
    fireEvent.change(hitSelect, { target: { value: 'hit' } })
    await waitFor(() =>
      expect(mockUpdate).toHaveBeenCalledWith(
        10,
        expect.objectContaining({ actual_hit: true, expected_updated_at: expect.any(String) })
      )
    )
  })

  it('admin patches bet_amount on blur', async () => {
    stubAuth('admin')
    const item = makeItem()
    mockList.mockResolvedValue({ items: [item], total: 1 })
    mockUpdate.mockResolvedValue({ ...item, bet_amount: '88' })
    render(<ReviewClient />)
    await waitFor(() => expect(screen.getByText('HT vs AT')).toBeInTheDocument())
    const input = screen.getByLabelText('bet-amount-10') as HTMLInputElement
    fireEvent.change(input, { target: { value: '88' } })
    fireEvent.blur(input)
    await waitFor(() =>
      expect(mockUpdate).toHaveBeenCalledWith(
        10,
        expect.objectContaining({ bet_amount: 88, expected_updated_at: expect.any(String) })
      )
    )
  })

  it('409 conflict shows message and triggers reload', async () => {
    stubAuth('admin')
    const { ApiError } = await import('@/lib/auth/api')
    const item = makeItem()
    mockList.mockResolvedValue({ items: [item], total: 1 })
    mockUpdate.mockRejectedValueOnce(new ApiError(409, 'conflict'))
    render(<ReviewClient />)
    await waitFor(() => expect(screen.getByText('HT vs AT')).toBeInTheDocument())
    mockList.mockClear()

    const hitSelect = screen.getByLabelText('actual-hit-10') as HTMLSelectElement
    fireEvent.change(hitSelect, { target: { value: 'hit' } })

    await waitFor(() => expect(screen.getByText(/该行已被其他管理员更新/)).toBeInTheDocument())
    await waitFor(() => expect(mockList).toHaveBeenCalled())
  })

  it('only_recommended toggle triggers reload', async () => {
    stubAuth('admin')
    mockList.mockResolvedValue({ items: [], total: 0 })
    render(<ReviewClient />)
    await waitFor(() => expect(mockList).toHaveBeenCalled())
    mockList.mockClear()
    fireEvent.click(screen.getByLabelText('仅推荐'))
    await waitFor(() =>
      expect(mockList).toHaveBeenCalledWith(expect.objectContaining({ only_recommended: true }))
    )
  })
})
