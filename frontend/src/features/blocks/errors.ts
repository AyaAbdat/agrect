const BLOCK_ERROR_KEYS: Record<string, string> = {
  "block.name_required": "blocks.errors.nameRequired",
  "block.name_taken": "blocks.errors.nameTaken",
  "block.net_area_must_be_positive": "blocks.errors.netPositive",
  "block.net_area_exceeds_gross": "blocks.errors.netExceedsGross",
  "block.outline_invalid": "blocks.errors.outlineInvalid",
  "block.row_line_invalid": "blocks.errors.rowLineInvalid",
  "block.row_line_outside": "blocks.errors.rowLineOutside",
  "catalog.crop_not_found": "blocks.errors.cropNotFound",
  "catalog.variety_not_found": "blocks.errors.varietyNotFound",
  "block.training_system_mismatch": "blocks.errors.trainingMismatch",
  "record.reason_required": "blocks.errors.reasonRequired",
  "registry.valve_rows_invalid": "blocks.errors.valveRowsInvalid",
  "registry.valve_rows_overlap": "blocks.errors.valveRowsOverlap",
}

export function blockErrorKey(code: string): string {
  const known = BLOCK_ERROR_KEYS[code]
  if (known !== undefined) return known
  if (code.startsWith("registry.") && code.endsWith("_must_be_positive")) {
    return "blocks.errors.positive"
  }
  return "blocks.errors.save"
}

export function isPositiveDecimal(value: string): boolean {
  const normalized = value.trim().replace(",", ".")
  if (!/^\d+(\.\d+)?$/.test(normalized)) return false
  const parsed = Number(normalized)
  return Number.isFinite(parsed) && parsed > 0
}

export function normalizeDecimal(value: string): string {
  return value.trim().replace(",", ".")
}

export function decimalInput(value: string | null): string {
  if (value === null) return ""
  if (!value.includes(".")) return value
  return value.replace(/0+$/, "").replace(/\.$/, "")
}
