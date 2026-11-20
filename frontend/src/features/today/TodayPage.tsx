import { useQueries, useQuery } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import { Button } from "@/components/ui/button"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { crumbClass } from "../../lib/navStyles"
import { UNIT_MM, UNIT_TEMP_C, UNIT_WIND_M_S } from "../../lib/units"
import { activeLang, cropLabel, localizedName, type BlockListItem, type BlockStatus } from "../blocks/types"
import { runParts } from "../soilwater/display"
import type { FarmIrrigationToday, IrrigationToday } from "../soilwater/types"
import { asNumber, farmLocalNow, formatHour, formatLongDate, formatMediumDate, formatWeekdayDate } from "../weather/format"
import type { StageSummary, SummaryBlock } from "../stages/types"
import { ThresholdsDrawer } from "../weather/ThresholdsDrawer"
import type {
  BlockGddSetting,
  DegreeDays,
  ForecastDay,
  ForecastOut,
  GddSettingListItem,
  NowOut,
  Thresholds,
} from "../weather/types"
import { PageHeader, SourceTag, cardClass, outlineBtn, primaryBtn } from "../weather/ui"

type FarmToday = {
  name: string
  timezone: string
}

const rowClass =
  "grid grid-cols-[1.75rem_minmax(120px,1.2fr)_auto_auto_auto_auto_minmax(110px,auto)_minmax(120px,auto)_minmax(140px,auto)_auto] items-center gap-x-3 px-1 py-3 text-start"

function greetingKey(hour: number): "today.morning" | "today.afternoon" | "today.evening" {
  if (hour >= 5 && hour < 12) return "today.morning"
  if (hour >= 12 && hour < 18) return "today.afternoon"
  return "today.evening"
}

function show(value: string | number | null | undefined, digits: number, lang: string): string {
  return formatNumber(asNumber(value), digits, lang)
}

function BodySkeleton({ tall = false }: { tall?: boolean }) {
  return (
    <div className={`mt-4 animate-pulse rounded-xl bg-[#E5E7EB] ${tall ? "h-36" : "h-20"}`} />
  )
}

function InlineError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      <p className="text-[13px]">{t("common.loadError")}</p>
      <Button type="button" className={primaryBtn} onClick={onRetry}>
        {t("common.retry")}
      </Button>
    </div>
  )
}

function TodayHeader({
  farmName,
  timezone,
  lang,
  pending,
  failed,
  onRetry,
}: {
  farmName: string
  timezone: string | null
  lang: string
  pending: boolean
  failed: boolean
  onRetry: () => void
}) {
  const { t } = useTranslation()
  const sub = t("today.sub", { name: farmName })
  if (pending) {
    return (
      <header>
        <div className="h-3 w-56 animate-pulse rounded bg-[#E5E7EB]" />
        <div className="mt-2 h-7 w-48 animate-pulse rounded bg-[#E5E7EB]" />
        <p className="mt-1 text-mut">{sub}</p>
      </header>
    )
  }
  if (failed || timezone === null) {
    return (
      <header>
        <p className={crumbClass}>{t("nav.today")}</p>
        <h1 className="text-[24px] font-bold leading-tight">{t("nav.today")}</h1>
        <p className="mt-1 text-mut">{sub}</p>
        <InlineError onRetry={onRetry} />
      </header>
    )
  }
  const local = farmLocalNow(timezone)
  return (
    <PageHeader
      crumb={t("today.crumb", { date: formatLongDate(local.isoDate, lang) })}
      title={t(greetingKey(local.hour))}
      sub={sub}
    />
  )
}

function MetricTile({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="min-w-0 rounded-xl bg-[#F7F8F7] px-3 py-3">
      <p className="text-[12px] text-mut">{label}</p>
      <p className="mt-1 text-[18px] font-bold leading-tight">
        {value} <span className="text-[12px] font-medium text-mut">{unit}</span>
      </p>
    </div>
  )
}

