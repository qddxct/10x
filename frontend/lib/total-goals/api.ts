import { apiFetch } from '@/lib/auth/api'

import type {
  TotalGoalComboHistoryResponse,
  TotalGoalComboSnapshotResult,
  TotalGoalComputeResult,
  TotalGoalListResponse,
  TotalGoalTodayResponse
} from './types'

export async function getTodayTotalGoals(): Promise<TotalGoalTodayResponse> {
  return apiFetch<TotalGoalTodayResponse>('/api/total-goals/today')
}

export async function snapshotTodayTotalGoalCombos(): Promise<TotalGoalComboSnapshotResult> {
  return apiFetch<TotalGoalComboSnapshotResult>('/api/total-goals/snapshot-today', {
    method: 'POST'
  })
}

export async function listTotalGoalComboHistory(limit = 50): Promise<TotalGoalComboHistoryResponse> {
  return apiFetch<TotalGoalComboHistoryResponse>(`/api/total-goals/history?limit=${limit}`)
}

export async function getTotalGoalsByDate(date: string): Promise<TotalGoalListResponse> {
  return apiFetch<TotalGoalListResponse>(`/api/total-goals/by-date?date=${date}`)
}

export async function computeTotalGoals(date: string): Promise<TotalGoalComputeResult> {
  return apiFetch<TotalGoalComputeResult>(`/api/total-goals/compute?date=${date}`, {
    method: 'POST'
  })
}

export async function computeUpcomingTotalGoals(days = 7): Promise<TotalGoalComputeResult> {
  return apiFetch<TotalGoalComputeResult>(`/api/total-goals/compute-upcoming?days=${days}`, {
    method: 'POST'
  })
}
