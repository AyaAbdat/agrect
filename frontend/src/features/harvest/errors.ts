import { ApiError } from "../../lib/api"

const HARVEST_ERRORS: Record<string, string> = {
  "harvest.quantity_must_be_positive": "harvest.errors.quantityPositive",
  "harvest.unit_weight_required": "harvest.errors.unitWeight",
  "harvest.unit_invalid": "harvest.errors.unit",
  "harvest.valve_required": "harvest.errors.valveRequired",
  "harvest.valve_not_in_block": "harvest.errors.valveMissing",
  "harvest.net_area_required": "harvest.errors.netArea",
  "harvest.rows_required": "harvest.errors.rowsRequired",
  "harvest.rows_total_missing": "harvest.errors.rowsTotal",
  "harvest.rows_exceed_total": "harvest.errors.rowsExceed",
  "harvest.trees_required": "harvest.errors.treesRequired",
  "harvest.trees_per_ha_missing": "harvest.errors.treesPerHa",
  "harvest.basis_invalid": "harvest.errors.basis",
  "harvest.kg_must_be_positive": "harvest.errors.quantityPositive",
  "harvest.area_must_be_positive": "harvest.errors.netArea",
  "harvest.season_invalid": "harvest.errors.season",
  "harvest.not_found": "harvest.errors.missing",
  "harvest.size_grade_sum_invalid": "harvest.errors.sizeGradeSum",
  "conflict.version": "harvest.errors.conflict",
  "conflict.version_required": "harvest.errors.conflict",
}

export function harvestErrorKey(code: string): string {
  return HARVEST_ERRORS[code] ?? "harvest.errors.save"
}

export function harvestErrorState(error: unknown): {
  form: string | null
  fields: Record<string, string>
} {
  if (!(error instanceof ApiError)) return { form: "harvest.errors.save", fields: {} }
  if (error.status === 409 || error.status === 428) {
    return { form: "harvest.errors.conflict", fields: {} }
  }
  const fields: Record<string, string> = {}
  for (const [field, code] of Object.entries(error.fields)) {
    const leaf = field.split(".").pop() ?? field
    fields[leaf] = harvestErrorKey(code)
  }
  if (Object.keys(fields).length > 0) return { form: null, fields }
  return { form: harvestErrorKey(error.code), fields: {} }
}
