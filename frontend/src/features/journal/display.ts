import { formatNumber } from "../../lib/format"
import { asNumber } from "../weather/format"
import type {
  JournalItem,
  JournalTypeFilter,
  OperationLabour,
  OperationMachine,
  OperationType,
  OperationWarning,
  ProductUnit,
  SourceKind,
} from "./types"

const TYPE_KEYS: Record<OperationType, string> = {
  fertigation: "journal.types.fertigation",
  foliar_application: "journal.types.foliar",
  crop_protection_spray: "journal.types.treatment",
  herbicide: "journal.types.weed",
  pruning: "journal.types.pruning",
  shoot_cluster_thinning: "journal.types.thinning",
  growth_regulator: "journal.types.growthRegulator",
  girdling: "journal.types.girdling",
  leaf_removal: "journal.types.leafRemoval",
  cover_netting: "journal.types.coverNetting",
  tillage: "journal.types.tillage",
  sowing: "journal.types.sowing",
  nitrogen_application: "journal.types.nitrogen",
  other: "journal.types.other",
}

const FILTER_QUERY: Record<Exclude<JournalTypeFilter, "all" | "more">, string> = {
  fertigation: "fertigation",
  treatment: "crop_protection_spray",
  foliar: "foliar_application",
  irrigation: "irrigation",
  weed: "herbicide",
  pruning: "pruning",
  thinning: "shoot_cluster_thinning",
  harvest: "harvest",
  stages: "stage",
  scouting: "scouting",
}

const MORE_TYPES: OperationType[] = [
  "growth_regulator",
  "girdling",
  "leaf_removal",
  "cover_netting",
  "tillage",
  "sowing",
  "nitrogen_application",
  "other",
]

export function operationTypeKey(type: OperationType): string {
  return TYPE_KEYS[type]
}

export function journalTypesQuery(filter: JournalTypeFilter): string | null {
  if (filter === "all") return null
  if (filter === "more") return MORE_TYPES.join(",")
  return FILTER_QUERY[filter]
}

