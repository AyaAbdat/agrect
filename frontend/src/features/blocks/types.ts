import type { GeoLine, GeoPolygon } from "../../components/map/geometry"

export type LocalizedName = {
  fr: string
  ar: string
  en: string
}

export type BlockCrop = {
  id: string
  code: string
  name: LocalizedName
}

export type BlockStatus = "draft" | "complete" | "archived"

export type BlockListItem = {
  id: string
  name: string
  status: BlockStatus
  crop: BlockCrop | null
  gross_area_ha: string | null
  net_area_ha: string | null
  trees_count: number | null
  q_block_m3h: string | null
  rate_mm_h: string | null
  outline: GeoPolygon | null
  version: number
}

export type DensityInput = "spacing" | "density" | "count"

export type IrrigationSystem =
  | "drip"
  | "subsurface_drip"
  | "micro_sprinkler"
  | "bubbler"
  | "sprinkler"

export type FlowEntryMode = "layout" | "per_tree" | "typed_flow"

export type Planting = {
  id: string
  variety_id: string | null
  variety_text: string | null
  rootstock: string | null
  planting_year: number | null
  density_input: DensityInput | null
  row_spacing_m: string | null
  tree_spacing_m: string | null
  trees_per_ha: number | null
  trees_count: number | null
  area_ha: string | null
  sort: number
}

export type IrrigationLayout = {
  id: string
  system: IrrigationSystem
  entry_mode: FlowEntryMode
  laterals_per_row: number | null
  emitter_spacing_m: string | null
  emitter_flow_lph: string | null
  emitters_per_tree: number | null
  flow_per_emitter_lph: string | null
  typed_flow_m3h: string | null
  typed_flow_basis: "block" | "ha" | "valve" | null
  flow_meter: boolean
  q_ha_m3h: string | null
  q_block_m3h: string | null
  rate_mm_h: string | null
}

export type BlockValve = {
  id: string
  name: string
  sort: number
  row_from: number
  row_to: number
  typed_q_m3h: string | null
  area_ha: string | null
  q_m3h: string | null
}

export type BlockHistoryItem = {
  id: string
  changed_fields: string[]
  reason: string | null
  changed_at: string
}

export type CatalogCrop = {
  id: string
  code: string
  kind: string
  name: LocalizedName
}

export type CatalogVariety = {
  id: string
  code: string
  name: string
}

export type CatalogTrainingSystem = {
  id: string
  code: string
  name: LocalizedName
  description: LocalizedName
}

export type BlockDetail = BlockListItem & {
  row_line: GeoLine | null
  row_bearing_deg: string | null
  rows_total: number | null
  training_system_id: string | null
  training_other: string | null
  plantings: Planting[]
  irrigation_layout: IrrigationLayout | null
  valves: BlockValve[]
}

export function selectedBlockId(pathname: string): string | null {
  const match = /^\/blocks\/([^/]+)(?:\/|$)/.exec(pathname)
  if (match === null || match[1] === "new") return null
  return match[1]
}

export function localizedName(name: LocalizedName, lang: string): string {
  if (lang === "ar" || lang === "en") return name[lang]
  return name.fr
}

export function cropLabel(crop: BlockCrop | null, lang: string): string | null {
  if (crop === null) return null
  return localizedName(crop.name, lang)
}

export function activeLang(language: string | undefined): string {
  if (language === "ar" || language === "en" || language === "fr") return language
  return "fr"
}
