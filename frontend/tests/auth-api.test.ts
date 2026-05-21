import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch, ApiError, loginApi, logoutApi } from '@/lib/auth/api'
import { persistAuth } from '@/lib/auth/storage'

type FetchMock = ReturnType<typeof vi.fn<typeof fetch>>

function mockFetch(
  response: Partial<Response> & { jsonBody?: unknown; textBody?: string }
): FetchMock {
  const status = response.status ?? 200
  const ct =
    response.headers instanceof Headers
      ? response.headers
      : new Headers({
          'Content-Type': response.jsonBody !== undefined ? 'application/json' : 'text/plain'
        })
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      ({
        ok: status >= 200 && status < 300,
        status,
        headers: ct,
        json: async () => response.jsonBody,
        text: async () => response.textBody ?? ''
      }) as Response
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('apiFetch', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('serializes JSON body and sets content-type', async () => {
    const fetchMock = mockFetch({ status: 200, jsonBody: { ok: true } })
    const data = await apiFetch<{ ok: boolean }>('/api/auth/login', {
      method: 'POST',
      body: { phone: '13800138000', password: 'x' },
      authenticated: false
    })
    expect(data).toEqual({ ok: true })
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    const hdrs = new Headers(init.headers)
    expect(hdrs.get('Content-Type')).toBe('application/json')
    expect(hdrs.has('Authorization')).toBe(false)
    expect(init.body).toBe('{"phone":"13800138000","password":"x"}')
  })

  it('attaches Authorization header from local storage', async () => {
    persistAuth('tk-123', { id: 1, phone: '13800138000', name: 'a', role: 'admin' })
    const fetchMock = mockFetch({ status: 200, jsonBody: { id: 1 } })
    await apiFetch('/api/auth/me')
    const init = fetchMock.mock.calls[0][1] as RequestInit
    const hdrs = new Headers(init.headers)
    expect(hdrs.get('Authorization')).toBe('Bearer tk-123')
  })

  it('throws ApiError on 4xx with detail string', async () => {
    mockFetch({ status: 401, jsonBody: { detail: 'Invalid phone or password' } })
    await expect(loginApi({ phone: '13800138000', password: 'x' })).rejects.toMatchObject({
      status: 401,
      message: 'Invalid phone or password'
    })
    await expect(loginApi({ phone: '13800138000', password: 'x' })).rejects.toBeInstanceOf(ApiError)
  })

  it('logout returns undefined on 204', async () => {
    const fetchMock = vi.fn(
      async () =>
        ({
          ok: true,
          status: 204,
          headers: new Headers(),
          json: async () => undefined,
          text: async () => ''
        }) as Response
    )
    vi.stubGlobal('fetch', fetchMock)
    await expect(logoutApi('tk')).resolves.toBeUndefined()
  })
})
