export type BetType = 'draw' | 'handicap_draw'

export interface Score {
  id: number
  match_id: number
  model_config_id: number
  user_id: number | null
  euro_score: number
  asian_score: number
  goals_score: number
  intent_score: number
  compression_score: number
  team_stats_score: number
  total_score: number
  bet_type: BetType | null
  kelly_pct: string | number | null
  is_recommended: boolean
  actual_hit: boolean | null
  bet_amount: string | number | null
  notes: string | null
  match_date: string | null
  home_team: string | null
  away_team: string | null
  league_name: string | null
  match_round: string | null
  sporttery_match_id: string | null
  sporttery_url: string | null
  had_draw_odds: string | number | null
  hhad_draw_odds: string | number | null
  bet_odds: string | number | null
  score_mode: 'rule' | 'diagnostic' | null
  rule_name: string | null
  rule_score: number | null
  diagnostic_score: number | null
  rule_explanation: string | null
}

export interface ScoreListResponse {
  items: Score[]
  total: number
}

export interface ScoreBreakdownItem {
  dimension: string
  score: number
  max_score: number
  explanation: string
}

export interface ScoreBreakdown {
  score: Score
  parts: ScoreBreakdownItem[]
}

export interface ScoreUpdatePayload {
  notes?: string | null
  bet_amount?: number | null
  actual_hit?: boolean | null
}

export interface ScoreComputeResult {
  date: string
  model_config_id: number
  computed: number
  skipped: number
}

export interface ScoreComputeUpcomingResult {
  model_config_id: number
  dates: string[]
  computed: number
  skipped: number
}
