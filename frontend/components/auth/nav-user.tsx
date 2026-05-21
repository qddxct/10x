'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { logoutApi } from '@/lib/auth/api'
import { useAuthStore } from '@/lib/auth/store'

export function NavUser() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const clear = useAuthStore((s) => s.clear)
  const [isLoading, setIsLoading] = useState(false)

  if (!user) return null

  async function handleLogout() {
    setIsLoading(true)
    try {
      await logoutApi()
    } catch (err) {
      console.warn('logout api failed', err)
    } finally {
      clear()
      setIsLoading(false)
      router.replace('/login')
    }
  }

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-muted-foreground">
        {user.name} · {user.role === 'admin' ? '管理员' : '成员'}
      </span>
      <Button
        variant="outline"
        size="sm"
        onClick={handleLogout}
        disabled={isLoading}
        aria-label="退出登录"
      >
        {isLoading ? '退出中…' : '退出'}
      </Button>
    </div>
  )
}
