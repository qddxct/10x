export interface WeightsJson {
  euro: number
  asian: number
  goals: number
  intent: number
  compression: number
  team_stats: number
  [k: string]: number
}

export interface KellyBand {
  min_score: number
  max_score: number
  kelly_pct: number
}

export interface ModelConfig {
  id: number
  name: string
  created_by: number | null
  parent_id: number | null
  is_active: boolean
  weights_json: WeightsJson
  thresholds_json: Record<string, number | string>
  kelly_bands_json: Record<string, KellyBand>
  scrape_schedule_json: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ModelConfigListResponse {
  items: ModelConfig[]
  total: number
}

export interface ModelConfigCreatePayload {
  name: string
  weights_json: WeightsJson
  thresholds_json: Record<string, number | string>
  kelly_bands_json: Record<string, KellyBand>
  scrape_schedule_json?: Record<string, unknown> | null
}

export interface ModelConfigUpdatePayload {
  name?: string
  weights_json?: WeightsJson
  thresholds_json?: Record<string, number | string>
  kelly_bands_json?: Record<string, KellyBand>
  scrape_schedule_json?: Record<string, unknown> | null
}

export interface ModelConfigActivateResponse extends ModelConfig {
  scores_recomputed: number
}
