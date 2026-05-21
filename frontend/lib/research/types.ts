export interface ResearchSummaryJson {
  model_name?: string
  model_config_id?: number
  date_from?: string
  date_to?: string
  candidates?: number
  same_day_combo_count?: number
  same_day_combo_roi?: number
  best_strategy?: string
  best_strategy_combo_count?: number
  best_strategy_roi?: number
  best_strategy_stake?: number
  best_strategy_pnl?: number
  best_strategy_return?: number
  random_label?: string
  random_roi_avg?: number
  model_roi_percentile_vs_random?: number | null
  full_market_random_roi_avg?: number | null
  full_market_model_roi_percentile?: number | null
  constrained_random_roi_avg?: number | null
  constrained_model_roi_percentile?: number | null
  strategy_rules?: Record<string, unknown>
  [key: string]: unknown
}

export interface ResearchArtifact {
  id: number
  run_id: number
  artifact_type: string
  label: string
  payload_json: Record<string, unknown>
}

export interface ResearchRun {
  id: number
  name: string
  base_model_config_id: number | null
  date_from: string
  date_to: string
  random_seed: number
  random_trials: number
  status: string
  summary_json: ResearchSummaryJson | null
  report_path: string | null
  created_at: string | null
}

export interface ResearchRunDetail extends ResearchRun {
  artifacts: Record<string, ResearchArtifact[]>
}

export interface ResearchTicketLeg {
  match_id: number
  match_date?: string
  league: string
  home_team: string
  away_team: string
  bet_type: 'draw' | 'handicap_draw'
  bet_label: string
  handicap_value: number | null
  odds: number
  is_hit: boolean
  result_label: string
  total_score: number
}

export interface ResearchTicket {
  strategy: string
  ticket_date: string
  combo_odds: number
  stake?: number
  is_hit: boolean
  pnl: number
  group_type?: string | null
  control_label?: string | null
  legs: ResearchTicketLeg[]
}

export interface ResearchTicketGroupSummary {
  ticket_count: number
  stake: number
  returns: number
  pnl: number
  roi: number
  max_hit_streak?: number
  max_miss_streak?: number
}

export interface ResearchTicketGroup {
  group_key: string
  title: string
  description: string
  summary: ResearchTicketGroupSummary
  tickets: ResearchTicket[]
}

export interface GenerateComboResearchPayload {
  date_from: string
  date_to: string
  model_name?: string
  random_trials?: number
  random_seed?: number
}

export interface GenerateComboResearchResponse {
  run_id: number
  report_path: string
  score_summary: {
    rows: number
    candidates: number
    portfolio: number
    scored_matches: number
    recommended_scores: number
    draw_scores: number
    handicap_draw_scores: number
    replaced_old_scores: number
  }
  research_summary: ResearchSummaryJson
}
