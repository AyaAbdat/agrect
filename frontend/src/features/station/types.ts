export type WaterSourceKind = "borehole" | "basin" | "network"

export type CapacityChoice = "priority" | "share" | "more_shifts"

export type CapacityMode = "today" | "peak_week"

export type WaterSource = {
  id: string
  name: string
  kind: WaterSourceKind
  ec_ds_m: string | null
  basin_volume_m3: string | null
}

export type PumpBlock = {
  id: string
  name: string
}

export type PumpWindow = {
  id: string
  start_time: string
  end_time: string
}

export type Pump = {
  id: string
  name: string
  flow_m3h: string
  serves_all_blocks: boolean
  pressure_bar: string | null
  version: number
  blocks: PumpBlock[]
  windows: PumpWindow[]
  water_source: WaterSource | null
}

export type FarmStation = {
  station: {
    id: string
    name: string
    version: number
    created_at: string
    updated_at: string
  } | null
  pumps: Pump[]
  water_sources: WaterSource[]
  totals: {
    pumps_flow_m3h: string
  }
}

export type ValveFlow = {
  valve_id: string
  block_id: string
  q_m3h: string
  run_time_min: string
}

export type Shift = {
  valves: ValveFlow[]
  flow_m3h: string
  time_min: string
}

export type CapacityCheck = {
  mode: CapacityMode
  source: "calculated"
  summary: {
    open_together_flow_m3h: string
    pumps_flow_m3h: string
    short_by_m3h: string
    hours_needed: string
    hours_available: string | null
    fits_in_hours: boolean | null
  }
  shifts: Shift[]
  cannot_supply: ValveFlow[]
  no_dose_blocks: string[]
}

export type WindowDraft = {
  start: string
  end: string
}
