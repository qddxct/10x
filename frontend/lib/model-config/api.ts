import { ApiError, apiFetch } from '@/lib/auth/api'

import type {
  ModelConfig,
  ModelConfigActivateResponse,
  ModelConfigCreatePayload,
  ModelConfigListResponse,
  ModelConfigUpdatePayload
} from './types'

export async function listModelConfigs(): Promise<ModelConfigListResponse> {
  return apiFetch<ModelConfigListResponse>('/api/model-configs')
}

export async function getActiveModelConfig(): Promise<ModelConfig | null> {
  try {
    return await apiFetch<ModelConfig>('/api/model-configs/active')
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

export async function getModelConfig(id: number): Promise<ModelConfig> {
  return apiFetch<ModelConfig>(`/api/model-configs/${id}`)
}

export async function createModelConfig(payload: ModelConfigCreatePayload): Promise<ModelConfig> {
  return apiFetch<ModelConfig>('/api/model-configs', {
    method: 'POST',
    body: payload
  })
}

export async function updateModelConfig(
  id: number,
  payload: ModelConfigUpdatePayload
): Promise<ModelConfig> {
  return apiFetch<ModelConfig>(`/api/model-configs/${id}`, {
    method: 'PATCH',
    body: payload
  })
}

export async function cloneModelConfig(id: number, name: string): Promise<ModelConfig> {
  return apiFetch<ModelConfig>(`/api/model-configs/${id}/clone`, {
    method: 'POST',
    body: { name }
  })
}

export async function activateModelConfig(id: number): Promise<ModelConfigActivateResponse> {
  return apiFetch<ModelConfigActivateResponse>(`/api/model-configs/${id}/activate`, {
    method: 'POST'
  })
}