function WeatherCard({
  farmId,
  timeZone,
  blockId,
  lang,
}: {
  farmId: string
  timeZone: string | null
  blockId: string | null
  lang: string
}) {
  const { t } = useTranslation()
  const nowQuery = useQuery({
    queryKey: ["weather", farmId, "now"],
    queryFn: () => apiGet<NowOut>(`/v1/farms/${farmId}/weather/now`),
    refetchInterval: 10 * 60 * 1000,
  })
  const now = nowQuery.data
  const time =
    now === undefined || now.issued_at === null || timeZone === null
      ? t("common.missing")
      : formatHour(now.issued_at, timeZone)
  return (
    <section className={`${cardClass} min-w-0 flex-1`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[16px] font-bold">{t("nav.weather")}</h2>
            <SourceTag kind="estimated" />
          </div>
          <p className="mt-1 text-[13px] text-mut">{t("today.weatherSub")}</p>
        </div>
        {blockId !== null ? (
          <Link
            to={`/blocks/${blockId}/weather`}
            className="shrink-0 text-[13px] font-semibold text-pri"
          >
            {t("today.openWeather")}
          </Link>
        ) : null}
      </div>
      {nowQuery.isLoading ? <BodySkeleton /> : null}
      {nowQuery.isError ? <InlineError onRetry={() => void nowQuery.refetch()} /> : null}
      {now !== undefined ? (
        <div className="mt-4 flex flex-col gap-3">
          <div className="grid grid-cols-5 gap-2">
            <MetricTile label={t("weather.now")} value={show(now.temp_c, 1, lang)} unit={UNIT_TEMP_C} />
            <MetricTile label={t("top.rh")} value={show(now.rh_pct, 0, lang)} unit="%" />
            <MetricTile label={t("weather.wind")} value={show(now.wind_ms, 1, lang)} unit={UNIT_WIND_M_S} />
            <MetricTile label={t("weather.rainToday")} value={show(now.rain_mm, 1, lang)} unit={UNIT_MM} />
            <MetricTile label={t("weather.et0Today")} value={show(now.et0_mm, 2, lang)} unit={UNIT_MM} />
          </div>
          {now.stale ? <p className="text-[12px] text-amb">{t("today.stale", { time })}</p> : null}
        </div>
      ) : null}
    </section>
  )
}

function warningLines(
  day: ForecastDay,
  lang: string,
  frostLabel: (hours: string, date: string) => string,
  heatLabel: (hours: string, date: string) => string,
): { key: string; tone: "frost" | "heat"; text: string }[] {
  const date = formatWeekdayDate(day.date, lang)
  const lines: { key: string; tone: "frost" | "heat"; text: string }[] = []
  if (day.frost_h !== null && day.frost_h > 0) {
    lines.push({
      key: `${day.date}-frost`,
      tone: "frost",
      text: frostLabel(formatNumber(day.frost_h, 0, lang), date),
    })
  }
  if (day.heat_h !== null && day.heat_h > 0) {
    lines.push({
      key: `${day.date}-heat`,
      tone: "heat",
      text: heatLabel(formatNumber(day.heat_h, 0, lang), date),
    })
  }
  return lines
}

function AlertsCard({
  farmId,
  lang,
  onSetThresholds,
}: {
  farmId: string
  lang: string
  onSetThresholds: () => void
}) {
  const { t } = useTranslation()
  const forecastQuery = useQuery({
    queryKey: ["weather", farmId, "forecast"],
    queryFn: () => apiGet<ForecastOut>(`/v1/farms/${farmId}/weather/forecast`),
    refetchInterval: 10 * 60 * 1000,
  })
  const thresholdsQuery = useQuery({
    queryKey: ["thresholds", farmId],
    queryFn: () => apiGet<Thresholds>(`/v1/farms/${farmId}/thresholds`),
  })
  const loading = forecastQuery.isLoading || thresholdsQuery.isLoading
  const failed = forecastQuery.isError || thresholdsQuery.isError
  const forecast = forecastQuery.data
  const thresholds = thresholdsQuery.data
  const unset =
    thresholds !== undefined && thresholds.frost_c === null && thresholds.heat_c === null
  const lines =
    forecast === undefined
      ? []
      : forecast.daily.flatMap((day) =>
          warningLines(
            day,
            lang,
            (hours, date) => t("today.frostLine", { hours, date }),
            (hours, date) => t("today.heatLine", { hours, date }),
          ),
        )
  return (
    <section className={`${cardClass} w-[340px] shrink-0`}>
      <h2 className="text-[16px] font-bold">{t("top.alerts")}</h2>
      <p className="mt-1 text-[13px] text-mut">{t("today.alertsSub")}</p>
      {loading ? <BodySkeleton /> : null}
      {failed ? (
        <InlineError
          onRetry={() => {
            void forecastQuery.refetch()
            void thresholdsQuery.refetch()
          }}
        />
      ) : null}
      {!loading && !failed && unset ? (
        <button
          type="button"
          className="mt-4 text-start text-[13px] font-semibold text-pri"
          onClick={onSetThresholds}
        >
          {t("today.setThresholds")}
        </button>
      ) : null}
      {!loading && !failed && !unset && lines.length === 0 ? (
        <p className="mt-4 text-[13px] text-mut">{t("today.noWarnings")}</p>
      ) : null}
      {!loading && !failed && !unset && lines.length > 0 ? (
        <ul className="mt-4 flex flex-col gap-2">
          {lines.map((line) => (
            <li key={line.key}>
              <span
                className={`inline-flex rounded-full px-2.5 py-1 text-[12px] font-semibold ${
                  line.tone === "frost" ? "bg-[#FEF3C7] text-amb" : "bg-[#FEE2E2] text-red"
                }`}
              >
                {line.text}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

function useBlockTotals(farmId: string, blocks: BlockListItem[]) {
  const cropIds = [
    ...new Set(blocks.flatMap((block) => (block.crop === null ? [] : [block.crop.id]))),
  ].sort()
  const settingsQuery = useQuery({
    queryKey: ["gdd-settings", farmId],
    queryFn: () => apiGet<GddSettingListItem[]>(`/v1/farms/${farmId}/gdd-settings`),
    enabled: cropIds.length > 0,
  })
  const overrideQueries = useQueries({
    queries: blocks.map((block) => ({
      queryKey: ["block-gdd-setting", block.id],
      queryFn: () => apiGet<BlockGddSetting>(`/v1/blocks/${block.id}/gdd-setting`),
    })),
  })
  const overridesReady = overrideQueries.every((query) => query.isSuccess)
  const settingsReady = cropIds.length === 0 || settingsQuery.isSuccess
  const startIds = new Set(
    (settingsQuery.data ?? [])
      .filter((row) => row.start_date !== null)
      .map((row) => row.crop_id),
  )
  const jobs: { key: readonly string[]; url: string; blockIds: string[] }[] = []
  if (overridesReady && settingsReady) {
    const byCrop = new Map<string, string[]>()
    blocks.forEach((block, index) => {
      const override = overrideQueries[index]?.data
      const cropId = block.crop?.id ?? null
      if (override?.method != null) {
        if (override.start_date !== null && cropId !== null) {
          jobs.push({
            key: ["weather", farmId, "degree-days", cropId, block.id],
            url: `/v1/farms/${farmId}/weather/degree-days?crop_id=${cropId}&block_id=${block.id}`,
            blockIds: [block.id],
          })
        }
        return
      }
      if (cropId !== null && startIds.has(cropId)) {
        const listed = byCrop.get(cropId) ?? []
        listed.push(block.id)
        byCrop.set(cropId, listed)
      }
    })
    for (const [cropId, blockIds] of byCrop) {
      jobs.push({
        key: ["weather", farmId, "degree-days", cropId],
        url: `/v1/farms/${farmId}/weather/degree-days?crop_id=${cropId}`,
        blockIds,
      })
    }
  }
  const gddQueries = useQueries({
    queries: jobs.map((job) => ({
      queryKey: job.key,
      queryFn: () => apiGet<DegreeDays>(job.url),
    })),
  })
  const totals = new Map<string, DegreeDays>()
  jobs.forEach((job, index) => {
    const row = gddQueries[index]?.data
    if (row !== undefined) {
      for (const blockId of job.blockIds) totals.set(blockId, row)
    }
  })
  return {
    totals,
    loading:
      (cropIds.length > 0 && settingsQuery.isLoading) ||
      overrideQueries.some((query) => query.isLoading) ||
      gddQueries.some((query) => query.isLoading),
    error:
      settingsQuery.isError ||
      overrideQueries.some((query) => query.isError) ||
      gddQueries.some((query) => query.isError),
    retry: () => {
      void settingsQuery.refetch()
      for (const query of overrideQueries) void query.refetch()
      for (const query of gddQueries) void query.refetch()
    },
  }
}

function StatusTag({ status }: { status: BlockStatus }) {
  const { t } = useTranslation()
  if (status === "draft") {
    return (
      <span className="shrink-0 rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[11px] font-semibold text-amb">
        {t("blocks.draft")}
      </span>
    )
  }
  if (status === "complete") {
    return (
      <span className="shrink-0 rounded-full bg-mint px-2 py-0.5 text-[11px] font-semibold text-pri">
        {t("today.complete")}
      </span>
    )
  }
  return null
}

function IrrigateMark({ status }: { status: IrrigationToday["status"] | undefined }) {
  const { t } = useTranslation()
  const soon = status === "irrigate_soon"
  const ok = status === "ok"
  return (
    <span
      className={`inline-flex w-fit rounded-full px-2 py-0.5 text-[10px] font-semibold ${
        soon ? "bg-[#FEF3C7] text-amb" : ok ? "bg-mint text-pri" : "bg-[#E5E7EB] text-mut"
      }`}
    >
      {t(soon ? "soil.statusSoon" : ok ? "soil.statusOk" : "soil.statusNotSet")}
    </span>
  )
}

function irrigateLine(
  item: FarmIrrigationToday["blocks"][number] | undefined,
  lang: string,
  label: (gross: string, hours: string, minutes: string) => string,
): string {
  const dose = item === undefined ? undefined : item.recommended === "refill" ? item.refill : item.maintain
  const run = runParts(dose?.run_time_min, lang)
  return label(formatNumber(asNumber(dose?.gross_mm), 2, lang), run.hours, run.minutes)
}

function useStageNow(farmId: string, cropIds: string[]) {
  const queries = useQueries({
    queries: cropIds.map((cropId) => ({
      queryKey: ["stage-summary", farmId, cropId],
      queryFn: () => apiGet<StageSummary>(`/v1/farms/${farmId}/stages/summary?crop_id=${cropId}`),
    })),
  })
  const byBlock = new Map<string, SummaryBlock>()
  for (const query of queries) {
    for (const block of query.data?.blocks ?? []) byBlock.set(block.block_id, block)
  }
  return {
    byBlock,
    loading: cropIds.length > 0 && queries.some((query) => query.isLoading),
    error: queries.some((query) => query.isError),
    retry: () => {
      for (const query of queries) void query.refetch()
    },
  }
}

function BlockRows({
  blocks,
  lang,
  totals,
  stages,
  stagesLoading,
  irrigate,
  irrigateLoading,
}: {
  blocks: BlockListItem[]
  lang: string
  totals: Map<string, DegreeDays>
  stages: Map<string, SummaryBlock>
  stagesLoading: boolean
  irrigate: Map<string, FarmIrrigationToday["blocks"][number]>
  irrigateLoading: boolean
}) {
  const { t } = useTranslation()
  const missing = t("common.missing")
  return (
    <div className="mt-2 overflow-x-auto">
      <div className={`${rowClass} min-w-[1040px] py-1 text-[11px] font-semibold uppercase tracking-wide text-mut`}>
        <span />
        <span />
        <span />
        <span />
        <span />
        <span />
        <span>{t("today.stageNow")}</span>
        <span>{t("today.next")}</span>
        <span>{t("today.irrigateToday")}</span>
        <span />
      </div>
      <ul className="min-w-[1040px]">
        {blocks.map((block, index) => {
          const crop = cropLabel(block.crop, lang) ?? missing
          const area =
            block.net_area_ha === null
              ? missing
              : t("blocks.netLine", { area: formatNumber(Number(block.net_area_ha), 2, lang) })
          const trees =
            block.trees_count === null
              ? missing
              : t("blocks.trees", { count: formatNumber(block.trees_count, 0, lang) })
          const flow =
            block.q_block_m3h === null
              ? missing
              : `${show(block.q_block_m3h, 2, lang)} ${t("blocks.unitFlow")}`
          const rate =
            block.rate_mm_h === null
              ? missing
              : `${show(block.rate_mm_h, 2, lang)} ${t("blocks.unitMmh")}`
          const degree = totals.get(block.id)
          let gdd = missing
          let hasTotal = false
          if (
            degree !== undefined &&
            degree.label === "calculated" &&
            degree.gdd_total !== null
          ) {
            hasTotal = true
            gdd = `${show(degree.gdd_total, 1, lang)} ${t("weather.unitCday")}`
          }
          const advice = irrigate.get(block.id)
          const stage = stages.get(block.id)
          const nowName =
            stage?.current_stage === null || stage?.current_stage === undefined
              ? missing
              : localizedName(stage.current_stage.name, lang)
          const nextName =
            stage?.next_stage === null || stage?.next_stage === undefined
              ? missing
              : localizedName(stage.next_stage.stage.name, lang)
          const nextDate =
            stage?.next_stage === null || stage?.next_stage === undefined
              ? null
              : formatMediumDate(stage.next_stage.date, lang)
          return (
            <li key={block.id} className={`${rowClass} border-b border-line hover:bg-[#F7F8F7] last:border-b-0`}>
              <Link to={`/blocks/${block.id}/setup`} className="contents">
                <span className="col-start-1 flex size-7 items-center justify-center rounded-full bg-mint text-[12px] font-bold text-pri">
                  {formatNumber(index + 1, 0, lang)}
                </span>
                <span className="col-start-2 min-w-0">
                  <span className="block truncate font-bold">{block.name}</span>
                  <span className="block truncate text-[12px] text-mut">
                    {crop}
                    <span className="px-1">·</span>
                    {area}
                  </span>
                </span>
                <span className="col-start-3 whitespace-nowrap text-[12px] text-mut">{trees}</span>
                <span className="col-start-4 whitespace-nowrap text-[12px] text-mut">{flow}</span>
                <span className="col-start-5 whitespace-nowrap text-[12px] text-mut">{rate}</span>
                <span className="col-start-6 inline-flex items-center gap-1.5 whitespace-nowrap text-[12px]">
                  <span className={hasTotal ? "font-semibold" : "text-mut"}>{gdd}</span>
                  {hasTotal ? <SourceTag kind="calculated" /> : null}
                </span>
                <span className="col-start-7 min-w-0 text-[12px]">
                  {stagesLoading ? (
                    <span className="block h-4 w-16 animate-pulse rounded bg-[#E5E7EB]" />
                  ) : (
                    <span className="block truncate">{nowName}</span>
                  )}
                </span>
                <span className="col-start-8 min-w-0 text-[12px]">
                  {stagesLoading ? (
                    <span className="block h-4 w-20 animate-pulse rounded bg-[#E5E7EB]" />
                  ) : (
                    <span className="block">
                      <span className="block truncate">{nextName}</span>
                      {nextDate !== null ? <span className="block text-mut">{nextDate}</span> : null}
                    </span>
                  )}
                </span>
                <span className="col-start-10">
                  <StatusTag status={block.status} />
                </span>
              </Link>
              <Link
                to={`/blocks/${block.id}/soil-water`}
                className="col-start-9 row-start-1 flex flex-col items-start gap-1"
              >
                {irrigateLoading ? (
                  <span className="h-8 w-28 animate-pulse rounded bg-[#E5E7EB]" />
                ) : (
                  <>
                    <IrrigateMark status={advice?.status} />
                    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[12px]">
                      {irrigateLine(advice, lang, (gross, hours, minutes) =>
                        t("today.irrigateDose", { gross, hours, minutes }),
                      )}
                      {asNumber(
                        (advice?.recommended === "refill" ? advice.refill : advice?.maintain)
                          ?.gross_mm,
                      ) !== null ? (
                        <SourceTag kind="calculated" />
                      ) : null}
                    </span>
                  </>
                )}
              </Link>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function EmptyBlocks() {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-mint text-pri">
        <Plus className="size-5" aria-hidden="true" />
      </div>
      <p className="text-[16px] font-bold">{t("nav.noBlocks")}</p>
      <p className="max-w-[420px] text-mut">{t("today.emptyText")}</p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Link to="/blocks/new" className={`inline-flex items-center ${primaryBtn}`}>
          {t("blocks.add")}
        </Link>
        <Link to="/blocks" className={`inline-flex items-center ${outlineBtn}`}>
          {t("today.openBlocks")}
        </Link>
      </div>
    </div>
  )
}

function BlocksCard({ farmId, lang }: { farmId: string; lang: string }) {
  const { t } = useTranslation()
  const blocksQuery = useQuery({
    queryKey: ["blocks", farmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${farmId}/blocks`),
  })
  const blocks = (blocksQuery.data ?? []).filter((block) => block.status !== "archived")
  const irrigateQuery = useQuery({
    queryKey: ["irrigation-today", "farm", farmId],
    queryFn: () => apiGet<FarmIrrigationToday>(`/v1/farms/${farmId}/irrigation-today`),
    enabled: blocksQuery.isSuccess && blocks.length > 0,
  })
  const irrigate = new Map((irrigateQuery.data?.blocks ?? []).map((item) => [item.block_id, item]))
  const cropIds = [
    ...new Set(blocks.flatMap((block) => (block.crop === null ? [] : [block.crop.id]))),
  ].sort()
  const degree = useBlockTotals(farmId, blocks)
  const stages = useStageNow(farmId, cropIds)
  const loading = blocksQuery.isLoading || (cropIds.length > 0 && degree.loading && !degree.error)
  return (
    <section className={`${cardClass} min-w-0 flex-1`}>
      <h2 className="text-[16px] font-bold">{t("nav.blocks")}</h2>
      <p className="mt-1 text-[13px] text-mut">{t("today.blocksSub")}</p>
      {loading ? <BodySkeleton tall /> : null}
      {blocksQuery.isError ? <InlineError onRetry={() => void blocksQuery.refetch()} /> : null}
      {!loading && blocksQuery.isSuccess && cropIds.length > 0 && degree.error ? (
        <div className="mt-3">
          <InlineError onRetry={degree.retry} />
        </div>
      ) : null}
      {!loading && blocksQuery.isSuccess && blocks.length === 0 ? <EmptyBlocks /> : null}
      {!loading && blocksQuery.isSuccess && blocks.length > 0 && irrigateQuery.isError ? (
        <div className="mt-3">
          <InlineError onRetry={() => void irrigateQuery.refetch()} />
        </div>
      ) : null}
      {!loading && blocksQuery.isSuccess && blocks.length > 0 && stages.error ? (
        <div className="mt-3">
          <InlineError onRetry={stages.retry} />
        </div>
      ) : null}
      {!loading && blocksQuery.isSuccess && blocks.length > 0 ? (
        <BlockRows
          blocks={blocks}
          lang={lang}
          totals={degree.totals}
          stages={stages.byBlock}
          stagesLoading={stages.loading}
          irrigate={irrigate}
          irrigateLoading={irrigateQuery.isLoading}
        />
      ) : null}
    </section>
  )
}

function DueCard() {
  const { t } = useTranslation()
  return (
    <section className={`${cardClass} w-[340px] shrink-0`}>
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-[16px] font-bold">{t("today.dueTitle")}</h2>
        <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
          {t("settings.phase2")}
        </span>
      </div>
      <p className="mt-1 text-[13px] text-mut">{t("today.dueSub")}</p>
      <p className="mt-3 text-[13px]">{t("today.nothingDue")}</p>
    </section>
  )
}

export function TodayPage() {
  const { i18n } = useTranslation()
  const { currentFarmId, user } = useAuth()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [thresholdsOpen, setThresholdsOpen] = useState(false)
  const farmId = currentFarmId
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmToday>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  const blocksQuery = useQuery({
    queryKey: ["blocks", farmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${farmId}/blocks`),
    enabled: farmId !== null,
  })
  if (farmId === null) return null
  const farmName = farmQuery.data?.name ?? user?.farms[0]?.name ?? ""
  const weatherBlock =
    (blocksQuery.data ?? []).find((block) => block.status !== "archived") ?? null
  return (
    <div className="flex flex-col gap-5">
      <TodayHeader
        farmName={farmName}
        timezone={farmQuery.data?.timezone ?? null}
        lang={lang}
        pending={farmQuery.isLoading}
        failed={farmQuery.isError}
        onRetry={() => void farmQuery.refetch()}
      />
      <div className="flex min-w-0 items-start gap-4">
        <WeatherCard
          farmId={farmId}
          timeZone={farmQuery.data?.timezone ?? null}
          blockId={blocksQuery.isSuccess ? weatherBlock?.id ?? null : null}
          lang={lang}
        />
        <AlertsCard farmId={farmId} lang={lang} onSetThresholds={() => setThresholdsOpen(true)} />
      </div>
      <div className="flex min-w-0 items-start gap-4">
        <BlocksCard farmId={farmId} lang={lang} />
        <DueCard />
      </div>
      <ThresholdsDrawer farmId={farmId} open={thresholdsOpen} onOpenChange={setThresholdsOpen} />
    </div>
  )
}
