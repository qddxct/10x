import type { AuthUser } from './types'

const TOKEN_KEY = 'sporttery_token'
const USER_KEY = 'sporttery_user'
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30

function hasWindow(): boolean {
  return typeof window !== 'undefined'
}

function setTokenCookie(token: string): void {
  document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`
}

function clearTokenCookie(): void {
  document.cookie = `${TOKEN_KEY}=; path=/; max-age=0; SameSite=Lax`
}

export function getStoredToken(): string | null {
  if (!hasWindow()) return null
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch (err) {
    console.warn('getStoredToken failed', err)
    return null
  }
}

export function getStoredUser(): AuthUser | null {
  if (!hasWindow()) return null
  try {
    const raw = window.localStorage.getItem(USER_KEY)
    if (!raw) return null
    return JSON.parse(raw) as AuthUser
  } catch (err) {
    console.warn('getStoredUser failed', err)
    return null
  }
}

export function persistAuth(token: string, user: AuthUser): void {
  if (!hasWindow()) return
  try {
    window.localStorage.setItem(TOKEN_KEY, token)
    window.localStorage.setItem(USER_KEY, JSON.stringify(user))
    setTokenCookie(token)
  } catch (err) {
    console.warn('persistAuth failed', err)
  }
}

export function clearAuth(): void {
  if (!hasWindow()) return
  try {
    window.localStorage.removeItem(TOKEN_KEY)
    window.localStorage.removeItem(USER_KEY)
    clearTokenCookie()
  } catch (err) {
    console.warn('clearAuth failed', err)
  }
}
