import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/scrape/api', () => ({
  listScrapeJobs: vi.fn(),
  listScrapeLogs: vi.fn(),
  runScrapeJob: vi.fn()
}))

import { ScrapeDashboard } from '@/app/admin/scrape/scrape-dashboard'
import { listScrapeJobs, listScrapeLogs, runScrapeJob } from '@/lib/scrape/api'
import type { ScrapeJobInfo, ScrapeJobName } from '@/lib/scrape/types'

const mockedJobs = vi.mocked(listScrapeJobs)
const mockedLogs = vi.mocked(listScrapeLogs)
const mockedRun = vi.mocked(runScrapeJob)

function jobFixture(name: ScrapeJobName, description: string): ScrapeJobInfo {
  return {
    name,
    description,
    last_started_at: null,
    last_finished_at: null,
    last_status: null,
    last_records_count: null
  }
}

describe('ScrapeDashboard', () => {
  beforeEach(() => {
    mockedJobs.mockReset()
    mockedLogs.mockReset()
    mockedRun.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders jobs and logs on mount', async () => {
    mockedJobs.mockResolvedValue([
      {
        ...jobFixture('schedule', '每日 08:30'),
        last_started_at: '2026-04-21T00:30:00',
        last_finished_at: '2026-04-21T00:31:00',
        last_status: 'success',
        last_records_count: 7
      },
      jobFixture('odds', '每 2 小时')
    ])
    mockedLogs.mockResolvedValue({
      total: 1,
      items: [
        {
          id: 42,
          source: 'sporttery',
          job_name: 'schedule',
          status: 'success',
          started_at: '2026-04-21T00:30:00',
          finished_at: '2026-04-21T00:31:00',
          records_count: 7,
          error_message: null
        }
      ]
    })

    render(<ScrapeDashboard />)

    await waitFor(() => expect(screen.getByText('每日 08:30')).toBeInTheDocument())
    expect(screen.getByText('每 2 小时')).toBeInTheDocument()
    expect(screen.getByText('共 1 条')).toBeInTheDocument()
    expect(screen.getByText('success')).toBeInTheDocument()
    expect(screen.getByText(/最后抓取/)).toBeInTheDocument()
  })

  it('triggers run and refreshes afterwards', async () => {
    mockedJobs.mockResolvedValue([jobFixture('schedule', 'x')])
    mockedLogs.mockResolvedValue({ items: [], total: 0 })
    mockedRun.mockResolvedValue({
      job: 'schedule',
      status: 'success',
      records: 2,
      error: null
    })

    render(<ScrapeDashboard />)
    await waitFor(() => expect(screen.getByText('x')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: '立即运行' }))
    await waitFor(() => expect(mockedRun).toHaveBeenCalledWith('schedule'))
    await waitFor(() => expect(mockedLogs).toHaveBeenCalledTimes(2))
  })

  it('shows error message on failure', async () => {
    mockedJobs.mockRejectedValue(new Error('Network down'))
    mockedLogs.mockResolvedValue({ items: [], total: 0 })

    render(<ScrapeDashboard />)
    await waitFor(() => expect(screen.getByText('Network down')).toBeInTheDocument())
  })
})
