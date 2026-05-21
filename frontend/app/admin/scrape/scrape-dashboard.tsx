'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { listScrapeJobs, listScrapeLogs, runScrapeJob } from '@/lib/scrape/api'
import type { ScrapeJobInfo, ScrapeJobName, ScrapeLog, ScrapeLogQuery } from '@/lib/scrape/types'

import styles from './scrape-dashboard.module.css'

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'running', label: '运行中' },
  { value: 'success', label: '成功' },
  { value: 'partial', label: '部分成功' },
  { value: 'failed', label: '失败' }
]

const JOB_OPTIONS = [
  { value: '', label: '全部任务' },
  { value: 'schedule', label: '赛程' },
  { value: 'result', label: '赛果' },
  { value: 'odds', label: '赔率' },
  { value: 'team_stats', label: '球队状态' }
]

function statusClass(status: string): string {
  if (status === 'success') return styles.statusSuccess
  if (status === 'failed') return styles.statusFailed
  if (status === 'partial') return styles.statusPartial
  if (status === 'running') return styles.statusRunning
  return ''
}

function formatDateTime(value: string | null): string {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}

function formatLastRun(job: ScrapeJobInfo): string {
  if (!job.last_started_at) return '暂无记录'
  return formatDateTime(job.last_finished_at ?? job.last_started_at)
}

export function ScrapeDashboard() {
  const [jobs, setJobs] = useState<ScrapeJobInfo[]>([])
  const [logs, setLogs] = useState<ScrapeLog[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [runningJob, setRunningJob] = useState<ScrapeJobName | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [jobFilter, setJobFilter] = useState('')

  const query = useMemo<ScrapeLogQuery>(
    () => ({
      status: statusFilter || undefined,
      job_name: jobFilter || undefined,
      limit: 50
    }),
    [statusFilter, jobFilter]
  )

  const refresh = useCallback(async () => {
    setIsLoading(true)
    setErrorMsg(null)
    try {
      const [jobList, logList] = await Promise.all([listScrapeJobs(), listScrapeLogs(query)])
      setJobs(jobList)
      setLogs(logList.items)
      setTotal(logList.total)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : '加载失败')
    } finally {
      setIsLoading(false)
    }
  }, [query])

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleRun = useCallback(
    async (name: ScrapeJobName) => {
      setRunningJob(name)
      setErrorMsg(null)
      try {
        await runScrapeJob(name)
        await refresh()
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : '运行失败')
      } finally {
        setRunningJob(null)
      }
    },
    [refresh]
  )

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>抓取管理</div>
          <div className={styles.subtitle}>手动触发任务、查看最近运行状态</div>
        </div>
        <Button onClick={refresh} disabled={isLoading}>
          {isLoading ? '刷新中…' : '刷新'}
        </Button>
      </div>

      <div className={styles.jobGrid}>
        {jobs.map((job) => (
          <div key={job.name} className={styles.jobCard}>
            <div className={styles.jobTopline}>
              <div className={styles.jobName}>{job.name}</div>
              {job.last_status && (
                <span className={`${styles.statusBadge} ${statusClass(job.last_status)}`}>
                  {job.last_status}
                </span>
              )}
            </div>
            <div className={styles.jobDesc}>{job.description}</div>
            <div className={styles.lastRunBox}>
              <span>最后抓取</span>
              <strong>{formatLastRun(job)}</strong>
              <small>
                记录数 {job.last_records_count ?? '-'}
                {job.last_started_at && job.last_finished_at
                  ? ` · 开始 ${formatDateTime(job.last_started_at)}`
                  : ''}
              </small>
            </div>
            <Button size="sm" onClick={() => handleRun(job.name)} disabled={runningJob !== null}>
              {runningJob === job.name ? '运行中…' : '立即运行'}
            </Button>
          </div>
        ))}
      </div>

      {errorMsg && <div className={styles.errorText}>{errorMsg}</div>}

      <div className={styles.filters}>
        <select
          className={styles.select}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="状态过滤"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          value={jobFilter}
          onChange={(e) => setJobFilter(e.target.value)}
          aria-label="任务过滤"
        >
          {JOB_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <span className={styles.subtitle}>共 {total} 条</span>
      </div>

      {logs.length === 0 ? (
        <div className={styles.emptyState}>暂无记录</div>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>ID</th>
              <th>任务</th>
              <th>来源</th>
              <th>状态</th>
              <th>记录数</th>
              <th>开始时间</th>
              <th>结束时间</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td>{log.id}</td>
                <td>{log.job_name}</td>
                <td>{log.source}</td>
                <td>
                  <span className={`${styles.statusBadge} ${statusClass(log.status)}`}>
                    {log.status}
                  </span>
                </td>
                <td>{log.records_count}</td>
                <td>{formatDateTime(log.started_at)}</td>
                <td>{formatDateTime(log.finished_at)}</td>
                <td className={styles.errorText}>{log.error_message || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
