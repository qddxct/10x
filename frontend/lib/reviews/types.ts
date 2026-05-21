export interface ReviewItem {
  score_id: number
  match_id: number
  match_date: string
  match_round: string | null
  sporttery_match_id: string | null
  sporttery_url: string | null
  league_name: string | null
  home_team: string
  away_team: string
  home_score: number | null
  away_score: number | null
  result: string | null
  handicap_result: string | null
  total_score: number
  bet_type: string | null
  bet_odds: string | number | null
  kelly_pct: string | number | null
  is_recommended: boolean
  actual_hit: boolean | null
  suggested_actual_hit: boolean | null
  bet_amount: string | number | null
  notes: string | null
  model_config_id: number
  model_name: string | null
  user_id: number | null
  updated_at: string
}

export interface ReviewListResponse {
  items: ReviewItem[]
  total: number
}

export interface ReviewUpdatePayload {
  actual_hit?: boolean | null
  bet_amount?: number | string | null
  notes?: string | null
  expected_updated_at?: string | null
}

export interface ReviewFilters {
  date_from?: string
  date_to?: string
  only_recommended?: boolean
  model_config_id?: number
}
