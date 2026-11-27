import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import { Button } from "@/components/ui/button"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { crumbClass } from "../../lib/navStyles"
import { UNIT_MM } from "../../lib/units"
import { showDecimal, varietyName } from "../blocks/display"
import {
  activeLang,
  cropLabel,
  localizedName,
  type BlockDetail,
  type CatalogVariety,
} from "../blocks/types"
import { EnteredTag } from "../blocks/wizard/wizardUi"
import { WaterChart, hasChartData, waterPoints } from "../soilwater/chart"
import { mm2, runParts, show } from "../soilwater/display"
import { useWaterLeftNow } from "../soilwater/waterLeft"
import { LogIrrigationDrawer } from "../soilwater/LogIrrigationDrawer"
import type { FarmClock, IrrigationToday, WaterBalance } from "../soilwater/types"
import { reasonKey } from "../stages/display"
import { readBlockStages } from "../stages/load"
import type { BlockStages, StageRow } from "../stages/types"
import type { HarvestFarmSummary } from "../harvest/types"
import type { JournalList, ReentryInfo } from "../journal/types"
import { itemTypeKey } from "../journal/display"
import { money } from "../inventories/money"
import type { BlockCosts } from "../inventories/types"
import { densityText } from "../harvest/display"
import {
  asNumber,
  farmToday,
  formatHour,
  formatMediumDate,
  formatWeekdayDate,
  shiftIsoDate,
} from "../weather/format"
import type { ForecastDay, ForecastOut, Thresholds } from "../weather/types"
import {
  FormulaTip,
  PageHeader,
  SourceTag,
  cardClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"

const CHART_FROM_OFFSET_DAYS = 21
const ACTION_HORIZON_DAYS = 6

type Translate = (key: string, options?: Record<string, string>) => string

type StageModel = {
  value: string
  sub: string | null
  entered: boolean
  calculated: boolean
}

type IrrigateLine = {
  status: "ok" | "irrigate_soon"
  gross: string
  hours: string
  minutes: string
  calculated: boolean
}

type WeatherHit = {
  key: string
  tone: "frost" | "heat"
  hours: string
  date: string
}

function stageModel(stages: BlockStages | null, lang: string, t: Translate): StageModel {
  if (stages === null) {
    return { value: t("stages.seasonNotStarted"), sub: null, entered: false, calculated: false }
  }
  const current = stages.today.current_stage
  const next = stages.today.next_stage
  const currentRow = rowFor(stages, current?.id ?? null)
  const nextRow = rowFor(stages, next?.id ?? null)
  const value = current === null ? t("common.missing") : localizedName(current.name, lang)
  const entered = currentRow?.label === "observed"
  if (nextRow !== undefined && nextRow.date !== null && nextRow.label === "predicted") {
    return {
      value,
      sub: t("overview.nextPredicted", { date: formatMediumDate(nextRow.date, lang) }),
      entered,
      calculated: true,
    }
  }
  if (nextRow !== undefined) {
    return { value, sub: t(reasonKey(nextRow.label, nextRow.reason)), entered, calculated: false }
  }
  if (current === null) {
    const first = stages.stages[0]
    const sub = first === undefined ? t("stages.seasonNotStarted") : t(reasonKey(first.label, first.reason))
    return { value, sub, entered: false, calculated: false }
  }
  return {
    value,
    sub: t("overview.nextPredicted", { date: t("common.missing") }),
    entered,
    calculated: false,
  }
}

function rowFor(stages: BlockStages, id: string | null): StageRow | undefined {
  if (id === null) return undefined
  return stages.stages.find((row) => row.stage.id === id)
}

function irrigateLine(advice: IrrigationToday, lang: string): IrrigateLine | null {
  if (advice.status === "no_data") return null
  const dose = advice.recommended === "refill" ? advice.refill : advice.maintain
  const run = runParts(dose.run_time_min, lang)
  return {
    status: advice.status,
    gross: formatNumber(asNumber(dose.gross_mm), 2, lang),
    hours: run.hours,
    minutes: run.minutes,
    calculated: asNumber(dose.gross_mm) !== null,
  }
}

function weatherHits(days: ForecastDay[], thresholds: Thresholds, today: string, lang: string): WeatherHit[] {
  if (thresholds.frost_c === null && thresholds.heat_c === null) return []
  const end = shiftIsoDate(today, ACTION_HORIZON_DAYS)
  const hits: WeatherHit[] = []
  for (const day of days) {
    if (day.date < today || day.date > end) continue
    const date = formatWeekdayDate(day.date, lang)
    if (thresholds.frost_c !== null && day.frost_h !== null && day.frost_h > 0) {
      hits.push({
        key: `${day.date}-frost`,
        tone: "frost",
        hours: formatNumber(day.frost_h, 0, lang),
        date,
      })
    }
    if (thresholds.heat_c !== null && day.heat_h !== null && day.heat_h > 0) {
      hits.push({
        key: `${day.date}-heat`,
        tone: "heat",
        hours: formatNumber(day.heat_h, 0, lang),
        date,
      })
    }
  }
  return hits
}

function stageSoon(stages: BlockStages, today: string, lang: string): { stage: string; date: string } | null {
  const next = stages.today.next_stage
  if (next === null) return null
  const row = rowFor(stages, next.id)
  if (row?.date == null || row.label !== "predicted") return null
  const end = shiftIsoDate(today, ACTION_HORIZON_DAYS)
  if (row.date < today || row.date > end) return null
  return { stage: localizedName(next.name, lang), date: formatMediumDate(row.date, lang) }
}

function PhaseTag() {
  const { t } = useTranslation()
  return (
    <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
      {t("settings.phase2")}
    </span>
  )
}

function CardSkeleton({ className = "mt-3 h-16" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[#E5E7EB] ${className}`} />
}

function CardError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="mt-3 flex flex-col items-start gap-2">
      <p className="text-[13px]">{t("common.loadError")}</p>
      <Button type="button" className={primaryBtn} onClick={onRetry}>
        {t("common.retry")}
      </Button>
    </div>
  )
}

function IrrigateStatus({ status }: { status: IrrigateLine["status"] }) {
  const { t } = useTranslation()
  const soon = status === "irrigate_soon"
  return (
    <span
      className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
        soon ? "bg-[#FEF3C7] text-amb" : "bg-mint text-pri"
      }`}
    >
      {t(soon ? "soil.statusSoon" : "soil.statusOk")}
    </span>
  )
}

function OverviewHeader({
  blockId,
  block,
  pending,
  failed,
  lang,
  onRetry,
}: {
  blockId: string
  block: BlockDetail | undefined
  pending: boolean
  failed: boolean
  lang: string
  onRetry: () => void
}) {
  const { t } = useTranslation()
  const cropId = block?.crop?.id ?? null
  const planting = block?.plantings[0]
  const varietiesQuery = useQuery({
    queryKey: ["catalog", "varieties", cropId],
    queryFn: () => apiGet<CatalogVariety[]>(`/v1/catalog/crops/${cropId}/varieties`),
    enabled: cropId !== null,
  })
  const edit = (
    <Link to={`/blocks/${blockId}/setup`} className={`inline-flex items-center ${outlineBtn}`}>
      {t("overview.editSetup")}
    </Link>
  )
  if (pending) {
    return (
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="h-3 w-40 animate-pulse rounded bg-[#E5E7EB]" />
          <div className="mt-2 h-7 w-56 animate-pulse rounded bg-[#E5E7EB]" />
        </div>
        {edit}
      </header>
    )
  }
  if (failed || block === undefined) {
    return (
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className={crumbClass}>{t("nav.blocks")}</p>
          <h1 className="text-[24px] font-bold leading-tight">{t("nav.overview")}</h1>
          <CardError onRetry={onRetry} />
        </div>
        {edit}
      </header>
    )
  }
  const missing = t("common.missing")
  const varietyPending = cropId !== null && planting?.variety_id != null && varietiesQuery.isPending
  const named = varietyName(planting, varietiesQuery.data ?? [])
  const variety = varietyPending ? t("common.loading") : (named ?? missing)
  const area = showDecimal(block.net_area_ha, 2, lang, missing)
  const crop = cropLabel(block.crop, lang) ?? missing
  return (
    <PageHeader
      crumb={t("blocks.setupCrumb", { name: block.name })}
      title={block.name}
      sub={t("blocks.setupSub", { crop, variety, area })}
      actions={edit}
    />
  )
}

function StageTile({ blockId, farmId, lang }: { blockId: string; farmId: string; lang: string }) {
  const { t } = useTranslation()
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
  })
  const today = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)
  const year = today === null ? null : Number(today.slice(0, 4))
  const stagesQuery = useQuery({
    queryKey: ["block-stages", blockId, year],
    queryFn: () => readBlockStages(blockId, year ?? 0),
    enabled: year !== null,
  })
  const pending = farmQuery.isLoading || (year !== null && stagesQuery.isLoading)
  const failed = farmQuery.isError || stagesQuery.isError
  const model =
    stagesQuery.isSuccess && !failed ? stageModel(stagesQuery.data ?? null, lang, t) : null
  return (
    <section className={cardClass}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[12px] text-mut">{t("today.stageNow")}</p>
        {model !== null ? (
          <span className="flex shrink-0 items-center gap-1">
            {model.entered ? <EnteredTag /> : null}
            {model.calculated ? <SourceTag kind="calculated" /> : null}
          </span>
        ) : null}
      </div>
      {pending ? <CardSkeleton /> : null}
      {failed ? (
        <CardError
          onRetry={() => {
            void farmQuery.refetch()
            void stagesQuery.refetch()
          }}
        />
      ) : null}
      {model !== null && !pending ? (
        <>
          <p className="mt-2 text-[20px] font-bold leading-tight">{model.value}</p>
          {model.sub !== null ? <p className="mt-1 text-[12px] text-mut">{model.sub}</p> : null}
        </>
      ) : null}
    </section>
  )
}

function WaterTile({ blockId, lang }: { blockId: string; lang: string }) {
  const { t } = useTranslation()
  const waterLeft = useWaterLeftNow(blockId)
  const row = waterLeft.row
  return (
    <section className={cardClass}>
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 text-[12px] text-mut">{t("soil.waterLeftTitle")}</p>
        {row !== undefined ? <SourceTag kind="calculated" /> : null}
      </div>
      {waterLeft.pending ? <CardSkeleton /> : null}
      {waterLeft.failed ? <CardError onRetry={waterLeft.refetch} /> : null}
      {!waterLeft.pending && !waterLeft.failed ? (
        <>
          <p className="mt-2 text-[20px] font-bold leading-tight">
            {mm2(row?.water_left_mm, lang)}{" "}
            <span className="text-[12px] font-medium text-mut">{UNIT_MM}</span>
          </p>
          {row !== undefined ? (
            <p className="mt-1 text-[12px] text-mut">
              {t("soil.waterLeftAsOf", { date: formatMediumDate(row.date, lang) })}
            </p>
          ) : null}
          <p className="mt-1 text-[12px] text-mut">
            {t("soil.irrigateBelow", { value: show(row?.irrigate_below_mm, lang) })}
          </p>
        </>
      ) : null}
    </section>
  )
}

function StaticTile({
  label,
  value,
  unit,
  sub,
}: {
  label: string
  value: string
  unit?: string
  sub: string
}) {
  return (
    <section className={cardClass}>
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 text-[12px] text-mut">{label}</p>
        <PhaseTag />
      </div>
      <p className="mt-2 text-[20px] font-bold leading-tight">
        {value}
        {unit !== undefined ? (
          <>
            {" "}
            <span className="text-[12px] font-medium text-mut">{unit}</span>
          </>
        ) : null}
      </p>
      <p className="mt-1 text-[12px] text-mut">{sub}</p>
    </section>
  )
}

function YieldTile({
  blockId,
  farmId,
  lang,
}: {
  blockId: string
  farmId: string
  lang: string
}) {
  const { t } = useTranslation()
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
  })
  const today = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)
  const year = today === null ? null : Number(today.slice(0, 4))
  const summaryQuery = useQuery({
    queryKey: ["harvest-summary", farmId, year],
    queryFn: () =>
      apiGet<HarvestFarmSummary>(`/v1/farms/${farmId}/harvest/summary?season=${year ?? 0}`),
    enabled: year !== null,
  })
  const pending = farmQuery.isLoading || (year !== null && summaryQuery.isLoading)
  const failed = farmQuery.isError || summaryQuery.isError
  const row =
    summaryQuery.data === undefined
      ? undefined
      : summaryQuery.data.blocks.find((block) => block.block_id === blockId)
  const hasYield = row !== undefined && row.kg_ha !== null
  const missing = t("common.missing")
  return (
    <section className={cardClass}>
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 text-[12px] text-mut">{t("overview.yieldThisSeason")}</p>
        <span className="flex shrink-0 items-center gap-1">
          {hasYield ? <SourceTag kind="calculated" /> : null}
          <FormulaTip text={t("overview.expectedYieldPhase3")} />
        </span>
      </div>
      {pending ? <CardSkeleton /> : null}
      {failed ? (
        <CardError
          onRetry={() => {
            void farmQuery.refetch()
            void summaryQuery.refetch()
          }}
        />
      ) : null}
      {!pending && !failed ? (
        <>
          <p className="mt-2 text-[20px] font-bold leading-tight" dir="ltr">
            {hasYield ? densityText(row.kg_ha, lang) : missing}{" "}
            <span className="text-[12px] font-medium text-mut">{t("overview.yieldUnit")}</span>
          </p>
          <p className="mt-1 text-[12px] text-mut">
            {hasYield
              ? t("overview.passesCount", { count: String(row.passes) })
              : t("overview.onNetArea")}
          </p>
        </>
      ) : null}
    </section>
  )
}

function WaterChartCard({ blockId, farmId, lang }: { blockId: string; farmId: string; lang: string }) {
  const { t } = useTranslation()
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
  })
  const today = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)
  const from = today === null ? null : shiftIsoDate(today, -CHART_FROM_OFFSET_DAYS)
  const balanceQuery = useQuery({
    queryKey: ["water-balance", blockId, "overview", from],
    queryFn: () =>
      apiGet<WaterBalance>(`/v1/blocks/${blockId}/water-balance?from=${from ?? ""}`),
    enabled: from !== null,
  })
  const waterLeft = useWaterLeftNow(blockId)
  const pending = farmQuery.isLoading || (from !== null && balanceQuery.isLoading)
  const failed = farmQuery.isError || balanceQuery.isError
  const points = balanceQuery.data === undefined ? [] : waterPoints(balanceQuery.data.rows, lang)
  const ready = hasChartData(points)
  const threshold =
    waterLeft.row === undefined ? null : asNumber(waterLeft.row.irrigate_below_mm)
  return (
    <section className={`${cardClass} min-w-0`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-[15px] font-bold">{t("overview.waterChart")}</h2>
          <p className="text-[13px] text-mut">{t("overview.last3Weeks")}</p>
        </div>
        {ready ? <SourceTag kind="calculated" /> : null}
      </div>
      {pending ? <CardSkeleton className="mt-3 h-[220px]" /> : null}
      {failed ? (
        <CardError
          onRetry={() => {
            void farmQuery.refetch()
            void balanceQuery.refetch()
          }}
        />
      ) : null}
      {!pending && !failed && ready ? (
        <div className="mt-3">
          <WaterChart
            points={points}
            lang={lang}
            threshold={threshold}
            thresholdLabel={t("soil.legendThreshold")}
          />
        </div>
      ) : null}
      {!pending && !failed && !ready && balanceQuery.isSuccess ? (
        <div className="mt-3 flex h-[220px] items-center justify-center text-[13px] text-mut">
          {t("soil.noData")}
        </div>
      ) : null}
    </section>
  )
}

function TodayCard({
  blockId,
  farmId,
  lang,
  canLog,
  onLog,
}: {
  blockId: string
  farmId: string
  lang: string
  canLog: boolean
  onLog: () => void
}) {
  const { t } = useTranslation()
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
  })
  const today = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)
  const year = today === null ? null : Number(today.slice(0, 4))
  const adviceQuery = useQuery({
    queryKey: ["irrigation-today", blockId],
    queryFn: () => apiGet<IrrigationToday>(`/v1/blocks/${blockId}/irrigation-today`),
  })
  const forecastQuery = useQuery({
    queryKey: ["weather", farmId, "forecast"],
    queryFn: () => apiGet<ForecastOut>(`/v1/farms/${farmId}/weather/forecast`),
  })
  const thresholdsQuery = useQuery({
    queryKey: ["thresholds", farmId],
    queryFn: () => apiGet<Thresholds>(`/v1/farms/${farmId}/thresholds`),
  })
  const stagesQuery = useQuery({
    queryKey: ["block-stages", blockId, year],
    queryFn: () => readBlockStages(blockId, year ?? 0),
    enabled: year !== null,
  })
  const irrigate = adviceQuery.data === undefined ? null : irrigateLine(adviceQuery.data, lang)
  const hits =
    forecastQuery.data === undefined || thresholdsQuery.data === undefined || today === null
      ? []
      : weatherHits(forecastQuery.data.daily, thresholdsQuery.data, today, lang)
  const soon =
    stagesQuery.data === undefined || stagesQuery.data === null || today === null
      ? null
      : stageSoon(stagesQuery.data, today, lang)
  const reentryQuery = useQuery({
    queryKey: ["reentry", blockId],
    queryFn: () => apiGet<ReentryInfo | null>(`/v1/blocks/${blockId}/reentry`),
  })
  const reentry = reentryQuery.data ?? null
  const pending =
    adviceQuery.isLoading ||
    farmQuery.isLoading ||
    forecastQuery.isLoading ||
    thresholdsQuery.isLoading ||
    (year !== null && stagesQuery.isLoading)
  const failed =
    adviceQuery.isError ||
    farmQuery.isError ||
    forecastQuery.isError ||
    thresholdsQuery.isError ||
    stagesQuery.isError
  const hasLine = irrigate !== null || hits.length > 0 || soon !== null || reentry !== null
  return (
    <section className={cardClass}>
      <h2 className="text-[15px] font-bold">{t("overview.todayTitle")}</h2>
      {hasLine ? (
        <ul className="mt-3 flex flex-col gap-3">
          {irrigate !== null ? (
            <li className="flex flex-col items-start gap-1">
              <span className="text-[13px] font-semibold">{t("today.irrigateToday")}</span>
              <span className="flex flex-wrap items-center gap-2">
                <IrrigateStatus status={irrigate.status} />
                <span className="text-[13px]">
                  {t("today.irrigateDose", {
                    gross: irrigate.gross,
                    hours: irrigate.hours,
                    minutes: irrigate.minutes,
                  })}
                </span>
                {irrigate.calculated ? <SourceTag kind="calculated" /> : null}
              </span>
              <button
                type="button"
                className="text-[13px] font-semibold text-pri disabled:text-mut"
                disabled={!canLog}
                onClick={onLog}
              >
                {t("soil.logButton")}
              </button>
            </li>
          ) : null}
          {hits.map((hit) => (
            <li key={hit.key} className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex rounded-full px-2.5 py-1 text-[12px] font-semibold ${
                  hit.tone === "frost" ? "bg-[#FEF3C7] text-amb" : "bg-[#FEE2E2] text-red"
                }`}
              >
                {t(hit.tone === "frost" ? "today.frostLine" : "today.heatLine", {
                  hours: hit.hours,
                  date: hit.date,
                })}
              </span>
              <SourceTag kind="estimated" />
            </li>
          ))}
          {soon !== null ? (
            <li className="flex flex-wrap items-center gap-2 text-[13px]">
              <span>{t("overview.nextStageSoon", { stage: soon.stage, date: soon.date })}</span>
              <SourceTag kind="calculated" />
            </li>
          ) : null}
          {reentry !== null ? (
            <li className="text-[13px] text-amb">
              {t("overview.reentryLine", {
                product: reentry.product,
                until: formatHour(reentry.until, farmQuery.data?.timezone ?? "UTC"),
              })}
            </li>
          ) : null}
        </ul>
      ) : null}
      {pending && !hasLine ? <CardSkeleton /> : null}
      {failed ? (
        <CardError
          onRetry={() => {
            void adviceQuery.refetch()
            void farmQuery.refetch()
            void forecastQuery.refetch()
            void thresholdsQuery.refetch()
            void stagesQuery.refetch()
            void reentryQuery.refetch()
          }}
        />
      ) : null}
      {!pending && !failed && !hasLine ? (
        <p className="mt-3 text-[13px] text-mut">{t("overview.noActions")}</p>
      ) : null}
    </section>
  )
}

