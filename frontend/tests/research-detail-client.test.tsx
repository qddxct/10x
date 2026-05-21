import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ResearchDetailClient } from '@/app/combo-reports/[runId]/research-detail-client'

const run = {
  id: 6,
  name: 'v34-combo-selector',
  base_model_config_id: 8,
  date_from: '2024-09-28',
  date_to: '2026-04-22',
  random_seed: 20260426,
  random_trials: 1000,
  status: 'succeeded',
  summary_json: {
    candidates: 561,
    best_strategy: 'frequency_selector',
    best_strategy_combo_count: 139,
    best_strategy_roi: 0.4972,
    best_strategy_stake: 13900,
    best_strategy_pnl: 6911.08,
    best_strategy_return: 20811.08,
    random_label: '候选池约束随机',
    random_roi_avg: 0.2375,
    model_roi_percentile_vs_random: 0.819,
    strategy_rules: {
      combo_odds_range: '10-14',
      excluded_leagues: ['德甲', '澳超'],
      ticket_window: '两天滚动组单',
      frequency: '每个滚动窗口最多一单',
      mixed_bet_policy: '允许平/让平混合, 但不额外加分'
    }
  },
  report_path: 'docs/analysis/v34.md',
  created_at: '2026-04-26T15:20:00',
  artifacts: {
    random_baseline: [
      {
        id: 1,
        run_id: 6,
        artifact_type: 'random_baseline',
        label: 'frequency_selector:候选池约束随机',
        payload_json: {
          strategy: 'frequency_selector',
          label: '候选池约束随机',
          roi_avg: 0.2375,
          roi_p90: 0.48,
          model_roi_percentile: 0.819
        }
      }
    ]
  }
}

const modelTickets = [
  {
    strategy: 'frequency_selector',
    ticket_date: '2026-01-01',
    combo_odds: 11.2,
    stake: 100,
    is_hit: false,
    pnl: -100,
    legs: [
      {
        match_id: 11,
        match_date: '2026-01-01',
        league: '英冠',
        home_team: '主队A',
        away_team: '客队A',
        bet_type: 'draw' as const,
        bet_label: '平',
        handicap_value: 0.25,
        odds: 3.2,
        is_hit: true,
        result_label: '1-1 命中',
        total_score: 108
      },
      {
        match_id: 12,
        match_date: '2026-01-02',
        league: '西甲',
        home_team: '主队B',
        away_team: '客队B',
        bet_type: 'handicap_draw' as const,
        bet_label: '让平 (-1)',
        handicap_value: -1,
        odds: 3.5,
        is_hit: false,
        result_label: '1-1 未命中',
        total_score: 112
      }
    ]
  }
]

const ticketGroups = [
  {
    group_key: 'model:frequency_selector',
    title: '模型最佳策略：frequency_selector',
    description: '模型选择出的实际二串一方案。',
    summary: {
      ticket_count: 1,
      stake: 100,
      returns: 0,
      pnl: -100,
      roi: -1,
      max_hit_streak: 0,
      max_miss_streak: 1
    },
    tickets: modelTickets
  },
  {
    group_key: 'random:frequency_selector:全市场随机',
    title: '对照组：全市场随机',
    description: '固定 seed 的随机样本，用于审计随机组选票构成；随机 ROI 以汇总分布为准。',
    summary: {
      ticket_count: 1,
      stake: 100,
      returns: 0,
      pnl: -100,
      roi: -1,
      max_hit_streak: 0,
      max_miss_streak: 1
    },
    tickets: [
      {
        strategy: 'frequency_selector',
        group_type: 'random_control',
        control_label: '全市场随机',
        ticket_date: '2026-01-03',
        combo_odds: 12.1,
        stake: 100,
        is_hit: false,
        pnl: -100,
        legs: [
          {
            match_id: 21,
            match_date: '2026-01-03',
            league: '荷乙',
            home_team: '随机主队A',
            away_team: '随机客队A',
            bet_type: 'draw' as const,
            bet_label: '平',
            handicap_value: null,
            odds: 3.4,
            is_hit: false,
            result_label: '2-1 未命中',
            total_score: 0
          },
          {
            match_id: 22,
            match_date: '2026-01-04',
            league: '法乙',
            home_team: '随机主队B',
            away_team: '随机客队B',
            bet_type: 'draw' as const,
            bet_label: '平',
            handicap_value: null,
            odds: 3.56,
            is_hit: true,
            result_label: '0-0 命中',
            total_score: 0
          }
        ]
      }
    ]
  },
  {
    group_key: 'random:frequency_selector:候选池约束随机',
    title: '对照组：候选池约束随机',
    description: '固定 seed 的随机样本，用于审计随机组选票构成；随机 ROI 以汇总分布为准。',
    summary: {
      ticket_count: 1,
      stake: 100,
      returns: 455,
      pnl: 355,
      roi: 3.55,
      max_hit_streak: 1,
      max_miss_streak: 0
    },
    tickets: [
      {
        strategy: 'frequency_selector',
        group_type: 'random_control',
        control_label: '候选池约束随机',
        ticket_date: '2026-01-05',
        combo_odds: 4.55,
        stake: 100,
        is_hit: true,
        pnl: 355,
        legs: [
          {
            match_id: 31,
            match_date: '2026-01-05',
            league: '英冠',
            home_team: '候选主队A',
            away_team: '候选客队A',
            bet_type: 'handicap_draw' as const,
            bet_label: '让平 (+1)',
            handicap_value: 1,
            odds: 2.1,
            is_hit: true,
            result_label: '0-1 命中',
            total_score: 104
          },
          {
            match_id: 32,
            match_date: '2026-01-05',
            league: '西乙',
            home_team: '候选主队B',
            away_team: '候选客队B',
            bet_type: 'draw' as const,
            bet_label: '平',
            handicap_value: null,
            odds: 2.17,
            is_hit: true,
            result_label: '1-1 命中',
            total_score: 101
          }
        ]
      }
    ]
  }
]

