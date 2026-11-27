import type { OperationType } from "../journal/types"

export type PriceResource =
  | "product"
  | "water_m3"
  | "labour_h"
  | "machine_h"
  | "fuel_l"
  | "energy_kwh"

export type Price = {
  id: string
  farm_id: string
  product_id: string | null
  resource: PriceResource
  valid_from: string
  dzd_per_unit: string
  unit: string
  note: string | null
  version: number
  created_at: string
  updated_at: string
}
export type PriceList = { prices: Price[] }

export type StockMoveKind = "purchase" | "use" | "adjustment"
export type StockMove = {
  id: string
  farm_id: string
  product_id: string
  date: string
  qty: string
  kind: StockMoveKind
  operation_id: string | null
  note: string | null
  created_at: string
}
export type StockMoveList = { moves: StockMove[] }

export type StockItem = {
  product_id: string
  product_name: string
  unit: string
  on_hand: string
  last_purchase: string | null
  uses_this_season: string
  unit_mismatch_count: number
  low: boolean | null
}
export type Stock = { items: StockItem[] }

export type UnitMismatch = {
  operation_id: string
  block_id: string
  block_name: string
  date: string
  product: string
  operation_unit: string
  product_unit: string
}
export type CostByOperation = { date: string; type: OperationType; dzd: string }

export type BlockCosts = {
  season: number
  total_dzd: string
  per_ha_dzd: string | null
  by_source: Record<string, string>
  by_operation: CostByOperation[]
  missing_prices: string[]
  unit_mismatches: UnitMismatch[]
}

export type FarmCostBlock = {
  block_id: string
  name: string
  total_dzd: string
  per_ha_dzd: string | null
  by_source: Record<string, string>
}
export type FarmCosts = {
  season: number
  blocks: FarmCostBlock[]
  total_dzd: string
  per_ha_dzd: string | null
  missing_prices: string[]
  unit_mismatches: UnitMismatch[]
}
