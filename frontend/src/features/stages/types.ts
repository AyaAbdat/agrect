export type ScaleCode = "el" | "bbch" | "bbch_olive" | "zadoks"
export type StageLabel = "observed" | "predicted" | "not_enough_data" | "beyond_data"
export type DdSource = "entered" | "literature"
export type StageSource = DdSource | "farm_seasons"
export type GddMethod = "average" | "single_sine"
export type HistoryStatus = "ready" | "loading" | "empty"

export type StageName = {
  fr: string
  ar: string
  en: string
}

export type StageBrief = {
  id: string
  code: string
  name: StageName
}

export type SeasonOut = {
  id: string
  block_id: string
  year: number
  start_date: string | null
  start_stage_def_id: string | null
  start_stage: StageBrief | null
  start_observed: boolean
  status: string
}

export type StageSetting = {
  base_c: string
  upper_c: string | null
  method: GddMethod
}

export type StageRow = {
  stage: StageBrief
  label: StageLabel
  date: string | null
  earliest: string | null
  latest: string | null
  dd_needed: string | null
  dd_counted: string | null
  dd_source: DdSource | null
  citation: string | null
  reason: string | null
}

export type ObservationItem = {
  id: string
  stage_def_id: string
  observed_on: string
  share_pct: string | null
}

export type BlockStages = {
  season: SeasonOut
  setting: StageSetting | null
  history_status: HistoryStatus
  history: { years_count: number; status: HistoryStatus }
  today: {
    dd_counted: string | null
    current_stage: StageBrief | null
    next_stage: StageBrief | null
  }
  stages: StageRow[]
  observations: ObservationItem[]
}

export type CatalogStage = {
  id: string
  code: string
  sort: number
  name: StageName
  description: StageName
}

export type CropStages = {
  scale: ScaleCode
  scale_citation: string
  stages: CatalogStage[]
}

export type StageDdRow = {
  stage_def_id: string
  code: string
  sort: number
  name: StageName
  dd_value: string | null
  base_c: string | null
  upper_c: string | null
  method: GddMethod | null
  source: StageSource | null
  citation: string | null
  label: "not_enough_data" | null
}

export type StageDdOut = {
  crop_id: string
  stages: StageDdRow[]
}

export type StagePref = {
  stage_def_id: string
  hidden: boolean
  local_name: string | null
}

export type StagePrefs = {
  items: StagePref[]
}

export type SummaryNext = {
  stage: StageBrief
  date: string
}

export type SummaryBlock = {
  block_id: string
  name: string
  season_id: string | null
  year: number
  current_stage: StageBrief | null
  next_stage: SummaryNext | null
}

export type StageSummary = {
  crop_id: string
  blocks: SummaryBlock[]
}
