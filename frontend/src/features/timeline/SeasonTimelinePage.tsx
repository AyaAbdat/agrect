import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, Plus } from "lucide-react"
import { useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { activeLang, type BlockListItem } from "../blocks/types"
import type { HarvestList } from "../harvest/types"
import type { JournalList } from "../journal/types"
import type { FarmClock } from "../soilwater/types"
import { readBlockStages } from "../stages/load"
import { farmToday } from "../weather/format"
import {
  ChoiceChip,
  LoadError,
  PageHeader,
  PageSkeleton,
  primaryBtn,
} from "../weather/ui"
import {
  buildHarvestMarkers,
  buildIrrigationBins,
  buildOpMarkers,
  buildStageMarkers,
  buildYearBar,
  cropPalette,
  monthLabels,
  type TimelineRowData,
  type TimelineSpan,
} from "./model"
import { TimelineGrid } from "./TimelineGrid"

export function SeasonTimelinePage() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId
  const [span, setSpan] = useState<TimelineSpan>("this")

  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  const blocksQuery = useQuery({
    queryKey: ["blocks", farmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${farmId}/blocks`),
    enabled: farmId !== null,
  })

  const todayIso = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)
  const currentYear = todayIso === null ? null : Number(todayIso.slice(0, 4))
  const years = useMemo(() => {
    if (currentYear === null) return []
    return span === "this" ? [currentYear] : [currentYear - 1, currentYear]
  }, [currentYear, span])

  const completeBlocks = useMemo(() => {
    const list = (blocksQuery.data ?? []).filter((block) => block.status === "complete")
    return [...list].sort((left, right) => left.name.localeCompare(right.name, lang))
  }, [blocksQuery.data, lang])

  const stagePairs = useMemo(
    () =>
      completeBlocks.flatMap((block) =>
        years.map((year) => ({ blockId: block.id, year })),
      ),
    [completeBlocks, years],
  )

  const stageQueries = useQueries({
    queries: stagePairs.map((pair) => ({
      queryKey: ["stages", pair.blockId, pair.year],
      queryFn: () => readBlockStages(pair.blockId, pair.year),
      enabled: years.length > 0,
    })),
  })

  const harvestQueries = useQueries({
    queries: completeBlocks.map((block) => ({
      queryKey: ["harvest", block.id],
      queryFn: () => apiGet<HarvestList>(`/v1/blocks/${block.id}/harvest`),
      enabled: years.length > 0,
    })),
  })

  const fromDate = years.length > 0 ? `${years[0]}-01-01` : ""
  const toDate = years.length > 0 ? `${years[years.length - 1]}-12-31` : ""

  const journalQueries = useQueries({
    queries: completeBlocks.map((block) => ({
      queryKey: ["timeline-journal", block.id, fromDate, toDate],
      queryFn: () =>
        apiGet<JournalList>(`/v1/blocks/${block.id}/journal?from=${fromDate}&to=${toDate}`),
      enabled: years.length > 0,
    })),
  })

  if (farmId === null) return null
  if (farmQuery.isPending || blocksQuery.isPending || todayIso === null || currentYear === null) {
    return <PageSkeleton />
  }
  if (
    farmQuery.isError ||
    blocksQuery.isError ||
    farmQuery.data === undefined ||
    blocksQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void queryClient.invalidateQueries({ queryKey: ["farm", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["blocks", farmId] })
        }}
      />
    )
  }

  const yearsPerBlock = years.length
  const rows: TimelineRowData[] = completeBlocks.map((block, blockIdx) => {
    const blockStageQueries = stageQueries.slice(
      blockIdx * yearsPerBlock,
      (blockIdx + 1) * yearsPerBlock,
    )
    const harvestQuery = harvestQueries[blockIdx]
    const journalQuery = journalQueries[blockIdx]

    const stagesByYear = blockStageQueries.map((query) => query.data)
    const harvests = harvestQuery?.data?.entries ?? []
    const journalItems = journalQuery?.data?.items ?? []

    const bars = years
      .map((year, yearIdx) => buildYearBar(year, stagesByYear[yearIdx], harvests, years))
      .filter((bar) => bar !== null)

    const partialError =
      blockStageQueries.some((query) => query.isError) ||
      Boolean(harvestQuery?.isError) ||
      Boolean(journalQuery?.isError)

    const loading =
      blockStageQueries.some((query) => query.isLoading) ||
      Boolean(harvestQuery?.isLoading) ||
      Boolean(journalQuery?.isLoading)

    return {
      block,
      palette: cropPalette(block.crop?.code),
      bars,
      stages: buildStageMarkers(stagesByYear, years),
      harvests: buildHarvestMarkers(harvests, years),
      operations: buildOpMarkers(journalItems, years),
      irrigations: buildIrrigationBins(journalItems, years),
      partialError,
      loading,
    }
  })

  const hasPartialError = rows.some((row) => row.partialError)

  function retryFailed() {
    for (const query of stageQueries) {
      if (query.isError) void query.refetch()
    }
    for (const query of harvestQueries) {
      if (query.isError) void query.refetch()
    }
    for (const query of journalQueries) {
      if (query.isError) void query.refetch()
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("nav.farm")}
        title={t("nav.seasonTimeline")}
        sub={t("timeline.sub")}
        actions={
          <button
            type="button"
            disabled
            aria-disabled="true"
            title={t("timeline.addCropHint")}
            className="inline-flex h-9 cursor-not-allowed items-center gap-2 rounded-full border border-line bg-[#F3F5F3] px-3.5 text-[13px] font-semibold text-mut"
          >
            <Plus className="size-4" aria-hidden="true" />
            <span>{t("timeline.addCrop")}</span>
            <span className="rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
              {t("timeline.phase2")}
            </span>
          </button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <ChoiceChip selected={span === "this"} onClick={() => setSpan("this")}>
          {t("timeline.thisSeason")}
        </ChoiceChip>
        <ChoiceChip selected={span === "two"} onClick={() => setSpan("two")}>
          {t("timeline.twoSeasons")}
        </ChoiceChip>
      </div>

      {hasPartialError ? (
        <div className="flex items-center justify-between gap-3 rounded-xl bg-[#FEF3C7] px-4 py-2.5 text-[13px] text-amb">
          <span className="inline-flex items-center gap-2">
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
            {t("timeline.partialWarning")}
          </span>
          <button
            type="button"
            onClick={retryFailed}
            className="shrink-0 rounded-full border border-amb/30 bg-white/80 px-3 py-1 text-[12px] font-semibold text-amb hover:bg-white"
          >
            {t("common.retry")}
          </button>
        </div>
      ) : null}

      {completeBlocks.length === 0 ? (
        <section className="overflow-hidden rounded-2xl border border-line bg-white">
          <div className="overflow-x-auto" dir="ltr">
            <div className="flex min-w-[760px] items-center border-b border-line bg-white px-5 py-3">
              <div
                className="w-[180px] shrink-0 text-[11px] font-semibold uppercase tracking-wider text-mut"
                dir={lang === "ar" ? "rtl" : "ltr"}
              >
                {t("timeline.colBlock")}
              </div>
              <div className="grid flex-1 grid-cols-12">
                {monthLabels(lang).map((label, idx) => (
                  <span key={idx} className="text-center text-[11px] font-medium text-mut">
                    {label}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="flex flex-col items-center justify-center gap-3 px-6 py-20 text-center">
            <div className="flex size-11 items-center justify-center rounded-xl bg-mint text-pri">
              <Plus className="size-5" aria-hidden="true" />
            </div>
            <p className="text-[15px] font-bold text-text">{t("timeline.emptyTitle")}</p>
            <p className="max-w-[340px] text-[13px] leading-relaxed text-mut">
              {t("timeline.emptyText")}
            </p>
            <Link to="/blocks/new" className={`mt-1 inline-flex items-center gap-1.5 ${primaryBtn}`}>
              <Plus className="size-4" aria-hidden="true" />
              <span>{t("timeline.addCrop")}</span>
            </Link>
          </div>
        </section>
      ) : (
        <TimelineGrid rows={rows} years={years} todayIso={todayIso} lang={lang} />
      )}
    </div>
  )
}
