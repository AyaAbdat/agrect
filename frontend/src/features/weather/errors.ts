const GDD_ERRORS: Record<string, string> = {
  "gdd.base_out_of_range": "weather.errors.baseRange",
  "gdd.upper_not_above_base": "weather.errors.upperAbove",
  "gdd.upper_out_of_range": "weather.errors.upperRange",
}

const THRESHOLD_ERRORS: Record<string, string> = {
  "weather.frost_c_out_of_range": "weather.errors.frostRange",
  "weather.heat_c_out_of_range": "weather.errors.heatRange",
  "weather.vpd_limit_kpa_out_of_range": "weather.errors.vpdRange",
}

export function gddErrorKey(code: string): string {
  return GDD_ERRORS[code] ?? "weather.errors.save"
}

export function thresholdErrorKey(code: string): string {
  return THRESHOLD_ERRORS[code] ?? "weather.errors.save"
}
