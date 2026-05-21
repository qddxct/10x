export type BacktestMode = 'fixed' | 'kelly' | 'both'

export interface BetDetail {
  match_id: number
  match_date: string
  league: string
  home_team: string
  away_team: string
  bet_type: 'draw' | 'handicap_draw'
  handicap_value?: string | number | null
  total_score: number
  odds: string
  stake_fixed: string
  stake_kelly: string
  is_hit: boolean
  home_score: number
  away_score: number
  pnl_fixed: string
  pnl_kelly: string
}

export interface EquityCurvePoint {
  date: string
  cumulative_pnl_fixed: number
  cumulative_pnl_kelly: number
}

export interface BacktestBucket {
  bets: number
  hits: number
  hit_rate: number
  profit_loss_fixed: number
  profit_loss_kelly: number
  roi_fixed: number
  roi_kelly: number
}

export interface BacktestSummary {
  id: number
  model_config_id: number
  date_from: string
  date_to: string
  total_bets: number
  hit_count: number
  hit_rate: string | number
  roi: string | number
  profit_loss: string | number
  kelly_profit_loss: string | number
  kelly_roi: string | number
  mode: BacktestMode
  initial_capital: string | number | null
  fixed_stake: string | number | null
  bets_detail: BetDetail[] | null
  results_by_score: Record<string, BacktestBucket> | null
  results_by_league: Record<string, BacktestBucket> | null
  equity_curve: EquityCurvePoint[] | null
  created_at?: string | null
}

export interface BacktestListResponse {
  items: BacktestSummary[]
  total: number
}

export interface BacktestCreatePayload {
  model_config_id?: number | null
  date_from: string
  date_to: string
  mode?: BacktestMode
  initial_capital?: number
  fixed_stake?: number
}

export interface BacktestCompareResponse {
  a: BacktestSummary
  b: BacktestSummary
}
