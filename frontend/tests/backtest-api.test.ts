import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { persistAuth } from '@/lib/auth/storage'
import {
  compareBacktests,
  createBacktest,
  deleteBacktest,
  getBacktest,
  listBacktests
} from '@/lib/backtest/api'

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

describe('backtest api', () => {
  beforeEach(() => {
    window.localStorage.clear()
    persistAuth('tk', { id: 1, phone: '13800138000', name: 'a', role: 'admin' })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('createBacktest POSTs payload', async () => {
    const fetchMock = mockFetchJson(201, { id: 1, total_bets: 0 })
    await createBacktest({
      date_from: '2026-04-01',
      date_to: '2026-04-30',
      mode: 'both',
      initial_capital: 10000
    })
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/backtest')
    const body = JSON.parse(init.body as string)
    expect(body.date_from).toBe('2026-04-01')
    expect(body.mode).toBe('both')
  })

  it('listBacktests passes limit/offset', async () => {
    const fetchMock = mockFetchJson(200, { items: [], total: 0 })
    await listBacktests(10, 5)
    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('limit=10')
    expect(url).toContain('offset=5')
  })

  it('getBacktest returns one session', async () => {
    mockFetchJson(200, { id: 42 })
    const res = await getBacktest(42)
    expect(res.id).toBe(42)
  })

  it('compareBacktests passes a and b', async () => {
    const fetchMock = mockFetchJson(200, { a: { id: 1 }, b: { id: 2 } })
    await compareBacktests(1, 2)
    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('a=1')
    expect(url).toContain('b=2')
  })

  it('deleteBacktest sends DELETE', async () => {
    const fetchMock = mockFetchJson(204, undefined)
    await deleteBacktest(9)
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/backtest/9')
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('DELETE')
  })
})
