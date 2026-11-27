import { ApiError } from "../../lib/api"

const TEAM_ERRORS: Record<string, string> = {
  "labour.worker_name_required": "team.errors.nameRequired",
  "labour.worker_name_taken": "team.errors.nameTaken",
  "labour.worker_in_use": "team.errors.workerInUse",
  "labour.worker_not_in_farm": "team.errors.workerNotInFarm",
  "labour.hours_invalid": "team.errors.hoursInvalid",
  "labour.range_invalid": "team.errors.rangeInvalid",
  "worker.not_found": "team.errors.notFound",
  "equipment.machine_name_required": "team.machines.errors.nameRequired",
  "equipment.machine_name_taken": "team.machines.errors.nameTaken",
  "equipment.machine_in_use": "team.machines.errors.inUse",
  "equipment.hours_invalid": "team.machines.errors.hoursInvalid",
  "equipment.task_required": "team.machines.errors.taskRequired",
  "equipment.interval_required": "team.machines.errors.intervalRequired",
  "equipment.interval_invalid": "team.machines.errors.intervalInvalid",
  "machine.not_found": "team.machines.errors.notFound",
  "maintenance.not_found": "team.machines.errors.maintenanceNotFound",
  "conflict.version": "team.errors.conflict",
  "conflict.version_required": "team.errors.conflict",
}

export function teamErrorKey(code: string): string {
  return TEAM_ERRORS[code] ?? "team.errors.save"
}

export function teamErrorState(error: unknown): {
  form: string | null
  fields: Record<string, string>
} {
  if (!(error instanceof ApiError)) return { form: "team.errors.save", fields: {} }
  if (error.status === 409 || error.status === 428) {
    if (error.code === "labour.worker_in_use") {
      return { form: "team.errors.workerInUse", fields: {} }
    }
    if (error.code === "equipment.machine_in_use") {
      return { form: "team.machines.errors.inUse", fields: {} }
    }
    return { form: "team.errors.conflict", fields: {} }
  }
  const fields: Record<string, string> = {}
  for (const [field, code] of Object.entries(error.fields)) {
    const leaf = field.split(".").pop() ?? field
    fields[leaf] = teamErrorKey(code)
  }
  if (Object.keys(fields).length > 0) return { form: null, fields }
  return { form: teamErrorKey(error.code), fields: {} }
}
