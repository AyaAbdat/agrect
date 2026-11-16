import { formatNumber } from "../../lib/format"
import type { CatalogTrainingSystem, CatalogVariety, Planting } from "./types"
import { localizedName } from "./types"

export function showDecimal(
  value: string | number | null | undefined,
  places: number,
  lang: string,
  missing: string,
): string {
  if (value === null || value === undefined || value === "") return missing
  const parsed = typeof value === "number" ? value : Number(value)
  if (!Number.isFinite(parsed)) return missing
  return formatNumber(parsed, places, lang)
}

export function varietyName(
  planting: Planting | undefined,
  varieties: CatalogVariety[],
): string | null {
  if (planting === undefined) return null
  if (planting.variety_id !== null) {
    const found = varieties.find((item) => item.id === planting.variety_id)
    if (found !== undefined) return found.name
  }
  const text = planting.variety_text?.trim() ?? ""
  return text === "" ? null : text
}

export function trainingName(
  systemId: string | null,
  other: string | null,
  systems: CatalogTrainingSystem[],
  lang: string,
): string | null {
  if (systemId !== null) {
    const found = systems.find((item) => item.id === systemId)
    if (found !== undefined) return localizedName(found.name, lang)
  }
  const text = other?.trim() ?? ""
  return text === "" ? null : text
}

export function formatHistoryDate(value: string, lang: string, missing: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return missing
  return new Intl.DateTimeFormat(`${lang}-u-nu-latn`, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date)
}
