import type { OperationType } from "../journal/types"

export type WorkerRole =
  | "farm_manager"
  | "agronomist"
  | "irrigation_lead"
  | "scout"
  | "operator"
  | "owner"
  | "other"

export type WorkerKind = "permanent" | "seasonal"

export const WORKER_ROLES: WorkerRole[] = [
  "farm_manager",
  "agronomist",
  "irrigation_lead",
  "scout",
  "operator",
  "owner",
  "other",
]

export const WORKER_KINDS: WorkerKind[] = ["permanent", "seasonal"]

export type Worker = {
  id: string
  farm_id: string
  name: string
  role: WorkerRole
  kind: WorkerKind
  phone: string | null
  active: boolean
  version: number
  created_at: string
  updated_at: string
}

export type WorkerList = {
  workers: Worker[]
}

export type AttendanceItem = {
  worker_id: string
  worker_name: string
  present: boolean
  hours: string | null
  note: string | null
  source: "entered"
}

export type AttendanceDay = {
  date: string
  items: AttendanceItem[]
}

export type AttendanceSummaryRow = {
  worker_id: string
  worker_name: string
  days_present: number
  hours: string
  source: "calculated"
}

export type AttendanceSummary = {
  date_from: string
  date_to: string
  workers: AttendanceSummaryRow[]
}

export type NormCrop = {
  id: string
  code: string
  name: { fr: string; ar: string; en: string }
}

export type LabourNorm = {
  operation_type: OperationType
  crop: NormCrop | null
  total_hours: string
  total_area_ha: string
  h_per_ha: string | null
  operations_count: number
  source: "calculated"
}

export type LabourNormList = {
  season: number
  rows: LabourNorm[]
}

export type MachineType = "tractor" | "sprayer" | "combine" | "other"
export type MachineStatus = "ok" | "repair"

export const MACHINE_TYPES: MachineType[] = ["tractor", "sprayer", "combine", "other"]
export const MACHINE_STATUSES: MachineStatus[] = ["ok", "repair"]

export type Machine = {
  id: string
  farm_id: string
  type: MachineType
  name: string
  status: MachineStatus
  engine_hours_reading: string | null
  reading_date: string | null
  version: number
  created_at: string
  updated_at: string
}

export type MachineList = {
  machines: Machine[]
}

export type MachineBrief = {
  id: string
  name: string
}

export type MaintenanceDue = {
  due_by_hours: boolean
  due_by_date: boolean
  next_due_h: string | null
  next_due_date: string | null
  overdue: boolean
  source: "calculated"
}

export type MaintenanceItem = {
  id: string
  farm_id: string
  machine: MachineBrief
  task: string
  interval_h: string | null
  interval_days: number | null
  last_done_date: string | null
  last_done_h: string | null
  due: MaintenanceDue
  version: number
  created_at: string
  updated_at: string
}

export type MaintenanceList = {
  items: MaintenanceItem[]
}

export type MachineSeasonUse = {
  season: number
  uses_count: number
  hours: string
  fuel_l: string
  area_ha: string
  avg_work_rate_ha_h: string | null
  source: "calculated"
}

export type MachineDetail = Machine & {
  current_engine_hours: string | null
  current_engine_hours_source: "calculated" | null
  uses_this_season: MachineSeasonUse
  maintenance: MaintenanceItem[]
}
