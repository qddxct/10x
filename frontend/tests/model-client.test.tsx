import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/model-config/api', () => ({
  listModelConfigs: vi.fn(),
  activateModelConfig: vi.fn(),
  cloneModelConfig: vi.fn(),
  createModelConfig: vi.fn(),
  updateModelConfig: vi.fn()
}))

vi.mock('@/lib/auth/store', () => ({
  useAuthStore: vi.fn()
}))

import { ModelClient } from '@/app/model/model-client'
import { useAuthStore } from '@/lib/auth/store'
import {
  activateModelConfig,
  cloneModelConfig,
  createModelConfig,
  listModelConfigs,
  updateModelConfig
} from '@/lib/model-config/api'

const mockList = vi.mocked(listModelConfigs)
const mockActivate = vi.mocked(activateModelConfig)
const mockClone = vi.mocked(cloneModelConfig)
const mockCreate = vi.mocked(createModelConfig)
const mockUpdate = vi.mocked(updateModelConfig)
const mockAuth = vi.mocked(useAuthStore)

function configFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    name: 'default',
    created_by: null,
    parent_id: null,
    is_active: true,
    weights_json: {
      euro: 25,
      asian: 20,
      goals: 20,
      intent: 15,
      compression: 20,
      team_stats: 20
    },
    thresholds_json: {
      min_total_score: 78,
      recommend_total_score: 84,
      draw_min_score: 84,
      handicap_draw_min_score: 78
    },
    kelly_bands_json: {
      low: { min_score: 78, max_score: 84, kelly_pct: 0.01 }
    },
    scrape_schedule_json: null,
    created_at: '2026-04-01T00:00:00',
    updated_at: '2026-04-01T00:00:00',
    ...overrides
  }
}

function stubAuth(role: 'admin' | 'member') {
  mockAuth.mockImplementation((selector: (s: unknown) => unknown) =>
    selector({
      user: { id: 1, name: 'tester', role, phone: '13800000000' },
      token: 't',
      hasHydrated: true,
      setAuth: vi.fn(),
      clear: vi.fn(),
      hydrate: vi.fn()
    })
  )
}

describe('ModelClient', () => {
  beforeEach(() => {
    mockList.mockReset()
    mockActivate.mockReset()
    mockClone.mockReset()
    mockCreate.mockReset()
    mockUpdate.mockReset()
    mockAuth.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('member sees read-only mode', async () => {
    stubAuth('member')
    mockList.mockResolvedValue({ items: [configFixture() as never], total: 1 })

    render(<ModelClient />)
    await waitFor(() => expect(mockList).toHaveBeenCalled())

    expect(screen.queryByRole('button', { name: '编辑' })).toBeNull()
    expect(screen.queryByRole('button', { name: '克隆' })).toBeNull()
    expect(screen.queryByRole('button', { name: '激活' })).toBeNull()
    expect(screen.getByLabelText('权重-euro')).toBeDisabled()
  })

  it('admin can edit and save weights via PATCH', async () => {
    stubAuth('admin')
    const cfg = configFixture() as never
    mockList.mockResolvedValue({ items: [cfg], total: 1 })
    mockUpdate.mockResolvedValue(cfg as never)

    render(<ModelClient />)
    await waitFor(() => expect(screen.getByText('编辑')).toBeInTheDocument())

    fireEvent.click(screen.getByText('编辑'))
    const euro = screen.getByLabelText('权重-euro') as HTMLInputElement
    expect(euro).not.toBeDisabled()
    fireEvent.change(euro, { target: { value: '30' } })

    fireEvent.click(screen.getByText('保存'))
    await waitFor(() => expect(mockUpdate).toHaveBeenCalledTimes(1))
    const [id, payload] = mockUpdate.mock.calls[0]
    expect(id).toBe(1)
    expect((payload as { weights_json: { euro: number } }).weights_json.euro).toBe(30)
  })

  it('admin activate calls API and reloads', async () => {
    stubAuth('admin')
    const a = configFixture({ id: 1, name: 'a', is_active: true }) as never
    const b = configFixture({ id: 2, name: 'b', is_active: false }) as never
    mockList.mockResolvedValue({ items: [a, b], total: 2 })
    mockActivate.mockResolvedValue({
      ...(b as Record<string, unknown>),
      is_active: true,
      scores_recomputed: 3
    } as never)

    render(<ModelClient />)
    await waitFor(() => expect(screen.getByText('b')).toBeInTheDocument())

    fireEvent.click(screen.getByText('b'))
    const activateBtn = await waitFor(() => screen.getByRole('button', { name: '激活' }))
    fireEvent.click(activateBtn)
    await waitFor(() => expect(mockActivate).toHaveBeenCalledWith(2))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('重算今日评分 3 条'))
  })

  it('admin clone prompts for name and calls API', async () => {
    stubAuth('admin')
    const a = configFixture() as never
    mockList.mockResolvedValue({ items: [a], total: 1 })
    mockClone.mockResolvedValue({
      ...(a as Record<string, unknown>),
      id: 9,
      name: 'default-v2',
      is_active: false
    } as never)
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('default-v2')

    render(<ModelClient />)
    await waitFor(() => expect(screen.getByText('克隆')).toBeInTheDocument())

    fireEvent.click(screen.getByText('克隆'))
    await waitFor(() => expect(mockClone).toHaveBeenCalledWith(1, 'default-v2'))
    promptSpy.mockRestore()
  })

  it('new config uses createModelConfig', async () => {
    stubAuth('admin')
    mockList.mockResolvedValue({ items: [], total: 0 })
    mockCreate.mockResolvedValue({ id: 5, name: 'fresh' } as never)

    render(<ModelClient />)
    await waitFor(() => expect(screen.getByText('新建')).toBeInTheDocument())
    fireEvent.click(screen.getByText('新建'))

    const nameInput = screen.getByLabelText('模型名称') as HTMLInputElement
    fireEvent.change(nameInput, { target: { value: 'fresh' } })

    fireEvent.click(screen.getByText('保存'))
    await waitFor(() => expect(mockCreate).toHaveBeenCalled())
    const payload = mockCreate.mock.calls[0][0] as { name: string }
    expect(payload.name).toBe('fresh')
  })
})