describe('ResearchDetailClient', () => {
  it('renders summary, strategy rules, random baseline, and ticket legs', () => {
    render(<ResearchDetailClient run={run} ticketGroups={ticketGroups} />)

    expect(screen.getByText('V3.4 研究报告明细')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回报告列表' })).toHaveAttribute(
      'href',
      '/combo-reports'
    )
    expect(screen.getByText('二串一逐票明细')).toBeInTheDocument()
    expect(
      screen.getByText(
        '这里展示多次随机试验的统计分布；下方逐票明细展示固定 seed 的代表性随机样本，便于审计对照组选票构成。'
      )
    ).toBeInTheDocument()
    expect(screen.getByText('统计口径说明')).toBeInTheDocument()
    expect(screen.getByText(/ROI 均值：多次随机组单试验后的平均收益率/)).toBeInTheDocument()
    expect(screen.getByText(/P90：随机结果中前 10% 的门槛/)).toBeInTheDocument()
    expect(screen.getByText(/模型分位：模型 ROI 在随机结果中的排名位置/)).toBeInTheDocument()
    expect(screen.getByText(/最大连不中：按二串一票次统计/)).toBeInTheDocument()
    expect(screen.getByText('模型最佳策略：frequency_selector')).toBeInTheDocument()
    expect(screen.getByText('对照组：全市场随机')).toBeInTheDocument()
    expect(screen.getByText('对照组：候选池约束随机')).toBeInTheDocument()
    expect(screen.getAllByText(/最大连中/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/最大连不中/).length).toBeGreaterThan(0)
    expect(screen.getByText('frequency_selector')).toBeInTheDocument()
    expect(screen.getByText('49.72%')).toBeInTheDocument()
    expect(screen.getByText('¥13,900.00')).toBeInTheDocument()
    expect(screen.getByText('¥20,811.08')).toBeInTheDocument()
    expect(screen.getByText('+¥6,911.08')).toBeInTheDocument()
    expect(screen.getByText('赔率范围：10-14')).toBeInTheDocument()
    expect(screen.getByText('排除联赛：德甲、澳超')).toBeInTheDocument()
    expect(screen.getByText('候选池约束随机')).toBeInTheDocument()
    expect(screen.getByText('23.75%')).toBeInTheDocument()
    expect(
      screen.getByText('2026-01-01 · 投入 ¥100.00 · 组合赔率 11.20 · 未命中 · 盈亏 -¥100.00')
    ).toBeInTheDocument()
    expect(screen.getByText('英冠 · 主队A vs 客队A')).toBeInTheDocument()
    expect(screen.getByText('选择：平 · 赔率 3.20 · 赛果 1-1 命中')).toBeInTheDocument()
    expect(
      screen.getByText('选择：让平 (-1) · 让球 -1 · 赔率 3.50 · 赛果 1-1 未命中')
    ).toBeInTheDocument()
    expect(screen.getByText('荷乙 · 随机主队A vs 随机客队A')).toBeInTheDocument()
    expect(screen.getByText('英冠 · 候选主队A vs 候选客队A')).toBeInTheDocument()
    expect(
      screen.getByText('选择：让平 (+1) · 让球 1 · 赔率 2.10 · 赛果 0-1 命中')
    ).toBeInTheDocument()
  })
})
