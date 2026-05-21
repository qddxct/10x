import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { persistAuth } from '@/lib/auth/storage'
import { listScrapeJobs, listScrapeLogs, runScrapeJob } from '@/lib/scrape/api'

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

describe('scrape api', () => {
  beforeEach(() => {
    window.localStorage.clear()
    persistAuth('tk-admin', { id: 1, phone: '13800138000', name: 'a', role: 'admin' })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listScrapeJobs returns job list', async () => {
    const jobs = [{ name: 'schedule', description: '赛程' }]
    mockFetchJson(200, jobs)
    await expect(listScrapeJobs()).resolves.toEqual(jobs)
  })

  it('listScrapeLogs forwards filters as query params', async () => {
    const fetchMock = mockFetchJson(200, { items: [], total: 0 })
    await listScrapeLogs({ status: 'failed', limit: 10, offset: 5 })
    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('status=failed')
    expect(url).toContain('limit=10')
    expect(url).toContain('offset=5')
  })

  it('runScrapeJob POSTs to run endpoint', async () => {
    const fetchMock = mockFetchJson(200, {
      job: 'schedule',
      status: 'success',
      records: 3,
      error: null
    })
    const result = await runScrapeJob('schedule')
    expect(result.status).toBe('success')
    expect(result.records).toBe(3)
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/scrape/jobs/schedule/run')
  })
})