export function isoWeekNumber(isoDate: string): number {
  const [year, month, day] = isoDate.split("-").map(Number)
  const utc = new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1))
  const dayNum = utc.getUTCDay() || 7
  utc.setUTCDate(utc.getUTCDate() + 4 - dayNum)
  const yearStart = new Date(Date.UTC(utc.getUTCFullYear(), 0, 1))
  return Math.ceil(((utc.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
}

export function isoWeekText(isoDate: string, lang: string): string {
  return formatNumber(isoWeekNumber(isoDate), 0, lang)
}

export function itemTypeKey(item: JournalItem): string {
  if (item.kind === "irrigation") return "journal.kind.irrigation"
  if (item.kind === "harvest") return "journal.kind.harvest"
  if (item.kind === "stage") return "journal.kind.stage"
  if (item.operation_type !== null) return operationTypeKey(item.operation_type)
  return "journal.kind.operation"
}

export function sourceKey(kind: SourceKind): string {
  if (kind === "measured") return "journal.source.measured"
  if (kind === "entered") return "journal.source.entered"
  if (kind === "estimated") return "weather.estimated"
  return "weather.calculated"
}

export function sourceBadgeClass(kind: SourceKind): string {
  if (kind === "estimated") return "bg-[#E5E7EB] text-mut"
  if (kind === "entered") return "bg-mint text-pri"
  if (kind === "measured") return "bg-[#DBEAFE] text-[#1D4ED8]"
  return "bg-mint text-pri"
}

export function unitLabel(unit: ProductUnit, t: (key: string) => string): string {
  return t(`journal.units.${unit}`)
}

export function scaleQty(
  value: string,
  unit: ProductUnit,
): { qty: number; unit: ProductUnit } | null {
  const parsed = asNumber(value)
  if (parsed === null) return null
  if (unit === "ml" && parsed !== 0 && parsed % 1000 === 0) {
    return { qty: parsed / 1000, unit: "l" }
  }
  if (unit === "g" && parsed !== 0 && parsed % 1000 === 0) {
    return { qty: parsed / 1000, unit: "kg" }
  }
  return { qty: parsed, unit }
}

export function totalOnAreaText(
  totalQty: string,
  totalUnit: ProductUnit | null,
  areaHa: string,
  lang: string,
  t: (key: string, opts?: Record<string, string>) => string,
): string {
  if (totalUnit === null) return "—"
  const scaled = scaleQty(totalQty, totalUnit)
  if (scaled === null) return "—"
  const qty = formatNumber(scaled.qty, scaled.unit === "l" || scaled.unit === "kg" ? 2 : 0, lang)
  const area = formatNumber(asNumber(areaHa), 2, lang)
  return t("journal.totalOnArea", {
    qty,
    unit: unitLabel(scaled.unit, t),
    area,
  })
}

export function groupByOperationType(items: JournalItem[]): { key: string; items: JournalItem[] }[] {
  const buckets = new Map<string, JournalItem[]>()
  for (const item of items) {
    const key =
      item.kind === "operation" && item.operation_type !== null ? item.operation_type : item.kind
    const list = buckets.get(key) ?? []
    list.push(item)
    buckets.set(key, list)
  }
  return [...buckets.entries()].map(([key, rows]) => ({ key, items: rows }))
}

export function waterLitersFromM3(m3Text: string): string | null {
  const trimmed = m3Text.trim().replace(",", ".")
  if (trimmed === "" || !/^-?\d+(\.\d+)?$/.test(trimmed)) return null
  const m3 = Number(trimmed)
  if (!Number.isFinite(m3) || m3 <= 0) return null
  return String(m3 * 1000)
}

export function m3FromWaterLiters(lHa: string | null | undefined): string {
  if (lHa === null || lHa === undefined || lHa === "") return ""
  const parsed = asNumber(lHa)
  if (parsed === null) return ""
  return String(parsed / 1000)
}

export function warningKey(warning: OperationWarning, index: number): string {
  if (warning.code === "labour.worker_inactive") {
    return `${warning.code}-${warning.worker ?? warning.worker_name ?? warning.product ?? index}`
  }
  if (warning.code === "equipment.machine_in_repair") {
    return `${warning.code}-${warning.machine ?? index}`
  }
  return `${warning.code}-${warning.product}`
}

export function warningText(
  warning: OperationWarning,
  t: (key: string, opts?: Record<string, string>) => string,
): string {
  if (warning.code === "labour.worker_inactive") {
    const worker = warning.worker ?? warning.worker_name ?? warning.product ?? ""
    return worker !== ""
      ? t("journal.workerInactive", { worker })
      : t("journal.workerInactiveGeneric")
  }
  if (warning.code === "equipment.machine_in_repair") {
    const machine = warning.machine ?? ""
    return machine !== ""
      ? t("journal.machineInRepair", { machine })
      : t("journal.machineInRepairGeneric")
  }
  return t("journal.unitMismatch", { product: warning.product })
}

export function labourDetailsText(
  labour: OperationLabour | null | undefined,
  lang: string,
  t: (key: string, opts?: Record<string, string>) => string,
): string | null {
  if (labour === null || labour === undefined) return null
  return t("journal.labourDetails", {
    count: formatNumber(labour.headcount, 0, lang),
    hours: formatNumber(asNumber(labour.total_hours), 1, lang),
  })
}

export function machinesDetailsText(
  machines: OperationMachine[] | null | undefined,
  lang: string,
  t: (key: string, opts?: Record<string, string>) => string,
): string | null {
  if (machines === null || machines === undefined || machines.length === 0) return null
  return machines
    .map((item) => {
      const hours = formatNumber(asNumber(item.hours), 1, lang)
      if (item.fuel_l !== null) {
        return t("journal.machineDetailsFuel", {
          machine: item.name,
          hours,
          fuel: formatNumber(asNumber(item.fuel_l), 1, lang),
        })
      }
      return t("journal.machineDetails", {
        machine: item.name,
        hours,
      })
    })
    .join(" · ")
}