'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, loginApi } from '@/lib/auth/api'
import { useAuthStore } from '@/lib/auth/store'

const PHONE_RE = /^1[3-9]\d{9}$/

export function LoginForm() {
  const router = useRouter()
  const params = useSearchParams()
  const redirectTo = params.get('redirect') || '/'
  const setAuth = useAuthStore((s) => s.setAuth)

  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    if (!PHONE_RE.test(phone)) {
      setError('手机号格式不正确')
      return
    }
    if (!password) {
      setError('请输入密码')
      return
    }

    setIsLoading(true)
    try {
      const res = await loginApi({ phone, password })
      setAuth(res.token, res.user)
      router.replace(redirectTo)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? '手机号或密码错误' : err.message)
      } else {
        setError('网络异常，请稍后再试')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="text-2xl">登录</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="phone">手机号</Label>
            <Input
              id="phone"
              name="phone"
              type="tel"
              inputMode="numeric"
              autoComplete="username"
              placeholder="13800138000"
              value={phone}
              onChange={(e) => setPhone(e.target.value.trim())}
              disabled={isLoading}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              required
            />
          </div>
          {error !== null && (
            <div role="alert" className="text-sm text-destructive">
              {error}
            </div>
          )}
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? '登录中…' : '登录'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
