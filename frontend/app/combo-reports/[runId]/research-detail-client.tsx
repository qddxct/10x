import Link from 'next/link'

import type { ResearchRunDetail, ResearchTicket, ResearchTicketGroup } from '@/lib/research/types'

import styles from './research-detail.module.css'

interface ResearchDetailClientProps {
  run: ResearchRunDetail
  ticketGroups: ResearchTicketGroup[]
}

function formatPct(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return `${(value * 100).toFixed(2)}%`
}

function formatNumber(value: unknown, digits = 2): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return value.toFixed(digits)
}

function formatMoney(value: unknown, options: { signed?: boolean } = {}): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  const abs = Math.abs(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
  if (!options.signed) return `¥${abs}`
  return `${value >= 0 ? '+' : '-'}¥${abs}`
}

function formatRuleValue(value: unknown): string {
  if (Array.isArray(value)) return value.join('、')
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}

function handicapText(betType: string, value: number | null): string {
  if (betType !== 'handicap_draw' || value === null || value === undefined) return ''
  return ` · 让球 ${value}`
}

function ticketStatus(hit: boolean): string {
  return hit ? '命中' : '未命中'
}

function pnlClass(pnl: number): string {
  return pnl >= 0 ? styles.hit : styles.miss
}

export function ResearchDetailClient({ run, ticketGroups }: ResearchDetailClientProps) {
  const summary = run.summary_json ?? {}
  const rules = (summary.strategy_rules ?? {}) as Record<string, unknown>
  const bestStrategy = typeof summary.best_strategy === 'string' ? summary.best_strategy : null
  const randomBaselines = (run.artifacts.random_baseline ?? []).filter((artifact) => {
    const strategy = artifact.payload_json.strategy
    return !bestStrategy || strategy === bestStrategy
  })

  return (
    <main className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>V3.4 研究报告明细</h1>
          <div className={styles.subtitle}>
            {run.name} · {run.date_from} → {run.date_to}
          </div>
        </div>
        <Link className={styles.backLink} href="/combo-reports">
          返回报告列表
        </Link>
      </div>

      <section className={styles.heroCard}>
        <div className={styles.sectionTitle}>报告摘要</div>
        <div className={styles.metricGrid}>
          <div className={styles.metric}>
            <span className={styles.label}>最佳策略</span>
            <strong className={styles.value}>{summary.best_strategy ?? '-'}</strong>
          </div>
          <div className={styles.metric}>
            <span className={styles.label}>候选场次</span>
            <strong className={styles.value}>{summary.candidates ?? '-'}</strong>
          </div>
          <div className={styles.metric}>
            <span className={styles.label}>二串一数量</span>
            <strong className={styles.value}>{summary.best_strategy_combo_count ?? '-'}</strong>
          </div>
          <div className={styles.metric}>
            <span className={styles.label}>模型 ROI</span>
            <strong className={styles.value}>{formatPct(summary.best_strategy_roi)}</strong>
          </div>
          <div className={styles.metric}>
            <span className={styles.label}>总投入</span>
            <strong className={styles.value}>{formatMoney(summary.best_strategy_stake)}</strong>
          </div>
          <div className={styles.metric}>
            <span className={styles.label}>总回收</span>
            <strong className={styles.value}>{formatMoney(summary.best_strategy_return)}</strong>
          </div>
          <div className={styles.metric}>
            <span className={styles.label}>净盈亏</span>
            <strong className={styles.value}>
              {formatMoney(summary.best_strategy_pnl, { signed: true })}
            </strong>
          </div>
          <div className={styles.metric}>
            <span className={styles.label}>随机均值 ROI</span>
            <strong className={styles.value}>{formatPct(summary.random_roi_avg)}</strong>
          </div>
          <div className={styles.metric}>
            <span className={styles.label}>超过随机百分位</span>
            <strong className={styles.value}>
              {formatPct(summary.model_roi_percentile_vs_random)}
            </strong>
          </div>
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.sectionTitle}>策略方案</div>
        <div className={styles.ruleList}>
          <div className={styles.ruleItem}>赔率范围：{formatRuleValue(rules.combo_odds_range)}</div>
          <div className={styles.ruleItem}>排除联赛：{formatRuleValue(rules.excluded_leagues)}</div>
          <div className={styles.ruleItem}>组单窗口：{formatRuleValue(rules.ticket_window)}</div>
          <div className={styles.ruleItem}>下单频率：{formatRuleValue(rules.frequency)}</div>
          <div className={styles.ruleItem}>混合选择：{formatRuleValue(rules.mixed_bet_policy)}</div>
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.sectionTitle}>随机对照</div>
        <div className={styles.controlNote}>
          这里展示多次随机试验的统计分布；下方逐票明细展示固定 seed
          的代表性随机样本，便于审计对照组选票构成。
        </div>
        <div className={styles.tipBox}>
          <strong>统计口径说明</strong>
          <div>ROI 均值：多次随机组单试验后的平均收益率，用来看随机买的整体水平。</div>
          <div>
            P90：随机结果中前 10% 的门槛，例如 P90 为 60%，表示只有约 10% 的随机结果能超过 60% ROI。
          </div>
          <div>
            模型分位：模型 ROI 在随机结果中的排名位置，例如 99%，表示模型超过了 99% 的随机结果。
          </div>
          <div>
            最大连不中：按二串一票次统计，连续未命中的最长票数；这个指标越高，越容易影响客户信心和销售热度。
          </div>
        </div>
        {randomBaselines.length === 0 ? (
          <div className={styles.empty}>暂无随机对照。</div>
        ) : (
          <div className={styles.baselineList}>
            {randomBaselines.map((artifact) => {
              const payload = artifact.payload_json
              return (
                <div className={styles.baselineItem} key={artifact.id}>
                  <strong>{String(payload.label ?? artifact.label)}</strong>
                  <div className={styles.meta}>
                    ROI 均值 {formatPct(payload.roi_avg)} · P90 {formatPct(payload.roi_p90)} ·
                    模型分位 {formatPct(payload.model_roi_percentile)}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      <section className={styles.card}>
        <div className={styles.sectionTitle}>二串一逐票明细</div>
        {ticketGroups.length === 0 ? (
          <div className={styles.empty}>暂无二串一逐票明细。</div>
        ) : (
          <div className={styles.groupList}>
            {ticketGroups.map((group) => (
              <section className={styles.ticketGroup} key={group.group_key}>
                <div className={styles.ticketGroupHead}>
                  <div>
                    <strong>{group.title}</strong>
                    <div className={styles.meta}>{group.description}</div>
                  </div>
                  <div className={styles.groupSummary}>
                    票数 {group.summary.ticket_count} · 投入 {formatMoney(group.summary.stake)} ·
                    回收 {formatMoney(group.summary.returns)} · 盈亏{' '}
                    {formatMoney(group.summary.pnl, { signed: true })} · ROI{' '}
                    {formatPct(group.summary.roi)} · 最大连中 {group.summary.max_hit_streak ?? 0} ·
                    最大连不中 {group.summary.max_miss_streak ?? 0}
                  </div>
                </div>
                {group.tickets.length === 0 ? (
                  <div className={styles.empty}>该组暂无逐票明细。</div>
                ) : (
                  <TicketList tickets={group.tickets} />
                )}
              </section>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}

function TicketList({ tickets }: { tickets: ResearchTicket[] }) {
  return (
    <div className={styles.ticketList}>
      {tickets.map((ticket, index) => (
        <article className={styles.ticketItem} key={`${ticket.ticket_date}-${index}`}>
          <div className={styles.ticketHead}>
            <span>
              {ticket.ticket_date} · 投入 {formatMoney(ticket.stake ?? 100)} · 组合赔率{' '}
              {formatNumber(ticket.combo_odds)} · {ticketStatus(ticket.is_hit)} · 盈亏{' '}
              {formatMoney(ticket.pnl, { signed: true })}
            </span>
            <span className={pnlClass(ticket.pnl)}>{ticket.pnl >= 0 ? '盈利' : '亏损'}</span>
          </div>
          <div className={styles.legGrid}>
            {ticket.legs.map((leg) => (
              <div className={styles.legCard} key={leg.match_id}>
                <strong>
                  {leg.league} · {leg.home_team} vs {leg.away_team}
                </strong>
                <div className={styles.meta}>
                  选择：{leg.bet_label}
                  {handicapText(leg.bet_type, leg.handicap_value)} · 赔率 {formatNumber(leg.odds)} ·
                  赛果 {leg.result_label}
                </div>
              </div>
            ))}
          </div>
        </article>
      ))}
    </div>
  )
}
