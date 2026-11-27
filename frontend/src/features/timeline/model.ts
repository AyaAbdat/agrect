import type { BlockListItem } from "../blocks/types"
import type { HarvestEntry } from "../harvest/types"
import { isoWeekNumber } from "../journal/display"
import type { JournalItem, OperationType } from "../journal/types"
import type { BlockStages, StageName } from "../stages/types"

export type TimelineSpan = "this" | "two"

export type CropPalette = {
  solid: string
  light: string
  border: string
}

export type TimelineYearBar = {
  year: number
  startPct: number
  endPct: number
  splitPct: number | null
}

export type TimelineStageMarker = {
  id: string
  code: string
  name: StageName
  date: string
  xPct: number
}

export type TimelineHarvestMarker = {
  id: string
  date: string
  passNo: number
  kg: string
  xPct: number
}

export type TimelineOpMarker = {
  id: string
  date: string
  title: string
  details: string | null
  operationType: OperationType | null
  color: string
  xPct: number
}

export type TimelineIrrigationBin = {
  key: string
  year: number
  week: number
  count: number
  startPct: number
  widthPct: number
}

export type TimelineRowData = {
  block: BlockListItem
  palette: CropPalette
  bars: TimelineYearBar[]
  stages: TimelineStageMarker[]
  harvests: TimelineHarvestMarker[]
  operations: TimelineOpMarker[]
  irrigations: TimelineIrrigationBin[]
  partialError: boolean
  loading: boolean
}

const CROP_PALETTES: Record<string, CropPalette> = {
  table_grape: { solid: "#7C3AED", light: "#DDD6FE", border: "#6D28D9" },
  olive: { solid: "#2D6A4F", light: "#D8F3DC", border: "#1B4332" },
  apple: { solid: "#DC2626", light: "#FECACA", border: "#B91C1C" },
  pear: { solid: "#65A30D", light: "#ECFCCB", border: "#4D7C0F" },
  wheat: { solid: "#D97706", light: "#FEF3C7", border: "#B45309" },
  barley: { solid: "#B45309", light: "#FDE68A", border: "#92400E" },
  citrus: { solid: "#EA580C", light: "#FFEDD5", border: "#C2410C" },
}

const FALLBACK_PALETTES: CropPalette[] = [
  { solid: "#0D9488", light: "#CCFBF1", border: "#0F766E" },
  { solid: "#2563EB", light: "#DBEAFE", border: "#1D4ED8" },
  { solid: "#059669", light: "#D1FAE5", border: "#047857" },
  { solid: "#9333EA", light: "#F3E8FF", border: "#7E22CE" },
]

const DEFAULT_PALETTE: CropPalette = {
  solid: "#40916C",
  light: "#D8F3DC",
  border: "#2D6A4F",
}

export const OP_COLORS = {
  nutrition: "#2563EB",
  protection: "#DC2626",
  foliar: "#9333EA",
  canopy: "#D97706",
  other: "#4B5563",
} as const

export function cropPalette(cropCode: string | null | undefined): CropPalette {
  if (cropCode === null || cropCode === undefined || cropCode === "") {
    return DEFAULT_PALETTE
  }
  const direct = CROP_PALETTES[cropCode]
  if (direct !== undefined) return direct
  let hash = 0
  for (let i = 0; i < cropCode.length; i += 1) {
    hash = (hash * 31 + cropCode.charCodeAt(i)) >>> 0
  }
  return FALLBACK_PALETTES[hash % FALLBACK_PALETTES.length] ?? DEFAULT_PALETTE
}

export function operationColor(type: OperationType | null): string {
  if (type === "fertigation" || type === "nitrogen_application") {
    return OP_COLORS.nutrition
  }
  if (type === "crop_protection_spray" || type === "herbicide") {
    return OP_COLORS.protection
  }
  if (type === "foliar_application" || type === "growth_regulator") {
    return OP_COLORS.foliar
  }
  if (
    type === "pruning" ||
    type === "shoot_cluster_thinning" ||
    type === "leaf_removal" ||
    type === "girdling" ||
    type === "cover_netting"
  ) {
    return OP_COLORS.canopy
  }
  return OP_COLORS.other
}

export function monthLabels(lang: string): string[] {
  const formatter = new Intl.DateTimeFormat(`${lang}-u-nu-latn`, {
    month: "short",
    timeZone: "UTC",
  })
  return Array.from({ length: 12 }, (_, index) =>
    formatter.format(new Date(Date.UTC(2026, index, 15, 12))),
  )
}

function parseIsoParts(isoDate: string): [number, number, number] | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate)
  if (match === null) return null
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  if (month < 1 || month > 12 || day < 1 || day > 31) return null
  return [year, month, day]
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate()
}

function positionPct(
  isoDate: string,
  years: number[],
  dayOffset: number,
): number | null {
  const parts = parseIsoParts(isoDate)
  if (parts === null) return null
  const [year, month, day] = parts
  const yearIndex = years.indexOf(year)
  if (yearIndex === -1) return null
  const dim = daysInMonth(year, month)
  const frac = Math.min(1, Math.max(0, (day - 1 + dayOffset) / dim))
  const totalMonths = years.length * 12
  return ((yearIndex * 12 + (month - 1) + frac) / totalMonths) * 100
}

export function dateToAxisPct(isoDate: string, years: number[]): number | null {
  return positionPct(isoDate, years, 0.5)
}

export function dateStartPct(isoDate: string, years: number[]): number | null {
  return positionPct(isoDate, years, 0)
}

