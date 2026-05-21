import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const replace = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace })
}))

import { NavUser } from '@/components/auth/nav-user'
import { useAuthStore } from '@/lib/auth/store'

describe('NavUser', () => {
  beforeEach(() => {
    replace.mockClear()
    useAuthStore.setState({ token: null, user: null, hasHydrated: false })
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders nothing when no user', () => {
    const { container } = render(<NavUser />)
    expect(container).toBeEmptyDOMElement()
  })

  it('clears store and redirects on logout', async () => {
    useAuthStore.setState({
      token: 'tk',
      user: { id: 1, phone: '13800138000', name: 'admin', role: 'admin' },
      hasHydrated: true
    })

    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          ({
            ok: true,
            status: 204,
            headers: new Headers(),
            json: async () => undefined,
            text: async () => ''
          }) as Response
      )
    )

    render(<NavUser />)
    expect(screen.getByText(/管理员/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '退出登录' }))
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login'))
    expect(useAuthStore.getState().token).toBeNull()
  })
})
