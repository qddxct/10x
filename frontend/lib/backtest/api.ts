import { apiFetch } from '@/lib/auth/api'

import type {
  BacktestCompareResponse,
  BacktestCreatePayload,
  BacktestListResponse,
  BacktestSummary
} from './types'

export async function createBacktest(payload: BacktestCreatePayload): Promise<BacktestSummary> {
  return apiFetch<BacktestSummary>('/api/backtest', {
    method: 'POST',
    body: payload
  })
}

export async function listBacktests(limit = 20, offset = 0): Promise<BacktestListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  return apiFetch<BacktestListResponse>(`/api/backtest?${params.toString()}`)
}

export async function getBacktest(id: number): Promise<BacktestSummary> {
  return apiFetch<BacktestSummary>(`/api/backtest/${id}`)
}

export async function deleteBacktest(id: number): Promise<void> {
  return apiFetch<void>(`/api/backtest/${id}`, {
    method: 'DELETE'
  })
}

export async function compareBacktests(a: number, b: number): Promise<BacktestCompareResponse> {
  const params = new URLSearchParams({ a: String(a), b: String(b) })
  return apiFetch<BacktestCompareResponse>(`/api/backtest/compare?${params.toString()}`)
}
