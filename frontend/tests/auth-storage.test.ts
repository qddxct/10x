import { beforeEach, describe, expect, it } from 'vitest'

import { clearAuth, getStoredToken, getStoredUser, persistAuth } from '@/lib/auth/storage'

describe('auth storage', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('returns null when nothing stored', () => {
    expect(getStoredToken()).toBeNull()
    expect(getStoredUser()).toBeNull()
  })

  it('persists token and user', () => {
    persistAuth('tk-1', { id: 1, phone: '13800138000', name: 'u', role: 'admin' })
    expect(getStoredToken()).toBe('tk-1')
    expect(getStoredUser()).toEqual({
      id: 1,
      phone: '13800138000',
      name: 'u',
      role: 'admin'
    })
  })

  it('clears auth', () => {
    persistAuth('tk', { id: 2, phone: '13800138001', name: 'x', role: 'member' })
    clearAuth()
    expect(getStoredToken()).toBeNull()
    expect(getStoredUser()).toBeNull()
  })

  it('returns null when user json is corrupted', () => {
    window.localStorage.setItem('sporttery_user', 'not-json{')
    expect(getStoredUser()).toBeNull()
  })
})
