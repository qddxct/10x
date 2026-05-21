'use client'

import { useEffect, useState } from 'react'

import { getResearchRun, getResearchTicketGroups } from '@/lib/research/api'
import type { ResearchRunDetail, ResearchTicketGroup } from '@/lib/research/types'

import { ResearchDetailClient } from './research-detail-client'
import styles from './research-detail.module.css'

interface ResearchDetailPageProps {
  params: {
    runId: string
  }
}

export default function ResearchDetailPage({ params }: ResearchDetailPageProps) {
  const runId = Number(params.runId)
  const [run, setRun] = useState<ResearchRunDetail | null>(null)
  const [ticketGroups, setTicketGroups] = useState<ResearchTicketGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        setLoading(true)
        const detail = await getResearchRun(runId)
        const ticketRows = await getResearchTicketGroups(runId)
        if (cancelled) return
        setRun(detail)
        setTicketGroups(ticketRows)
        setError(null)
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [runId])

  if (!Number.isFinite(runId)) {
    return <main className={styles.container}>研究报告 ID 无效。</main>
  }

  if (loading) {
    return <main className={styles.container}>正在加载研究报告...</main>
  }

  if (error) {
    return <main className={styles.container}>研究报告加载失败：{error}</main>
  }

  if (!run) {
    return <main className={styles.container}>研究报告不存在。</main>
  }

  return <ResearchDetailClient run={run} ticketGroups={ticketGroups} />
}
