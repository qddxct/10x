export interface TotalGoalItem {
  id: number
  match_id: number
  model_version: string
  target_goals: number
  target_label: string
  odds_label: string | null
  total_score: number
  confidence_pct: string | number | null
  bet_odds: string | number | null
  is_recommended: boolean
  hit: boolean | null
  explanation: {
    expected_goals?: number
    target_goals?: number[]
    target_odds?: Record<string, string>
    market_line?: number | null
    recent_expected?: number | null
    venue_expected?: number | null
    h2h_expected?: number | null
    low_rate?: number | null
    high_rate?: number | null
    parts?: Record<string, number>
  } | null
  match_date: string | null
  home_team: string | null
  away_team: string | null
  league_name: string | null
  match_round: string | null
  sporttery_url: string | null
  home_score: number | null
  away_score: number | null
  actual_total_goals: number | null
}

export interface TotalGoalCombo {
  title: string
  items: TotalGoalItem[]
  combo_odds: string | number | null
  avg_score: number
  status: 'pending' | 'won' | 'lost'
  hit: boolean | null
}

export interface TotalGoalTodayResponse {
  items: TotalGoalItem[]
  total: number
  combos: TotalGoalCombo[]
}

export interface TotalGoalListResponse {
  items: TotalGoalItem[]
  total: number
}

export interface TotalGoalComputeResult {
  date?: string
  dates?: string[]
  computed: number
  skipped: number
}
