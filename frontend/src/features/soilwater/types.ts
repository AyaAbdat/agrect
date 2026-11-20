import type { LocalizedName } from "../blocks/types"

export type FarmClock = {
  timezone: string
}

export type SoilClass = {
  id: string
  code: string
  name: LocalizedName
}

export type SoilProfile = {
  texture_mode: "class" | "percent" | null
  texture_class: SoilClass | null
  sand_pct: string | null
  silt_pct: string | null
  clay_pct: string | null
  theta_fc: string | null
  theta_wp: string | null
  root_depth_m: string | null
  dry_down_pct: string | null
  full_on: string | null
  organic_matter_pct: string | null
  compaction: "loose" | "normal" | "compacted" | null
  infiltration_mm_h: string | null
  infiltration_source: "texture" | "ring_test" | null
  taw_mm: string | null
  raw_mm: string | null
  water_left_mm: string | null
  irrigate_below_mm: string | null
  label: "calculated" | "not_enough_data"
  version: number | null
}

export type SoilTexture = SoilClass & {
  theta_fc_min: string | null
  theta_fc_max: string | null
  theta_wp_min: string | null
  theta_wp_max: string | null
  theta_fc: string | null
  theta_wp: string | null
  citation: string | null
}

export type IrrigationSettings = {
  efficiency: string | null
  kc: string | null
  kc_source: "suggested" | "entered" | null
  version: number | null
}

export type Dose = {
  net_mm: string | null
  gross_mm: string | null
  run_time_min: string | null
  volume_m3: string | null
}

export type IrrigationToday = {
  date: string
  depletion_mm: string | null
  taw_mm: string | null
  raw_mm: string | null
  water_left_mm: string | null
  irrigate_below_mm: string | null
  etc_today_mm: string | null
  status: "ok" | "irrigate_soon" | "no_data"
  refill: Dose
  maintain: Dose
  recommended: "refill" | "maintain"
  label: "calculated" | "no_data"
  missing: string[]
}

export type IrrigationEvent = {
  id: string
  block_id: string
  valve_ids: string[]
  start_at: string
  duration_min: number
  depth_mm: string
  volume_m3: string
  soil_mm: string
  runoff_mm: string
  source: "calculated" | "measured"
  version: number
}

export type IrrigationTotals = {
  count: number
  depth_mm: string
  volume_m3: string
  soil_mm: string
}

export type IrrigationEvents = {
  events: IrrigationEvent[]
  totals: IrrigationTotals
}

export type IrrigationPreview = {
  depth_mm: string
  volume_m3: string
  soil_mm: string
  runoff_mm: string
  source: "calculated"
}

export type SoilFeel = "dry" | "slightly_moist" | "moist" | "wet"
export type DepthBand = "0_30" | "30_60"

export type SoilCheckPreview = {
  reset_depletion_mm: string
  water_left_mm: string
  pct_of_taw: string
}

export type BalanceRow = {
  date: string
  etc_mm: string | null
  rain_mm: string | null
  irrigation_soil_mm: string | null
  taw_mm: string | null
  water_left_mm: string | null
  irrigate_below_mm: string | null
  status: "ok" | "irrigate_soon" | "no_data"
  is_forecast: boolean
}

export type WaterBalance = {
  rows: BalanceRow[]
  notes: string[]
}

export type ForecastRain = {
  daily: { date: string; rain_mm: string | null }[]
}

export type FarmIrrigationToday = {
  date: string
  blocks: (IrrigationToday & { block_id: string })[]
}
