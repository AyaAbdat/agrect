export type PreharvestWarning = {
  product: string
  spray_date: string
  days_since: number
  days_needed: number
}

export type HarvestUnit = "kg" | "t" | "crate" | "bin"
export type HarvestBasis = "block" | "valve" | "rows" | "trees"

export type QualityField =
  | "brix"
  | "size_grade"
  | "waste_pct"
  | "moisture_pct"
  | "protein_pct"
  | "test_weight_kg_hl"

export type HarvestQuality = {
  brix: string | null
  size_grade: Record<string, number> | null
  waste_pct: string | null
  moisture_pct: string | null
  protein_pct: string | null
  test_weight_kg_hl: string | null
}

export type HarvestEntry = {
  id: string
  block_id: string
  valve_id: string | null
  date: string
  pass_no: number
  quantity: string
  unit: HarvestUnit
  unit_weight_kg: string | null
  basis: HarvestBasis
  basis_count: string | null
  kg: string
  kg_ha: string
  area_ha: string
  source: "calculated"
  quality: HarvestQuality | null
  preharvest_warning: PreharvestWarning | null
  version: number
  created_at: string
  updated_at: string
}

export type HarvestList = {
  entries: HarvestEntry[]
}

export type HarvestPreview = {
  kg: string
  kg_ha: string
  area_ha: string
  source: "calculated"
}

export type HarvestBlockSummary = {
  block_id: string
  kg_total: string
  kg_ha: string | null
  passes: number
}

export type HarvestFarmSummary = {
  season: number
  farm: {
    kg_total: string
    kg_ha: string | null
    blocks_harvested: number
  }
  blocks: HarvestBlockSummary[]
}

export type HarvestFields = {
  crop_id: string
  crop_code: string
  fields: QualityField[]
}

export type GradeRow = {
  key: string
  grade: string
  pct: string
}
