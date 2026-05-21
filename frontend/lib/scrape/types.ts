export type ScrapeJobName = 'schedule' | 'result' | 'odds' | 'team_stats' | 'scoring'
export type ScrapeStatus = 'running' | 'success' | 'failed' | 'partial'
export type ScrapeSource = 'sporttery' | 'titan007' | 'other'

export interface ScrapeJobInfo {
  name: ScrapeJobName
  description: string
  last_started_at: string | null
  last_finished_at: string | null
  last_status: ScrapeStatus | null
  last_records_count: number | null
}

export interface ScrapeLog {
  id: number
  source: ScrapeSource
  job_name: string
  status: ScrapeStatus
  started_at: string
  finished_at: string | null
  records_count: number
  error_message: string | null
}

export interface ScrapeLogList {
  items: ScrapeLog[]
  total: number
}

export interface ScrapeRunResult {
  job: ScrapeJobName
  status: ScrapeStatus
  records: number
  error: string | null
}

export interface ScrapeLogQuery {
  source?: string
  status?: string
  job_name?: string
  limit?: number
  offset?: number
}
