export type CompareMetric =
  | "water_left"
  | "water_applied"
  | "crop_water_use"
  | "degree_days"
  | "pest_count"
  | "stage"

export type CompareSource = "measured" | "estimated" | "calculated" | "entered"

export type CompareBlock = {
  id: string
  name: string
}

export type CompareRow = {
  block: CompareBlock
  value: string | null
  value_name: Record<string, string> | null
  unit: string | null
  mean_7d: string | null
  source: CompareSource | null
}

export type CompareFlag = {
  block_ids: string[]
  metric: "water_left"
  message_code: string
}

export type CompareResponse = {
  metric: CompareMetric
  date: string
  available: boolean
  unavailable_code: string | null
  rows: CompareRow[]
  flags: CompareFlag[]
}
