import { useQueries, useQuery } from "@tanstack/react-query"
import { Check } from "lucide-react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import type { BlockListItem } from "../blocks/types"
import type { BlockCosts } from "../inventories/types"
import type { IrrigationSettings, SoilProfile } from "../soilwater/types"
import type { FarmStation } from "../station/types"
import type { GddSettingListItem, NowOut, Thresholds } from "../weather/types"
import { cardClass, outlineBtn } from "../weather/ui"
import { hideChecklist, useChecklistForceShow } from "./checklistVisibility"

type FarmCheck = {
  id: string
  name: string
  lat: string | number | null
  lon: string | number | null
  timezone: string
}

type StepStatus = "loading" | "error" | "done" | "todo"

type StepItem = {
  id: string
  status: StepStatus
  titleKey: string
  whyKey: string
  to?: string
  onOpen?: () => void
  onRetry?: () => void
}

function hasCoord(value: string | number | null | undefined): boolean {
  if (value === null || value === undefined || value === "") return false
  const num = typeof value === "number" ? value : Number(value)
  return Number.isFinite(num)
}

function StepCircle({ status }: { status: StepStatus }) {
  if (status === "done") {
    return (
      <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-pri text-white">
        <Check className="size-3.5" strokeWidth={2.5} aria-hidden="true" />
      </span>
    )
  }
  if (status === "loading") {
    return (
      <span
        className="mt-0.5 size-5 shrink-0 animate-pulse rounded-full border-2 border-[#C7D2C9] bg-[#F3F5F3]"
        aria-hidden="true"
      />
    )
  }
  if (status === "error") {
    return (
      <span
        className="mt-0.5 size-5 shrink-0 rounded-full border-2 border-amb bg-[#FEF3C7]"
        aria-hidden="true"
      />
    )
  }
  return (
    <span
      className="mt-0.5 size-5 shrink-0 rounded-full border-2 border-[#C7D2C9] bg-white"
      aria-hidden="true"
    />
  )
}

