import { create } from 'zustand'

import { clearAuth, getStoredToken, getStoredUser, persistAuth } from './storage'
import type { AuthUser } from './types'

interface AuthState {
  token: string | null
  user: AuthUser | null
  hasHydrated: boolean
  setAuth: (token: string, user: AuthUser) => void
  clear: () => void
  hydrate: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  hasHydrated: false,
  setAuth: (token, user) => {
    persistAuth(token, user)
    set({ token, user, hasHydrated: true })
  },
  clear: () => {
    clearAuth()
    set({ token: null, user: null, hasHydrated: true })
  },
  hydrate: () => {
    const token = getStoredToken()
    const user = getStoredUser()
    set({ token, user, hasHydrated: true })
  }
}))
