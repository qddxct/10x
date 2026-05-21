import { apiFetch } from '@/lib/auth/api'

import type { ReviewFilters, ReviewItem, ReviewListResponse, ReviewUpdatePayload } from './types'

export async function listReviews(filters: ReviewFilters = {}): Promise<ReviewListResponse> {
  const params = new URLSearchParams()
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)
  if (filters.only_recommended) params.set('only_recommended', 'true')
  if (filters.model_config_id != null)
    params.set('model_config_id', String(filters.model_config_id))
  const suffix = params.toString() ? `?${params.toString()}` : ''
  return apiFetch<ReviewListResponse>(`/api/reviews${suffix}`)
}

export async function getReview(scoreId: number): Promise<ReviewItem> {
  return apiFetch<ReviewItem>(`/api/reviews/${scoreId}`)
}

export async function updateReview(
  scoreId: number,
  payload: ReviewUpdatePayload
): Promise<ReviewItem> {
  return apiFetch<ReviewItem>(`/api/reviews/${scoreId}`, {
    method: 'PATCH',
    body: payload
  })
}
