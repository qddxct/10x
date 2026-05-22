export interface ComboRecommendationLeg {
  score_id: number
  match_id: number
  match_round: string | null
  match_date: string | null
  league_name: string | null
  home_team: string
  away_team: string
  bet_type: 'draw' | 'handicap_draw' | null
  bet_odds: string | number | null
  total_score: number
  sporttery_url: string | null
  home_score: number | null
  away_score: number | null
  result: string | null
  handicap_result: string | null
  hit: boolean | null
}

export interface ComboRecommendation {
  id: number
  recommendation_date: string
  model_config_id: number
  model_name: string | null
  rank: number
  title: string
  combo_odds: string | number | null
  avg_score: number
  status: 'pending' | 'won' | 'lost'
  hit: boolean | null
  created_at: string
  legs: ComboRecommendationLeg[]
}

export interface ComboRecommendationListResponse {
  items: ComboRecommendation[]
  total: number
}

export interface ComboSnapshotResult {
  model_config_id: number
  recommendation_date: string
  created: number
  items: ComboRecommendation[]
}
