const SOIL_ERRORS: Record<string, string> = {
  "soil.root_depth_out_of_range": "soil.errors.rootRange",
  "soil.dry_down_out_of_range": "soil.errors.dryRange",
  "soil.percent_sum_invalid": "soil.errors.percentSum",
  "catalog.soil_texture_not_found": "soil.errors.textureMissing",
  "irrigation.efficiency_out_of_range": "soil.errors.efficiencyRange",
  "irrigation.kc_out_of_range": "soil.errors.kcRange",
  "record.reason_required": "soil.errors.reasonRequired",
  "irrigation.valve_not_found": "soil.errors.valveMissing",
  "irrigation.block_not_ready": "soil.errors.blockNotReady",
  "soil.taw_missing": "soil.errors.tawMissing",
  "soil.not_enough_data": "soil.errors.tawMissing",
}

export function soilErrorKey(code: string): string {
  return SOIL_ERRORS[code] ?? "soil.errors.save"
}
