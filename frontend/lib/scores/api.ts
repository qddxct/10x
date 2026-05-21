import { apiFetch } from '@/lib/auth/api'

import type {
  ScoreBreakdown,
  ScoreComputeResult,
  ScoreComputeUpcomingResult,
  ScoreListResponse,
  ScoreUpdatePayload,
  Score
} from './types'

export async function getTodayScores(modelConfigId?: number): Promise<ScoreListResponse> {
  const suffix = modelConfigId != null ? `?model_config_id=${modelConfigId}` : ''
  return apiFetch<ScoreListResponse>(`/api/scores/today${suffix}`)
}

export async function getScoresByDate(
  date: string,
  modelConfigId?: number
): Promise<ScoreListResponse> {
  const params = new URLSearchParams({ date })
  if (modelConfigId != null) params.set('model_config_id', String(modelConfigId))
  return apiFetch<ScoreListResponse>(`/api/scores/by-date?${params.toString()}`)
}

export async function computeScores(
  date?: string,
  modelConfigId?: number
): Promise<ScoreComputeResult> {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  if (modelConfigId != null) params.set('model_config_id', String(modelConfigId))
  const suffix = params.toString() ? `?${params.toString()}` : ''
  return apiFetch<ScoreComputeResult>(`/api/scores/compute${suffix}`, { method: 'POST' })
}

export async function computeUpcomingScores(
  modelConfigId?: number,
  days = 7
): Promise<ScoreComputeUpcomingResult> {
  const params = new URLSearchParams({ days: String(days) })
  if (modelConfigId != null) params.set('model_config_id', String(modelConfigId))
  return apiFetch<ScoreComputeUpcomingResult>(`/api/scores/compute-upcoming?${params.toString()}`, {
    method: 'POST'
  })
}

export async function getScoreBreakdown(scoreId: number): Promise<ScoreBreakdown> {
  return apiFetch<ScoreBreakdown>(`/api/scores/${scoreId}/breakdown`)
}

export async function updateScore(scoreId: number, payload: ScoreUpdatePayload): Promise<Score> {
  return apiFetch<Score>(`/api/scores/${scoreId}`, {
    method: 'PUT',
    body: payload
  })
}
