import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const replace = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams('redirect=/home')
}))

import { LoginForm } from '@/app/login/login-form'
import { useAuthStore } from '@/lib/auth/store'

describe('LoginForm', () => {
  beforeEach(() => {
    replace.mockClear()
    useAuthStore.setState({ token: null, user: null, hasHydrated: false })
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function stubFetch(status: number, body: unknown) {
    const mock = vi.fn(
      async () =>
        ({
          ok: status >= 200 && status < 300,
          status,
          headers: new Headers({ 'Content-Type': 'application/json' }),
          json: async () => body,
          text: async () => ''
        }) as Response
    )
    vi.stubGlobal('fetch', mock)
    return mock
  }

  it('shows validation error for bad phone format', async () => {
    render(<LoginForm />)
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '123' } })
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'Abcd1234' } })
    fireEvent.click(screen.getByRole('button', { name: '登录' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('手机号格式不正确')
  })

  it('submits credentials and redirects on success', async () => {
    stubFetch(200, {
      token: 'tk-1',
      token_type: 'bearer',
      user: { id: 1, phone: '13800138000', name: 'admin', role: 'admin' }
    })
    render(<LoginForm />)
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } })
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'Abcd1234' } })
    fireEvent.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/home'))
    expect(useAuthStore.getState().token).toBe('tk-1')
    expect(useAuthStore.getState().user?.role).toBe('admin')
  })

  it('shows friendly message on 401', async () => {
    stubFetch(401, { detail: 'Invalid phone or password' })
    render(<LoginForm />)
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } })
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'wrong123' } })
    fireEvent.click(screen.getByRole('button', { name: '登录' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('手机号或密码错误')
    expect(replace).not.toHaveBeenCalled()
  })
})
