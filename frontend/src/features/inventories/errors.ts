import { ApiError } from "../../lib/api"

const CODES: Record<string, string> = {
  "inputs.price_must_be_positive": "inventories.errors.price",
  "inputs.product_required": "inventories.errors.product",
  "inputs.product_not_allowed": "inventories.errors.product",
  "inputs.product_not_in_farm": "inventories.errors.product",
  "inputs.move_kind_not_allowed": "inventories.errors.kind",
  "inputs.use_not_deletable": "inventories.errors.useDelete",
  "record.reason_required": "inventories.errors.reason",
  "conflict.version": "inventories.errors.conflict",
  "conflict.version_required": "inventories.errors.conflict",
  "price.not_found": "inventories.errors.missing",
  "stock_move.not_found": "inventories.errors.missing",
}

export function inventoryErrorKey(code: string): string {
  return CODES[code] ?? "inventories.errors.save"
}

export function inventoryErrorState(error: unknown): {
  form: string | null
  fields: Record<string, string>
} {
  if (!(error instanceof ApiError)) return { form: "inventories.errors.save", fields: {} }
  if (error.status === 409 || error.status === 428) {
    return { form: "inventories.errors.conflict", fields: {} }
  }
  const fields: Record<string, string> = {}
  for (const [field, code] of Object.entries(error.fields)) {
    const leaf = field.split(".").pop() ?? field
    fields[leaf] = inventoryErrorKey(code)
  }
  if (Object.keys(fields).length > 0) return { form: null, fields }
  return { form: inventoryErrorKey(error.code), fields: {} }
}
