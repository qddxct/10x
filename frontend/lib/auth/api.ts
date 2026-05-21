import { getStoredToken } from './storage'
import type { LoginRequest, TokenResponse } from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown, message?: string) {
    super(message || `API error ${status}`)
    this.status = status
    this.detail = detail
  }
}

export interface ApiFetchOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  authenticated?: boolean
  token?: string | null
}

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const { body, authenticated = true, token, headers, ...rest } = options
  const finalHeaders = new Headers(headers)

  if (body !== undefined && !finalHeaders.has('Content-Type')) {
    finalHeaders.set('Content-Type', 'application/json')
  }

  if (authenticated) {
    const authToken = token ?? getStoredToken()
    if (authToken) {
      finalHeaders.set('Authorization', `Bearer ${authToken}`)
    }
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: finalHeaders,
    body: body === undefined ? undefined : JSON.stringify(body)
  })

  if (res.status === 204) {
    return undefined as T
  }

  const contentType = res.headers.get('Content-Type') || ''
  const isJson = contentType.includes('application/json')
  const payload = isJson ? await res.json() : await res.text()

  if (!res.ok) {
    const detailMsg =
      isJson && payload && typeof payload === 'object' && 'detail' in payload
        ? (payload as { detail: unknown }).detail
        : payload
    throw new ApiError(res.status, detailMsg, typeof detailMsg === 'string' ? detailMsg : undefined)
  }

  return payload as T
}

export async function loginApi(payload: LoginRequest): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/api/auth/login', {
    method: 'POST',
    body: payload,
    authenticated: false
  })
}

export async function logoutApi(token?: string): Promise<void> {
  await apiFetch<void>('/api/auth/logout', {
    method: 'POST',
    token
  })
}

export async function fetchMe(token?: string) {
  return apiFetch('/api/auth/me', { token })
}
