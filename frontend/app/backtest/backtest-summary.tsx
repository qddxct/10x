'use client'

import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'

import type { BacktestSummary as BacktestSummaryData } from '@/lib/backtest/types'

import styles from './backtest-client.module.css'

const BAND_COLORS = ['#22d3ee', '#34d399', '#f97316', '#a78bfa', '#f43f5e', '#f59e0b']

interface BacktestSummaryProps {
  data: BacktestSummaryData
}

function toNum(v: string | number | null | undefined): number {
  if (v === null || v === undefined) return 0
  return typeof v === 'string' ? parseFloat(v) : v
}

function pct(v: string | number | null | undefined): string {
  return `${(toNum(v) * 100).toFixed(2)}%`
}

function money(v: string | number | null | undefined): string {
  return `${toNum(v).toFixed(2)} 元`
}

export function BacktestSummary({ data }: BacktestSummaryProps) {
  const equity = data.equity_curve ?? []
  const scoreBands = Object.entries(data.results_by_score ?? {})

  const pieData = scoreBands.map(([name, stats]) => ({
    name,
    value: stats.bets
  }))

  const fixedStake = toNum(data.fixed_stake)
  const initialCapital = toNum(data.initial_capital)
  const totalFixed = fixedStake * data.total_bets
  const pnlFixed = toNum(data.profit_loss)
  const recoveryFixed = totalFixed + pnlFixed
  const pnlKelly = toNum(data.kelly_profit_loss)

  const bets = data.bets_detail ?? []
  const totalKellyStake = bets.reduce((sum, b) => sum + toNum(b.stake_kelly), 0)
  const recoveryKelly = totalKellyStake + pnlKelly

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className={styles.summaryBanner}>
        <span>
          总场次 <strong>{data.total_bets}</strong>
        </span>
        <span>
          命中 <strong>{data.hit_count}</strong> 场
        </span>
        <span>
          命中率 <strong>{pct(data.hit_rate)}</strong>
        </span>
        <span>
          初始本金 <strong>{money(initialCapital)}</strong>
        </span>
        <span>
          每场固定投注 <strong>{money(fixedStake)}</strong>
        </span>
      </div>

      <div className={styles.cardSection}>固定投注模式</div>
      <div className={styles.cardGrid}>
        <Card label="总投入（固定）" value={money(totalFixed)} sub="每场固定投注 × 总场次" />
        <Card
          label="总回收（固定）"
          value={money(recoveryFixed)}
          sub="命中场次的奖金总和（含本金）"
        />
        <Card
          label="净盈亏（固定）"
          value={money(pnlFixed)}
          sub={`ROI ${pct(data.roi)}`}
          tone={pnlFixed >= 0 ? 'positive' : 'negative'}
        />
      </div>

      <div className={styles.cardSection}>Kelly 模式</div>
      <div className={styles.cardGrid}>
        <Card
          label="总投入（Kelly）"
          value={money(totalKellyStake)}
          sub="各场 Kelly 建议金额累计"
        />
        <Card
          label="总回收（Kelly）"
          value={money(recoveryKelly)}
          sub="命中场次的奖金总和（含本金）"
        />
        <Card
          label="净盈亏（Kelly）"
          value={money(pnlKelly)}
          sub={`ROI ${pct(data.kelly_roi)}`}
          tone={pnlKelly >= 0 ? 'positive' : 'negative'}
        />
      </div>

      {equity.length > 0 && (
        <div className={styles.chartWrapper}>
          <div className={styles.chartTitle}>累计盈亏曲线</div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={equity}>
              <CartesianGrid stroke="rgb(51 65 85)" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="cumulative_pnl_fixed"
                name="固定投注"
                stroke="#22d3ee"
                dot={false}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="cumulative_pnl_kelly"
                name="Kelly"
                stroke="#f97316"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {pieData.length > 0 && (
        <div className={styles.chartWrapper}>
          <div className={styles.chartTitle}>分数段分布</div>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Tooltip />
              <Legend />
              <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={90} label>
                {pieData.map((_, idx) => (
                  <Cell key={idx} fill={BAND_COLORS[idx % BAND_COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className={styles.hint}>
        备注：MVP 基于当前抓取的最新一份赔率做回测，历史赔率快照功能将在后续版本引入。
      </div>
    </div>
  )
}

interface CardProps {
  label: string
  value: string
  sub?: string
  tone?: 'positive' | 'negative'
}

function Card({ label, value, sub, tone }: CardProps) {
  const toneClass =
    tone === 'positive' ? styles.cardPositive : tone === 'negative' ? styles.cardNegative : ''
  return (
    <div className={`${styles.card} ${toneClass}`}>
      <div className={styles.cardLabel}>{label}</div>
      <div className={styles.cardValue}>{value}</div>
      {sub && <div className={styles.cardSub}>{sub}</div>}
    </div>
  )
}
