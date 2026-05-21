import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/model-config/api', () => ({
  listModelConfigs: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  getModelConfig: vi.fn(),
  createModelConfig: vi.fn(),
  updateModelConfig: vi.fn(),
  cloneModelConfig: vi.fn(),
  activateModelConfig: vi.fn()
}))

vi.mock('@/lib/reviews/api', () => ({
  listReviews: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  getReview: vi.fn(),
  updateReview: vi.fn()
}))

import { ModelClient } from '@/app/model/model-client'
import { ReviewClient } from '@/app/review/review-client'
import { useAuthStore } from '@/lib/auth/store'

describe('P7 routes smoke', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: { id: 1, phone: '1', name: 'u', role: 'admin' } as never,
      accessToken: 't',
      refreshToken: 'r',
      isHydrated: true
    } as never)
  })

  it('/model renders without crash', async () => {
    render(<ModelClient />)
    await waitFor(() => expect(screen.getByText('版本列表')).toBeInTheDocument())
  })

  it('/review renders without crash', async () => {
    render(<ReviewClient />)
    await waitFor(() => expect(screen.getByText('复盘')).toBeInTheDocument())
  })
})
