import { formatNumber } from "../../lib/format"
import type { Operation, OperationType } from "../journal/types"
import { asNumber } from "../weather/format"
import type { HarvestBasis, HarvestEntry, HarvestUnit, PreharvestWarning } from "./types"

const SPRAY_TYPES = new Set<OperationType>([
  "crop_protection_spray",
  "herbicide",
  "growth_regulator",
  "foliar_application",
])

function coversValve(operation: Operation, valveId: string | null): boolean {
  if (valveId === null || valveId === "") return true
  if (operation.valve_ids.length === 0) return true
  return operation.valve_ids.includes(valveId)
}

export function previewPreharvestWarning(
  operations: Operation[],
  harvestDate: string,
  valveId: string | null,
): PreharvestWarning | null {
  const harvest = new Date(`${harvestDate}T12:00:00Z`)
  let best: PreharvestWarning | null = null
  let bestClear: Date | null = null
  for (const row of operations) {
    if (!SPRAY_TYPES.has(row.type)) continue
    if (row.date > harvestDate) continue
    if (!coversValve(row, valveId)) continue
    const phi = row.safety?.preharvest_interval_days
    if (phi === null || phi === undefined) continue
    const spray = new Date(`${row.date}T12:00:00Z`)
    const daysSince = Math.floor((harvest.getTime() - spray.getTime()) / 86400000)
    if (daysSince >= phi) continue
    const clearOn = new Date(spray.getTime() + phi * 86400000)
    if (bestClear !== null && clearOn <= bestClear) continue
    const product = row.products[0]?.product_name ?? row.target ?? "—"
    best = {
      product,
      spray_date: row.date,
      days_since: daysSince,
      days_needed: phi,
    }
    bestClear = clearOn
  }
  return best
}

type Translate = (key: string, options?: Record<string, string | number>) => string

export function massText(value: string | null | undefined, lang: string): string {
  return formatNumber(asNumber(value), 0, lang)
}

export function densityText(value: string | null | undefined, lang: string): string {
  return formatNumber(asNumber(value), 0, lang)
}

export function areaText(value: string | null | undefined, lang: string): string {
  return formatNumber(asNumber(value), 2, lang)
}

export function quantityText(value: string, unit: HarvestUnit, lang: string): string {
  const digits = unit === "t" ? 2 : 0
  return formatNumber(asNumber(value), digits, lang)
}

export function unitLabel(unit: HarvestUnit, t: Translate): string {
  return t(`harvest.unit.${unit}`)
}

export function basisLabel(
  entry: Pick<HarvestEntry, "basis" | "valve_id" | "basis_count">,
  t: Translate,
  valveName: string | null,
): string {
  if (entry.basis === "block") return t("harvest.basis.block")
  if (entry.basis === "valve") {
    return t("harvest.basis.valveNamed", { name: valveName ?? t("common.missing") })
  }
  if (entry.basis === "rows") {
    return t("harvest.basis.rowsCount", {
      count: formatNumber(asNumber(entry.basis_count), 0, "en"),
    })
  }
  return t("harvest.basis.treesCount", {
    count: formatNumber(asNumber(entry.basis_count), 0, "en"),
  })
}

export function seasonYears(current: number): number[] {
  return [current, current - 1, current - 2, current - 3, current - 4]
}

export function entryInSeason(entry: HarvestEntry, season: number): boolean {
  return entry.date.startsWith(`${season}-`)
}

export function needsUnitWeight(unit: HarvestUnit): boolean {
  return unit === "crate" || unit === "bin"
}

export function basisNeedsCount(basis: HarvestBasis): boolean {
  return basis === "rows" || basis === "trees"
}