export function GettingStartedCard({
  farmId,
  lang,
  onOpenThresholds,
}: {
  farmId: string
  lang: string
  onOpenThresholds: () => void
}) {
  const { t } = useTranslation()
  const forceShow = useChecklistForceShow(farmId)
  const season = new Date().getFullYear()

  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmCheck>(`/v1/farms/${farmId}`),
  })
  const blocksQuery = useQuery({
    queryKey: ["blocks", farmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${farmId}/blocks`),
  })
  const nowQuery = useQuery({
    queryKey: ["weather", farmId, "now"],
    queryFn: () => apiGet<NowOut>(`/v1/farms/${farmId}/weather/now`),
    refetchInterval: 10 * 60 * 1000,
  })
  const gddQuery = useQuery({
    queryKey: ["gdd-settings", farmId],
    queryFn: () => apiGet<GddSettingListItem[]>(`/v1/farms/${farmId}/gdd-settings`),
  })
  const thresholdsQuery = useQuery({
    queryKey: ["thresholds", farmId],
    queryFn: () => apiGet<Thresholds>(`/v1/farms/${farmId}/thresholds`),
  })
  const stationQuery = useQuery({
    queryKey: ["station", farmId],
    queryFn: () => apiGet<FarmStation>(`/v1/farms/${farmId}/station`),
  })

  const activeBlocks = (blocksQuery.data ?? []).filter((block) => block.status !== "archived")
  const completeBlocks = activeBlocks.filter((block) => block.status === "complete")
  const firstBlock = completeBlocks[0] ?? activeBlocks[0] ?? null

  const soilQueries = useQueries({
    queries: completeBlocks.map((block) => ({
      queryKey: ["soil", block.id],
      queryFn: () => apiGet<SoilProfile>(`/v1/blocks/${block.id}/soil`),
    })),
  })
  const irrigationQueries = useQueries({
    queries: completeBlocks.map((block) => ({
      queryKey: ["irrigation-settings", block.id],
      queryFn: () => apiGet<IrrigationSettings>(`/v1/blocks/${block.id}/irrigation-settings`),
    })),
  })
  const costQueries = useQueries({
    queries: activeBlocks.map((block) => ({
      queryKey: ["block-costs", block.id, season],
      queryFn: () => apiGet<BlockCosts>(`/v1/blocks/${block.id}/costs?season=${season}`),
    })),
  })

  // Step 1: Farm location set
  const locationSet =
    farmQuery.data !== undefined &&
    hasCoord(farmQuery.data.lat) &&
    hasCoord(farmQuery.data.lon)
  const step1Status: StepStatus = farmQuery.isLoading
    ? "loading"
    : farmQuery.isError
      ? "error"
      : locationSet
        ? "done"
        : "todo"

  // Step 2: First block completed
  const step2Status: StepStatus = blocksQuery.isLoading
    ? "loading"
    : blocksQuery.isError
      ? "error"
      : completeBlocks.length > 0
        ? "done"
        : "todo"

  // Step 3: Weather loaded
  const weatherLoaded =
    nowQuery.data !== undefined &&
    (nowQuery.data.temp_c !== null || nowQuery.data.issued_at !== null)
  const step3Status: StepStatus =
    farmQuery.isSuccess && !locationSet
      ? "todo"
      : nowQuery.isLoading
        ? "loading"
        : nowQuery.isError
          ? "error"
          : weatherLoaded
            ? "done"
            : "todo"

  // Step 4: Degree-day settings for each crop in use
  const completeCropIds = [
    ...new Set(completeBlocks.flatMap((block) => (block.crop === null ? [] : [block.crop.id]))),
  ]
  const configuredCropIds = new Set((gddQuery.data ?? []).map((row) => row.crop_id))
  const step4Status: StepStatus =
    blocksQuery.isLoading || gddQuery.isLoading
      ? "loading"
      : blocksQuery.isError || gddQuery.isError
        ? "error"
        : completeCropIds.length > 0 && completeCropIds.every((id) => configuredCropIds.has(id))
          ? "done"
          : "todo"

  // Step 5: Frost and heat thresholds
  const step5Status: StepStatus = thresholdsQuery.isLoading
    ? "loading"
    : thresholdsQuery.isError
      ? "error"
      : thresholdsQuery.data !== undefined &&
          thresholdsQuery.data.frost_c !== null &&
          thresholdsQuery.data.heat_c !== null
        ? "done"
        : "todo"

  // Step 6: Soil and irrigation settings for each complete block
  const soilLoading =
    blocksQuery.isLoading ||
    soilQueries.some((q) => q.isLoading) ||
    irrigationQueries.some((q) => q.isLoading)
  const soilError =
    blocksQuery.isError ||
    soilQueries.some((q) => q.isError) ||
    irrigationQueries.some((q) => q.isError)
  const firstIncompleteSoilBlock =
    completeBlocks.find((_, index) => {
      const soil = soilQueries[index]?.data
      const settings = irrigationQueries[index]?.data
      const ready =
        soil !== undefined &&
        soil.label === "calculated" &&
        settings !== undefined &&
        settings.kc !== null &&
        settings.efficiency !== null
      return !ready
    }) ?? completeBlocks[0]
  const allSoilReady =
    completeBlocks.length > 0 &&
    completeBlocks.every((_, index) => {
      const soil = soilQueries[index]?.data
      const settings = irrigationQueries[index]?.data
      return (
        soil !== undefined &&
        soil.label === "calculated" &&
        settings !== undefined &&
        settings.kc !== null &&
        settings.efficiency !== null
      )
    })
  const step6Status: StepStatus = soilLoading
    ? "loading"
    : soilError
      ? "error"
      : allSoilReady
        ? "done"
        : "todo"

  // Step 7: Fertigation station (at least one pump)
  const step7Status: StepStatus = stationQuery.isLoading
    ? "loading"
    : stationQuery.isError
      ? "error"
      : stationQuery.data !== undefined && stationQuery.data.pumps.length > 0
        ? "done"
        : "todo"

  // Step 8: Prices for products in use (block costs missing_prices empty for every block)
  const costsLoading = blocksQuery.isLoading || costQueries.some((q) => q.isLoading)
  const costsError = blocksQuery.isError || costQueries.some((q) => q.isError)
  const allPricesPresent =
    activeBlocks.length > 0 &&
    costQueries.length === activeBlocks.length &&
    costQueries.every((q) => q.data !== undefined && q.data.missing_prices.length === 0)
  const step8Status: StepStatus = costsLoading
    ? "loading"
    : costsError
      ? "error"
      : allPricesPresent
        ? "done"
        : "todo"

  const steps: StepItem[] = [
    {
      id: "location",
      status: step1Status,
      titleKey: "today.checklist.steps.location.title",
      whyKey: "today.checklist.steps.location.why",
      to: "/settings/farm-details",
      onRetry: () => void farmQuery.refetch(),
    },
    {
      id: "block",
      status: step2Status,
      titleKey: "today.checklist.steps.block.title",
      whyKey: "today.checklist.steps.block.why",
      to: "/blocks",
      onRetry: () => void blocksQuery.refetch(),
    },
    {
      id: "weather",
      status: step3Status,
      titleKey: "today.checklist.steps.weather.title",
      whyKey: "today.checklist.steps.weather.why",
      to: firstBlock !== null ? `/blocks/${firstBlock.id}/weather` : "/blocks",
      onRetry: () => void nowQuery.refetch(),
    },
    {
      id: "gdd",
      status: step4Status,
      titleKey: "today.checklist.steps.gdd.title",
      whyKey: "today.checklist.steps.gdd.why",
      to: firstBlock !== null ? `/blocks/${firstBlock.id}/weather/degree-day-settings` : "/blocks",
      onRetry: () => {
        void blocksQuery.refetch()
        void gddQuery.refetch()
      },
    },
    {
      id: "thresholds",
      status: step5Status,
      titleKey: "today.checklist.steps.thresholds.title",
      whyKey: "today.checklist.steps.thresholds.why",
      onOpen: onOpenThresholds,
      onRetry: () => void thresholdsQuery.refetch(),
    },
    {
      id: "soil",
      status: step6Status,
      titleKey: "today.checklist.steps.soil.title",
      whyKey: "today.checklist.steps.soil.why",
      to:
        firstIncompleteSoilBlock !== undefined
          ? `/blocks/${firstIncompleteSoilBlock.id}/soil-water/soil`
          : "/blocks",
      onRetry: () => {
        void blocksQuery.refetch()
        for (const q of soilQueries) void q.refetch()
        for (const q of irrigationQueries) void q.refetch()
      },
    },
    {
      id: "station",
      status: step7Status,
      titleKey: "today.checklist.steps.station.title",
      whyKey: "today.checklist.steps.station.why",
      to: "/station",
      onRetry: () => void stationQuery.refetch(),
    },
    {
      id: "prices",
      status: step8Status,
      titleKey: "today.checklist.steps.prices.title",
      whyKey: "today.checklist.steps.prices.why",
      to: "/settings/inventories?tab=prices",
      onRetry: () => {
        void blocksQuery.refetch()
        for (const q of costQueries) void q.refetch()
      },
    },
  ]

  const total = steps.length
  const doneCount = steps.filter((step) => step.status === "done").length
  const allDone = doneCount === total

  if (allDone && !forceShow) return null

  const pct = Math.round((doneCount / total) * 100)

  return (
    <section className={cardClass}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[16px] font-bold">{t("today.checklist.title")}</h2>
          <p className="mt-1 text-[13px] text-mut">{t("today.checklist.sub")}</p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-[13px] font-semibold text-pri">
            {t("today.checklist.progress", {
              done: formatNumber(doneCount, 0, lang),
              total: formatNumber(total, 0, lang),
            })}
          </span>
          {allDone && forceShow ? (
            <button
              type="button"
              onClick={() => hideChecklist(farmId)}
              className="text-[12px] font-semibold text-mut hover:text-text"
            >
              {t("today.checklist.hide")}
            </button>
          ) : null}
        </div>
      </div>

      <div
        className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[#E5E7EB]"
        role="progressbar"
        aria-valuenow={doneCount}
        aria-valuemin={0}
        aria-valuemax={total}
      >
        <div
          className="h-full rounded-full bg-pri transition-[width] duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>

      <ul className="mt-3 divide-y divide-line">
        {steps.map((step) => (
          <li key={step.id} className="flex items-start justify-between gap-3 py-3 first:pt-2 last:pb-1">
            <div className="flex min-w-0 items-start gap-3">
              <StepCircle status={step.status} />
              <div className="min-w-0">
                <p
                  className={`text-[13px] font-semibold ${
                    step.status === "done" ? "text-mut line-through" : "text-text"
                  }`}
                >
                  {t(step.titleKey)}
                </p>
                <p className="mt-0.5 text-[12px] text-mut">{t(step.whyKey)}</p>
                {step.status === "error" ? (
                  <p className="mt-1 flex items-center gap-2 text-[12px] text-amb">
                    <span>{t("today.checklist.stepError")}</span>
                    {step.onRetry !== undefined ? (
                      <button
                        type="button"
                        onClick={step.onRetry}
                        className="font-semibold text-pri underline"
                      >
                        {t("common.retry")}
                      </button>
                    ) : null}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="shrink-0">
              {step.to !== undefined ? (
                <Link to={step.to} className={`inline-flex items-center ${outlineBtn}`}>
                  {t("today.checklist.open")}
                </Link>
              ) : (
                <button type="button" onClick={step.onOpen} className={outlineBtn}>
                  {t("today.checklist.open")}
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
