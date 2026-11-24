export type SourceKind = "measured" | "estimated" | "calculated" | "entered"
export type JournalKind = "operation" | "irrigation" | "harvest" | "stage"
export type OperationType =
  | "fertigation"
  | "foliar_application"
  | "crop_protection_spray"
  | "herbicide"
  | "pruning"
  | "shoot_cluster_thinning"
  | "growth_regulator"
  | "girdling"
  | "leaf_removal"
  | "cover_netting"
  | "tillage"
  | "sowing"
  | "nitrogen_application"
  | "other"
export type ProductKind = "fertiliser" | "crop_protection" | "seed" | "packaging" | "other"
export type ProductUnit = "kg" | "g" | "l" | "ml" | "unit"
export type RateBasis = "per_ha" | "per_100l" | "per_block"
export type JournalItem = {
  kind: JournalKind
  date: string
  title: string
  details: string | null
  link_id: string
  source: SourceKind | null
  operation_type: OperationType | null
}
export type JournalList = { items: JournalItem[] }
export type StageAtBrief = {
  id: string
  code: string
  name: { fr: string; ar: string; en: string }
}
export type StageAt = {
  stage: StageAtBrief | null
  date: string | null
  label: "observed" | "predicted" | null
}
export type ReentryInfo = { until: string; product: string }
export type Product = {
  id: string
  farm_id: string
  name: string
  kind: ProductKind
  unit: ProductUnit
  active_ingredient: string | null
  nutrient_n_pct: string | null
  nutrient_p2o5_pct: string | null
  nutrient_k2o_pct: string | null
  preharvest_interval_days: number | null
  reentry_h: number | null
  version: number
  created_at: string
  updated_at: string
}
export type ProductList = { products: Product[] }
export type OperationProductLine = {
  id: string
  product_id: string
  product_name: string
  rate: string
  rate_unit: ProductUnit
  rate_basis: RateBasis
  water_l_ha: string | null
  total_qty: string
  total_unit: ProductUnit
  source: "calculated"
}
export type OperationSafety = {
  preharvest_interval_days: number | null
  reentry_h: number | null
}
export type Operation = {
  id: string
  farm_id: string
  block_id: string
  valve_ids: string[]
  type: OperationType
  date: string
  start_at: string | null
  duration_min: number | null
  workers_count: number | null
  target: string | null
  notes: string | null
  area_ha: string
  source: "calculated"
  products: OperationProductLine[]
  safety: OperationSafety | null
  version: number
  created_at: string
  updated_at: string
}
export type OperationList = { operations: Operation[] }
export type OperationProductPreview = {
  total_qty: string
  total_unit: ProductUnit | null
  source: "calculated"
}
export type ProductRow = {
  key: string
  product_id: string
  rate: string
  rate_unit: ProductUnit
  rate_basis: RateBasis
  water_m3_ha: string
}
export type JournalViewTab = "crop" | "operation"
export type JournalTypeFilter =
  | "all"
  | "fertigation"
  | "treatment"
  | "foliar"
  | "irrigation"
  | "weed"
  | "pruning"
  | "thinning"
  | "harvest"
  | "stages"
  | "scouting"
  | "more"