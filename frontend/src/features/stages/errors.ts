const FIELD_ERRORS: Record<string, string> = {
  "phenology.observed_in_future": "stages.errors.future",
  "phenology.before_season_start": "stages.errors.beforeStart",
  "phenology.stage_not_found": "stages.errors.stage",
  "phenology.season_start_required": "stages.errors.start",
  "phenology.dd_must_be_positive": "stages.errors.positive",
  "phenology.base_mismatch": "stages.errors.base",
  "phenology.duplicate_stage": "stages.errors.duplicate",
}

export function stageErrorKey(code: string): string {
  return FIELD_ERRORS[code] ?? "stages.errors.save"
}
