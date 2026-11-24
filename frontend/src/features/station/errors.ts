import { ApiError } from "../../lib/api"

const STATION_ERRORS: Record<string, string> = {
  "station.name_required": "station.errors.nameRequired",
  "station.name_taken": "station.errors.nameTaken",
  "station.flow_must_be_positive": "station.errors.flowPositive",
  "station.window_invalid": "station.errors.windowInvalid",
  "station.block_not_in_farm": "station.errors.blockMissing",
  "station.water_source_not_found": "station.errors.sourceMissing",
  "record.reason_required": "station.errors.reasonRequired",
  "conflict.version": "station.errors.conflict",
  "conflict.version_required": "station.errors.conflict",
}

export function stationErrorKey(code: string): string {
  return STATION_ERRORS[code] ?? "station.errors.save"
}

export function stationErrorState(error: unknown): {
  form: string | null
  fields: Record<string, string>
} {
  if (!(error instanceof ApiError)) return { form: "station.errors.save", fields: {} }
  if (error.status === 409 || error.status === 428) {
    return { form: "station.errors.conflict", fields: {} }
  }
  const fields: Record<string, string> = {}
  for (const [field, code] of Object.entries(error.fields)) {
    const leaf = field.split(".").pop() ?? field
    fields[leaf] = stationErrorKey(code)
  }
  if (Object.keys(fields).length > 0) return { form: null, fields }
  return { form: stationErrorKey(error.code), fields: {} }
}

export function positiveWire(value: string): { ok: boolean; wire: string | null; empty: boolean } {
  const trimmed = value.trim().replace(",", ".")
  if (trimmed === "") return { ok: false, wire: null, empty: true }
  if (!/^\d+(\.\d+)?$/.test(trimmed) || Number(trimmed) <= 0) {
    return { ok: false, wire: null, empty: false }
  }
  return { ok: true, wire: trimmed, empty: false }
}

export function optionalWire(value: string): { ok: true; wire: string | null } | { ok: false } {
  const trimmed = value.trim().replace(",", ".")
  if (trimmed === "") return { ok: true, wire: null }
  if (!/^\d+(\.\d+)?$/.test(trimmed)) return { ok: false }
  return { ok: true, wire: trimmed }
}
