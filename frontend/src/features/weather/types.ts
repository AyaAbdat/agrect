export type NowOut = {
  temp_c: string | null
  rh_pct: string | null
  wind_ms: string | null
  gust_ms: string | null
  wind_dir_deg: string | null
  rad_wm2: string | null
  dewpoint_c: string | null
  vpd_kpa: string | null
  rain_mm: string | null
  et0_mm: string | null
  rad_sum_jcm2_today: string | null
  ts: string
  issued_at: string | null
  stale: boolean
  provider: string
  source: string
  dewpoint_source: string
  vpd_source: string
  rad_sum_source: string
}

export type ForecastHour = {
  ts: string
  temp_c: string | null
  rh_pct: string | null
  rain_mm: string | null
  rain_prob_pct: string | null
  wind_ms: string | null
  gust_ms: string | null
  wind_dir_deg: string | null
  rad_wm2: string | null
  et0_mm: string | null
  dewpoint_c: string | null
  vpd_kpa: string | null
  is_forecast: boolean
  source: string
}

export type ForecastDay = {
  date: string
  tmin_c: string | null
  tmax_c: string | null
  rain_mm: string | null
  rain_prob_pct: string | null
  et0_mm: string | null
  frost_h: number | null
  heat_h: number | null
  is_forecast: boolean
  source: string
}

export type ForecastOut = {
  issued_at: string | null
  stale: boolean
  hourly: ForecastHour[]
  daily: ForecastDay[]
}

export type DailyRow = {
  date: string
  tmin_c: string | null
  tmax_c: string | null
  tmean_c: string | null
  rh_min: string | null
  rh_max: string | null
  rain_mm: string | null
  et0_mm: string | null
  vpd_max_kpa: string | null
  frost_h: number | null
  heat_h: number | null
  chill_h: number | null
  hours_count: number
  is_forecast: boolean
  source: string
}

export type DailyOut = {
  issued_at: string | null
  stale: boolean
  days: DailyRow[]
}

export type Thresholds = {
  frost_c: string | null
  heat_c: string | null
  vpd_limit_kpa: string | null
  chill_season_start: string | null
}

export type GddMethod = "average" | "single_sine"

export type GddSetting = {
  crop_id: string
  base_c: string | null
  upper_c: string | null
  method: GddMethod | null
  start_date: string | null
}

export type GddSettingListItem = {
  crop_id: string
  code: string
  name: { fr: string; ar: string; en: string }
  base_c: string
  upper_c: string | null
  method: GddMethod
  start_date: string | null
}

export type DegreeDayPoint = {
  date: string
  gdd: string | null
  gdd_cum: string | null
  is_forecast: boolean
}

export type DegreeDays = {
  setting: {
    base_c: string
    upper_c: string | null
    method: GddMethod
    start_date: string | null
  } | null
  from: string
  data_from: string | null
  days: DegreeDayPoint[]
  gdd_total: string | null
  chill: { season_start: string | null; hours_total: number | null }
  frost_h_total: number | null
  heat_h_total: number | null
  label: "calculated" | "not_enough_data"
  issued_at: string | null
  stale: boolean
}

export type FarmWeather = {
  id: string
  lat: string | null
  lon: string | null
  timezone: string
}

export type HourPoint = {
  label: string
  temp: number | null
  rain: number | null
  rh: number | null
  wind: number | null
}

export type HistoryPoint = {
  label: string
  tmin: number | null
  tmax: number | null
  rain: number | null
}

export type GddPoint = {
  label: string
  past: number | null
  forecast: number | null
  daily: number | null
}
