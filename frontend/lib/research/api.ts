import { apiFetch } from '@/lib/auth/api'

import type {
  GenerateComboResearchPayload,
  GenerateComboResearchResponse,
  ResearchRun,
  ResearchRunDetail,
  ResearchTicket,
  ResearchTicketGroup
} from './types'

export async function getLatestResearchRun(): Promise<ResearchRun | null> {
  return apiFetch<ResearchRun | null>('/api/research/latest')
}

export async function getResearchRun(runId: number): Promise<ResearchRunDetail> {
  return apiFetch<ResearchRunDetail>(`/api/research/${runId}`)
}

export async function getResearchTickets(
  runId: number,
  strategy?: string
): Promise<ResearchTicket[]> {
  const query = strategy ? `?strategy=${encodeURIComponent(strategy)}` : ''
  return apiFetch<ResearchTicket[]>(`/api/research/${runId}/tickets${query}`)
}

export async function getResearchTicketGroups(runId: number): Promise<ResearchTicketGroup[]> {
  return apiFetch<ResearchTicketGroup[]>(`/api/research/${runId}/ticket-groups`)
}

export async function generateComboResearchReport(
  payload: GenerateComboResearchPayload
): Promise<GenerateComboResearchResponse> {
  return apiFetch<GenerateComboResearchResponse>('/api/research/generate-combo-report', {
    method: 'POST',
    body: payload
  })
}
