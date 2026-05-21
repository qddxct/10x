import { apiFetch } from '@/lib/auth/api'

import type {
  ScrapeJobInfo,
  ScrapeJobName,
  ScrapeLogList,
  ScrapeLogQuery,
  ScrapeRunResult
} from './types'

export async function listScrapeJobs(): Promise<ScrapeJobInfo[]> {
  return apiFetch<ScrapeJobInfo[]>('/api/scrape/jobs')
}

export async function listScrapeLogs(query: ScrapeLogQuery = {}): Promise<ScrapeLogList> {
  const params = new URLSearchParams()
  if (query.source) params.set('source', query.source)
  if (query.status) params.set('status', query.status)
  if (query.job_name) params.set('job_name', query.job_name)
  if (query.limit !== undefined) params.set('limit', String(query.limit))
  if (query.offset !== undefined) params.set('offset', String(query.offset))
  const suffix = params.toString() ? `?${params.toString()}` : ''
  return apiFetch<ScrapeLogList>(`/api/scrape/logs${suffix}`)
}

export async function runScrapeJob(name: ScrapeJobName): Promise<ScrapeRunResult> {
  return apiFetch<ScrapeRunResult>(`/api/scrape/jobs/${name}/run`, {
    method: 'POST'
  })
}
