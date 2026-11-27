import { ApiError } from "../../lib/api"

const OPERATION_ERRORS: Record<string, string> = {
  "operations.product_name_required": "journal.errors.productNameRequired",
  "operations.product_name_taken": "journal.errors.productNameTaken",
  "operations.product_in_use": "journal.errors.productInUse",
  "operations.block_not_in_farm": "journal.errors.block",
  "operations.valve_not_in_block": "journal.errors.valve",
  "operations.net_area_required": "journal.errors.netArea",
  "operations.valve_area_required": "journal.errors.valveArea",
  "operations.product_not_in_farm": "journal.errors.productMissing",
  "operations.rate_must_be_positive": "journal.errors.rate",
  "operations.water_required": "journal.errors.water",
  "operations.area_must_be_positive": "journal.errors.netArea",
  "operations.rate_basis_invalid": "journal.errors.basis",
  "labour.headcount_mismatch": "journal.errors.labourHeadcount",
  "labour.headcount_invalid": "journal.errors.labourHeadcount",
  "labour.workers_required": "journal.errors.labourWorkersRequired",
  "labour.worker_not_in_farm": "journal.errors.labourWorkerNotInFarm",
  "labour.hours_invalid": "journal.errors.labourHours",
  "equipment.machine_duplicate": "journal.errors.machineDuplicate",
  "equipment.machine_not_in_farm": "journal.errors.machineNotInFarm",
  "equipment.hours_invalid": "journal.errors.machineHours",
  "equipment.fuel_invalid": "journal.errors.machineFuel",
  "operation.not_found": "journal.errors.missing",
  "product.not_found": "journal.errors.missing",
  "conflict.version": "journal.errors.conflict",
  "conflict.version_required": "journal.errors.conflict",
}

export function journalErrorKey(code: string): string {
  return OPERATION_ERRORS[code] ?? "journal.errors.save"
}

export function journalErrorState(error: unknown): {
  form: string | null
  fields: Record<string, string>
} {
  if (!(error instanceof ApiError)) return { form: "journal.errors.save", fields: {} }
  if (error.status === 409 || error.status === 428) {
    return { form: "journal.errors.conflict", fields: {} }
  }
  const fields: Record<string, string> = {}
  for (const [field, code] of Object.entries(error.fields)) {
    const leaf = field.split(".").pop() ?? field
    fields[leaf] = journalErrorKey(code)
  }
  if (Object.keys(fields).length > 0) return { form: null, fields }
  return { form: journalErrorKey(error.code), fields: {} }
}