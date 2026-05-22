import { apiFetch } from '@/lib/auth/api'

import type { ComboRecommendationListResponse, ComboSnapshotResult } from './types'

export async function snapshotTodayCombos(modelConfigId?: number): Promise<ComboSnapshotResult> {
  const suffix = modelConfigId != null ? `?model_config_id=${modelConfigId}` : ''
  return apiFetch<ComboSnapshotResult>(`/api/combo-recommendations/snapshot-today${suffix}`, {
    method: 'POST'
  })
}

export async function listComboRecommendationHistory(
  modelConfigId?: number,
  limit = 50
): Promise<ComboRecommendationListResponse> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (modelConfigId != null) params.set('model_config_id', String(modelConfigId))
  return apiFetch<ComboRecommendationListResponse>(
    `/api/combo-recommendations/history?${params.toString()}`
  )
}
