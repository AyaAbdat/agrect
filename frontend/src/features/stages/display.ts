import type { CatalogStage, ScaleCode, StageLabel, StageRow } from "./types"

export function scaleLabelKey(scale: ScaleCode): string {
  if (scale === "el") return "stages.scaleEl"
  if (scale === "zadoks") return "stages.scaleZadoks"
  return "stages.scaleBbch"
}

export function codeLabelKey(scale: ScaleCode): string {
  if (scale === "el") return "stages.codeEl"
  if (scale === "zadoks") return "stages.codeZ"
  return "stages.codeBbch"
}

export function reasonKey(label: StageLabel, reason: string | null): string {
  if (reason === "phenology.no_gdd_setting") return "stages.reasonNoSetting"
  if (reason === "phenology.setting_mismatch") return "stages.reasonMismatch"
  if (reason === "phenology.season_start_required") return "stages.reasonNoStart"
  if (label === "beyond_data") return "stages.reasonBeyond"
  return "stages.reasonNone"
}

export function countKey(code: string): string {
  if (code === "table_grape") return "stages.countGrape"
  if (code === "apple") return "stages.countApple"
  if (code === "pear") return "stages.countPear"
  if (code === "olive") return "stages.countOlive"
  if (code === "wheat") return "stages.countWheat"
  if (code === "barley") return "stages.countBarley"
  return "stages.countDefault"
}

export function fractionDigits(value: number | null): number {
  if (value === null || Number.isInteger(value)) return 0
  return 1
}

export function methodKey(method: "average" | "single_sine"): string {
  return method === "single_sine" ? "weather.singleSine" : "weather.simpleAverage"
}

export function isSownCrop(code: string): boolean {
  return code === "wheat" || code === "barley"
}

export function placeholderRow(stage: CatalogStage, reason: string): StageRow {
  return {
    stage: { id: stage.id, code: stage.code, name: stage.name },
    label: "not_enough_data",
    date: null,
    earliest: null,
    latest: null,
    dd_needed: null,
    dd_counted: null,
    dd_source: null,
    citation: null,
    reason,
  }
}