function JournalCard({ blockId, lang }: { blockId: string; lang: string }) {
  const { t } = useTranslation()
  const journalQuery = useQuery({
    queryKey: ["journal", blockId, null, null, null],
    queryFn: () => apiGet<JournalList>(`/v1/blocks/${blockId}/journal`),
  })
  const items = journalQuery.data?.items.slice(0, 3) ?? []
  return (
    <section className={cardClass}>
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-[15px] font-bold">{t("overview.journalTitle")}</h2>
        <Link
          to={`/blocks/${blockId}/journal`}
          className="text-[12px] font-semibold text-pri"
        >
          {t("overview.openJournal")}
        </Link>
      </div>
      {journalQuery.isLoading ? <CardSkeleton /> : null}
      {journalQuery.isError ? <p className="mt-3 text-[13px] text-mut">{t("common.loadError")}</p> : null}
      {journalQuery.isSuccess && items.length === 0 ? (
        <p className="mt-3 text-[13px] text-mut">{t("overview.journalEmpty")}</p>
      ) : null}
      {items.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-2">
          {items.map((item) => (
            <li key={`${item.kind}-${item.link_id}`} className="text-[13px]">
              <p className="font-semibold">
                {formatMediumDate(item.date, lang)} · {t(itemTypeKey(item))}
              </p>
              <p className="text-mut">{item.title}</p>
              {item.cost_dzd !== null ? (
                <p className="text-mut" dir="ltr">
                  {money(item.cost_dzd, lang)} {t("common.dzd")}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

function PlanCard({ blockId, lang }: { blockId: string; lang: string }) {
  const { t } = useTranslation()
  const costsQuery = useQuery({
    queryKey: ["block-costs", blockId, "overview"],
    queryFn: () => apiGet<BlockCosts>(`/v1/blocks/${blockId}/costs`),
  })
  const perHa = costsQuery.data?.per_ha_dzd ?? null
  return (
    <section className={cardClass}>
      <h2 className="text-[15px] font-bold">{t("overview.planTitle")}</h2>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Link to={`/blocks/${blockId}/costs`} className="block rounded-xl bg-[#F7F8F7] p-3">
          <p className="flex items-center justify-between gap-2 text-[12px] text-mut">
            {t("overview.costTile")}
            <SourceTag kind="calculated" />
          </p>
          <p className="mt-2 text-[18px] font-bold" dir="ltr">
            {costsQuery.isSuccess ? `${money(perHa, lang)} ${t("common.dzd")}` : t("common.missing")}
          </p>
          <p className="text-[11px] text-mut">{t("costs.perHa")}</p>
        </Link>
        <div className="rounded-xl bg-[#F7F8F7] p-3">
          <p className="flex items-center justify-between gap-2 text-[12px] text-mut">
            {t("overview.planCrop")}
            <PhaseTag />
          </p>
          <p className="mt-2 text-[18px] font-bold">{t("common.missing")}</p>
        </div>
      </div>
    </section>
  )
}

export function OverviewPage() {
  const { t, i18n } = useTranslation()
  const { blockId } = useParams()
  const { currentFarmId } = useAuth()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [logOpen, setLogOpen] = useState(false)
  const farmId = currentFarmId
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  if (blockId === undefined || farmId === null) return null
  const block = blockQuery.data
  const zone = farmQuery.data?.timezone ?? null
  const today = zone === null ? null : farmToday(zone)
  const missing = t("common.missing")
  return (
    <div className="flex flex-col gap-4">
      <OverviewHeader
        blockId={blockId}
        block={block}
        pending={blockQuery.isLoading}
        failed={blockQuery.isError}
        lang={lang}
        onRetry={() => void blockQuery.refetch()}
      />
      <div className="grid grid-cols-4 gap-3">
        <StageTile blockId={blockId} farmId={farmId} lang={lang} />
        <WaterTile blockId={blockId} lang={lang} />
        <StaticTile
          label={t("overview.pestPressure")}
          value={missing}
          sub={t("overview.noTraps")}
        />
        <YieldTile blockId={blockId} farmId={farmId} lang={lang} />
      </div>
      <div className="grid grid-cols-[minmax(0,1.55fr)_minmax(280px,0.85fr)] items-start gap-3">
        <WaterChartCard blockId={blockId} farmId={farmId} lang={lang} />
        <TodayCard
          blockId={blockId}
          farmId={farmId}
          lang={lang}
          canLog={block !== undefined && zone !== null && today !== null}
          onLog={() => setLogOpen(true)}
        />
      </div>
      <div className="grid grid-cols-2 items-start gap-3">
        <JournalCard blockId={blockId} lang={lang} />
        <PlanCard blockId={blockId} lang={lang} />
      </div>
      {block !== undefined && zone !== null && today !== null ? (
        <LogIrrigationDrawer
          open={logOpen}
          onOpenChange={setLogOpen}
          blockId={blockId}
          blockName={block.name}
          valves={block.valves}
          timeZone={zone}
          today={today}
          event={null}
        />
      ) : null}
    </div>
  )
}
