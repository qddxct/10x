'use client'

import { InfoTooltip } from '@/components/info-tooltip/info-tooltip'
import { BET_TYPE_LABEL, TOOLTIPS } from '@/lib/backtest/tooltips'
import type { BetDetail } from '@/lib/backtest/types'

import styles from './backtest-bets-table.module.css'

interface BacktestBetsTableProps {
  bets: BetDetail[] | null | undefined
}

function toNum(v: string | number | null | undefined): number {
  if (v === null || v === undefined) return 0
  return typeof v === 'string' ? parseFloat(v) : v
}

function money(v: string | number): string {
  return toNum(v).toFixed(2)
}

function signed(v: string | number): string {
  const n = toNum(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}`
}

function formatDate(d: string): string {
  const [, month, day] = d.split('-')
  return `${month}-${day}`
}

function formatHandicap(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === '') return '-'
  const n = toNum(v)
  if (!Number.isFinite(n)) return String(v)
  if (n === 0) return '0'
  return `${n > 0 ? '+' : ''}${n}`
}

export function BacktestBetsTable({ bets }: BacktestBetsTableProps) {
  if (!bets || bets.length === 0) {
    return (
      <div className={styles.wrapper}>
        <div className={styles.title}>下注明细</div>
        <div className={styles.empty}>历史回测无明细数据，请重新发起一次回测。</div>
      </div>
    )
  }

  const sorted = [...bets].sort((a, b) => b.match_date.localeCompare(a.match_date))

  const totalFixedStake = sorted.reduce((s, b) => s + toNum(b.stake_fixed), 0)
  const totalFixedPnl = sorted.reduce((s, b) => s + toNum(b.pnl_fixed), 0)
  const totalFixedRecovery = totalFixedStake + totalFixedPnl
  const totalKellyStake = sorted.reduce((s, b) => s + toNum(b.stake_kelly), 0)
  const totalKellyPnl = sorted.reduce((s, b) => s + toNum(b.pnl_kelly), 0)

  return (
    <div className={styles.wrapper}>
      <div className={styles.title}>下注明细（{sorted.length} 场）</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>日期</th>
            <th>联赛</th>
            <th>对阵</th>
            <th>
              推荐
              <InfoTooltip text={TOOLTIPS.bet_type} />
            </th>
            <th>让球</th>
            <th>
              总分
              <InfoTooltip text={TOOLTIPS.total_score} />
            </th>
            <th>
              赔率
              <InfoTooltip text={TOOLTIPS.odds} />
            </th>
            <th>固定投注</th>
            <th>
              Kelly 投注
              <InfoTooltip text={TOOLTIPS.stake_kelly} />
            </th>
            <th>结果</th>
            <th>固定盈亏</th>
            <th>Kelly 盈亏</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((b) => {
            const pnlFixed = toNum(b.pnl_fixed)
            const pnlKelly = toNum(b.pnl_kelly)
            return (
              <tr key={`${b.match_id}-${b.bet_type}`}>
                <td>{formatDate(b.match_date)}</td>
                <td>{b.league}</td>
                <td>
                  {b.home_team} vs {b.away_team}
                </td>
                <td>{BET_TYPE_LABEL[b.bet_type] ?? b.bet_type}</td>
                <td>{b.bet_type === 'handicap_draw' ? formatHandicap(b.handicap_value) : '-'}</td>
                <td>{b.total_score}</td>
                <td>{b.odds}</td>
                <td>{money(b.stake_fixed)}</td>
                <td>{money(b.stake_kelly)}</td>
                <td className={b.is_hit ? styles.hit : styles.miss}>
                  {b.home_score}:{b.away_score} {b.is_hit ? '✓' : '✗'}
                </td>
                <td className={pnlFixed >= 0 ? styles.positive : styles.negative}>
                  {signed(b.pnl_fixed)}
                </td>
                <td className={pnlKelly >= 0 ? styles.positive : styles.negative}>
                  {signed(b.pnl_kelly)}
                </td>
              </tr>
            )
          })}
          <tr className={styles.footerRow}>
            <td colSpan={7}>合计</td>
            <td>{money(totalFixedStake)}</td>
            <td>{money(totalKellyStake)}</td>
            <td>回收 {money(totalFixedRecovery)}</td>
            <td className={totalFixedPnl >= 0 ? styles.positive : styles.negative}>
              {signed(totalFixedPnl)}
            </td>
            <td className={totalKellyPnl >= 0 ? styles.positive : styles.negative}>
              {signed(totalKellyPnl)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
