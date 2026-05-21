import { describe, expect, it, vi } from 'vitest'

vi.mock('next/server', () => {
  class NextResponse {
    static next() {
      return { type: 'next' }
    }
    static redirect(url: URL) {
      return { type: 'redirect', url: url.toString() }
    }
  }
  return { NextResponse }
})

import { middleware } from '@/middleware'

type MinimalReq = {
  nextUrl: { pathname: string; search: string }
  url: string
  cookies: { get: (name: string) => { value: string } | undefined }
}

function buildReq(pathname: string, token?: string, search = ''): MinimalReq {
  return {
    nextUrl: { pathname, search },
    url: `http://localhost:3000${pathname}${search}`,
    cookies: {
      get: (name: string) => (token && name === 'sporttery_token' ? { value: token } : undefined)
    }
  }
}

describe('middleware', () => {
  it('redirects unauthenticated users to /login with redirect param', () => {
    const res = middleware(buildReq('/dashboard') as never) as { type: string; url?: string }
    expect(res.type).toBe('redirect')
    expect(res.url).toContain('/login')
    expect(res.url).toContain('redirect=%2Fdashboard')
  })

  it('allows authenticated users through', () => {
    const res = middleware(buildReq('/dashboard', 'tk') as never) as { type: string }
    expect(res.type).toBe('next')
  })

  it('allows /login for unauthenticated users', () => {
    const res = middleware(buildReq('/login') as never) as { type: string }
    expect(res.type).toBe('next')
  })

  it('allows /login even when a stale token cookie exists', () => {
    const res = middleware(buildReq('/login', 'tk') as never) as { type: string }
    expect(res.type).toBe('next')
  })
})
