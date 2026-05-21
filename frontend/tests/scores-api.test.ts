import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { persistAuth } from '@/lib/auth/storage'
import {
  computeScores,
  getScoreBreakdown,
  getScoresByDate,
  getTodayScores,
  updateScore
} from '@/lib/scores/api'

type FetchMock = ReturnType<typeof vi.fn<typeof fetch>>

function mockFetchJson(status: number, jsonBody: unknown): FetchMock {
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

describe('scores api', () => {
  beforeEach(() => {
    window.localStorage.clear()
    persistAuth('tk', { id: 1, phone: '13800138000', name: 'a', role: 'admin' })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('getTodayScores returns list', async () => {
    const payload = { items: [], total: 0 }
    mockFetchJson(200, payload)
    await expect(getTodayScores()).resolves.toEqual(payload)
  })

  it('getScoresByDate sends date and model_config_id', async () => {
    const fetchMock = mockFetchJson(200, { items: [], total: 0 })
    await getScoresByDate('2026-05-01', 7)
    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('date=2026-05-01')
    expect(url).toContain('model_config_id=7')
  })

  it('computeScores POSTs with date', async () => {
    const fetchMock = mockFetchJson(200, {
      date: '2026-05-01',
      model_config_id: 1,
      computed: 3,
      skipped: 0
    })
    await computeScores('2026-05-01')
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(String(fetchMock.mock.calls[0][0])).toContain('date=2026-05-01')
  })

  it('getScoreBreakdown reads breakdown', async () => {
    mockFetchJson(200, { score: {}, parts: [] })
    await getScoreBreakdown(42)
  })

  it('updateScore PUTs the payload', async () => {
    const fetchMock = mockFetchJson(200, { id: 1 })
    await updateScore(1, { notes: 'x', bet_amount: 100, actual_hit: true })
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('PUT')
    const body = JSON.parse(init.body as string) as Record<string, unknown>
    expect(body.notes).toBe('x')
    expect(body.bet_amount).toBe(100)
    expect(body.actual_hit).toBe(true)
  })
})
