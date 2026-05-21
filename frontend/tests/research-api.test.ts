import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { persistAuth } from '@/lib/auth/storage'
import {
  generateComboResearchReport,
  getLatestResearchRun,
  getResearchRun,
  getResearchTicketGroups,
  getResearchTickets
} from '@/lib/research/api'

function mockFetchJson(status: number, jsonBody: unknown) {
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      ({
        ok: status >= 200 && status < 300,
        status,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => jsonBody,
        text: async () => ''
      }) as Response
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('research api', () => {
  beforeEach(() => {
    window.localStorage.clear()
    persistAuth('tk', { id: 1, phone: '13800138000', name: 'a', role: 'admin' })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads latest research run', async () => {
    const fetchMock = mockFetchJson(200, { id: 1, name: 'v33' })
    const res = await getLatestResearchRun()
    expect(res?.id).toBe(1)
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/research/latest')
  })

  it('loads research run detail', async () => {
    const fetchMock = mockFetchJson(200, { id: 6, artifacts: {} })
    const res = await getResearchRun(6)
    expect(res.id).toBe(6)
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/research/6')
  })

  it('loads research tickets with optional strategy', async () => {
    const fetchMock = mockFetchJson(200, [{ strategy: 'frequency_selector' }])
    const res = await getResearchTickets(6, 'frequency_selector')
    expect(res).toHaveLength(1)
    expect(String(fetchMock.mock.calls[0][0])).toContain(
      '/api/research/6/tickets?strategy=frequency_selector'
    )
  })

  it('loads grouped research tickets', async () => {
    const fetchMock = mockFetchJson(200, [{ group_key: 'model:frequency_selector' }])
    const res = await getResearchTicketGroups(6)
    expect(res).toHaveLength(1)
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/research/6/ticket-groups')
  })

  it('generates combo research report', async () => {
    const fetchMock = mockFetchJson(201, {
      run_id: 10,
      report_path: 'docs/analysis/generated/x.md',
      score_summary: { recommended_scores: 4 },
      research_summary: { best_strategy: 'frequency_selector' }
    })
    const res = await generateComboResearchReport({
      date_from: '2026-01-01',
      date_to: '2026-01-31',
      random_trials: 1000,
      random_seed: 20260426
    })
    expect(res.run_id).toBe(10)
    expect(String(fetchMock.mock.calls[0][0])).toContain(
      '/api/research/generate-combo-report'
    )
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })
})