export function dateEndPct(isoDate: string, years: number[]): number | null {
  return positionPct(isoDate, years, 1)
}

function firstHarvestInYear(entries: HarvestEntry[], year: number): string | null {
  const prefix = `${year}-`
  let earliest: string | null = null
  for (const entry of entries) {
    if (!entry.date.startsWith(prefix)) continue
    if (earliest === null || entry.date < earliest) earliest = entry.date
  }
  return earliest
}

export function buildYearBar(
  year: number,
  stages: BlockStages | null | undefined,
  harvests: HarvestEntry[],
  years: number[],
): TimelineYearBar | null {
  const rawStart = stages?.season.start_date
  const effectiveStart =
    rawStart !== null && rawStart !== undefined && rawStart.startsWith(`${year}-`)
      ? rawStart
      : `${year}-01-01`
  const startPct = dateStartPct(effectiveStart, years)
  const endPct = dateEndPct(`${year}-12-31`, years)
  if (startPct === null || endPct === null) return null

  const firstHarvest = firstHarvestInYear(harvests, year)
  let splitPct: number | null = null
  if (firstHarvest !== null) {
    if (firstHarvest <= effectiveStart) {
      splitPct = startPct
    } else {
      splitPct = dateStartPct(firstHarvest, years)
    }
  }
  return { year, startPct, endPct, splitPct }
}

export function buildStageMarkers(
  stagesByYear: (BlockStages | null | undefined)[],
  years: number[],
): TimelineStageMarker[] {
  const seen = new Set<string>()
  const out: TimelineStageMarker[] = []
  for (const data of stagesByYear) {
    if (data === null || data === undefined) continue
    for (const row of data.stages) {
      if (row.label !== "observed" || row.date === null) continue
      const xPct = dateToAxisPct(row.date, years)
      if (xPct === null) continue
      const id = `${row.stage.id}-${row.date}`
      if (seen.has(id)) continue
      seen.add(id)
      out.push({
        id,
        code: row.stage.code,
        name: row.stage.name,
        date: row.date,
        xPct,
      })
    }
  }
  out.sort((a, b) => a.date.localeCompare(b.date))
  return out
}

export function buildHarvestMarkers(
  entries: HarvestEntry[],
  years: number[],
): TimelineHarvestMarker[] {
  const out: TimelineHarvestMarker[] = []
  for (const entry of entries) {
    const xPct = dateToAxisPct(entry.date, years)
    if (xPct === null) continue
    out.push({
      id: entry.id,
      date: entry.date,
      passNo: entry.pass_no,
      kg: entry.kg,
      xPct,
    })
  }
  out.sort((a, b) => a.date.localeCompare(b.date) || a.passNo - b.passNo)
  return out
}

export function buildOpMarkers(
  items: JournalItem[],
  years: number[],
): TimelineOpMarker[] {
  const out: TimelineOpMarker[] = []
  for (const item of items) {
    if (item.kind !== "operation") continue
    const xPct = dateToAxisPct(item.date, years)
    if (xPct === null) continue
    out.push({
      id: `${item.link_id}-${item.date}`,
      date: item.date,
      title: item.title,
      details: item.details,
      operationType: item.operation_type,
      color: operationColor(item.operation_type),
      xPct,
    })
  }
  out.sort((a, b) => a.date.localeCompare(b.date))
  return out
}

function weekBoundsInYear(isoDate: string, year: number): [string, string] {
  const parts = parseIsoParts(isoDate)
  if (parts === null) return [`${year}-01-01`, `${year}-01-07`]
  const utc = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]))
  const dayNum = utc.getUTCDay() || 7
  const monday = new Date(utc)
  monday.setUTCDate(utc.getUTCDate() - (dayNum - 1))
  const sunday = new Date(monday)
  sunday.setUTCDate(monday.getUTCDate() + 6)
  const yearStart = `${year}-01-01`
  const yearEnd = `${year}-12-31`
  const startIso = monday.toISOString().slice(0, 10)
  const endIso = sunday.toISOString().slice(0, 10)
  return [
    startIso < yearStart ? yearStart : startIso,
    endIso > yearEnd ? yearEnd : endIso,
  ]
}

export function buildIrrigationBins(
  items: JournalItem[],
  years: number[],
): TimelineIrrigationBin[] {
  const buckets = new Map<
    string,
    { year: number; week: number; count: number; sampleDate: string }
  >()
  for (const item of items) {
    if (item.kind !== "irrigation") continue
    const parts = parseIsoParts(item.date)
    if (parts === null) continue
    const year = parts[0]
    if (!years.includes(year)) continue
    const week = isoWeekNumber(item.date)
    const key = `${year}-${week}`
    const existing = buckets.get(key)
    if (existing !== undefined) {
      existing.count += 1
    } else {
      buckets.set(key, { year, week, count: 1, sampleDate: item.date })
    }
  }
  const bins: TimelineIrrigationBin[] = []
  for (const [key, bucket] of buckets) {
    const [startIso, endIso] = weekBoundsInYear(bucket.sampleDate, bucket.year)
    const startPct = dateStartPct(startIso, years)
    const endPct = dateEndPct(endIso, years)
    if (startPct === null || endPct === null) continue
    bins.push({
      key,
      year: bucket.year,
      week: bucket.week,
      count: bucket.count,
      startPct,
      widthPct: Math.max(0.6, endPct - startPct),
    })
  }
  bins.sort((a, b) => a.startPct - b.startPct)
  return bins
}

export function irrigationOpacity(count: number): number {
  if (count >= 3) return 1
  if (count === 2) return 0.65
  return 0.35
}
