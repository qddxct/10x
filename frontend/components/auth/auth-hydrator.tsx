'use client'

import { useEffect } from 'react'

import { useAuthStore } from '@/lib/auth/store'

export function AuthHydrator() {
  const hydrate = useAuthStore((s) => s.hydrate)
  useEffect(() => {
    hydrate()
  }, [hydrate])
  return null
}
