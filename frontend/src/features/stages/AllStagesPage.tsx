import { useQueries, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { activeLang, cropLabel, localizedName, type BlockListItem, type CatalogCrop } from "../blocks/types"
import { formatMediumDate } from "../weather/format"
import { ChoiceChip, LoadError, PageHeader, PageSkeleton, cardClass, outlineBtn, primaryBtn } from "../weather/ui"
import type { StageSummary } from "./types"

export function AllStagesPage() {
  const { t, i18n } = useTranslation()
  const { currentFarmId } = useAuth()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [cropId, setCropId] = useState("all")
  const farmId = currentFarmId
  const cropsQuery = useQuery({
    queryKey: ["catalog", "crops"],
    queryFn: () => apiGet<CatalogCrop[]>("/v1/catalog/crops"),
  })
  const blocksQuery = useQuery({
    queryKey: ["blocks", farmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${farmId}/blocks`),
    enabled: farmId !== null,
  })
  const crops = cropsQuery.data ?? []
  const blocks = (blocksQuery.data ?? []).filter((block) => block.status !== "archived")
  const selected = cropId === "all" ? crops.map((crop) => crop.id) : [cropId]
  const summaries = useQueries({
    queries: selected.map((id) => ({
      queryKey: ["stage-summary", farmId, id],
      queryFn: () => apiGet<StageSummary>(`/v1/farms/${farmId}/stages/summary?crop_id=${id}`),
      enabled: farmId !== null && blocksQuery.isSuccess && blocks.length > 0,
    })),
  })

  if (farmId === null) return null
  if (cropsQuery.isPending || blocksQuery.isPending) return <PageSkeleton />
  if (cropsQuery.isError || blocksQuery.isError || cropsQuery.data === undefined || blocksQuery.data === undefined) {
    return (
      <LoadError
        onRetry={() => {
          void cropsQuery.refetch()
          void blocksQuery.refetch()
        }}
      />
    )
  }
  const summaryError = summaries.some((query) => query.isError)
  const summaryLoading = blocks.length > 0 && summaries.some((query) => query.isLoading)
  const cropName = new Map(crops.map((crop) => [crop.id, localizedName(crop.name, lang)]))
  const rows = summaries.flatMap((query, index) => {
    const id = selected[index]
    if (query.data === undefined || id === undefined) return []
    return query.data.blocks.map((block) => ({ ...block, crop: cropName.get(id) ?? t("common.missing") }))
  })
  if (cropId === "all") {
    const seen = new Set(rows.map((row) => row.block_id))
    for (const block of blocks) {
      if (seen.has(block.id)) continue
      rows.push({
        block_id: block.id,
        name: block.name,
        season_id: null,
        year: 0,
        current_stage: null,
        next_stage: null,
        crop: cropLabel(block.crop, lang) ?? t("common.missing"),
      })
    }
  }
  rows.sort((left, right) => left.name.localeCompare(right.name, lang))

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("nav.blocks")}
        title={t("stages.allTitle")}
        sub={t("stages.allSub")}
        actions={
          <Link to="/blocks" className={`inline-flex items-center ${outlineBtn}`}>
            {t("stages.backToBlocks")}
          </Link>
        }
      />
      <div className="flex flex-wrap gap-2">
        <ChoiceChip selected={cropId === "all"} onClick={() => setCropId("all")}>
          {t("stages.all")}
        </ChoiceChip>
        {crops.map((crop) => (
          <ChoiceChip key={crop.id} selected={crop.id === cropId} onClick={() => setCropId(crop.id)}>
            {localizedName(crop.name, lang)}
          </ChoiceChip>
        ))}
      </div>
      <section className={cardClass}>
        <h2 className="text-[16px] font-bold">{t("nav.blocks")}</h2>
        {summaryLoading ? <div className="mt-4 h-40 animate-pulse rounded-xl bg-[#E5E7EB]" /> : null}
        {summaryError ? (
          <div className="mt-4">
            <LoadError
              onRetry={() => {
                for (const query of summaries) void query.refetch()
              }}
            />
          </div>
        ) : null}
        {!summaryLoading && !summaryError && blocks.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-14 text-center">
            <p className="text-[16px] font-bold">{t("nav.noBlocks")}</p>
            <p className="max-w-[420px] text-[13px] text-mut">{t("stages.noBlocksText")}</p>
            <Link to="/blocks/new" className={`inline-flex items-center ${primaryBtn}`}>
              {t("blocks.add")}
            </Link>
          </div>
        ) : null}
        {!summaryLoading && !summaryError && blocks.length > 0 ? (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[640px] text-start text-[13px]">
              <thead>
                <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-wide text-mut">
                  <th className="px-2 py-2 font-semibold">{t("stages.colBlock")}</th>
                  <th className="px-2 py-2 font-semibold">{t("stages.colCrop")}</th>
                  <th className="px-2 py-2 font-semibold">{t("stages.colNow")}</th>
                  <th className="px-2 py-2 font-semibold">{t("stages.colNext")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-2 py-10 text-center text-mut">
                      {t("nav.noBlocks")}
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr key={row.block_id} className="border-b border-line last:border-b-0">
                      <td className="px-2 py-3 font-semibold">
                        <Link to={`/blocks/${row.block_id}/stages`} className="hover:underline">
                          {row.name}
                        </Link>
                      </td>
                      <td className="px-2 py-3 text-mut">{row.crop}</td>
                      <td className="px-2 py-3">
                        {row.current_stage === null
                          ? t("common.missing")
                          : localizedName(row.current_stage.name, lang)}
                      </td>
                      <td className="px-2 py-3">
                        {row.next_stage === null ? (
                          t("common.missing")
                        ) : (
                          <span>
                            <span className="block">{localizedName(row.next_stage.stage.name, lang)}</span>
                            <span className="block text-[12px] text-mut">
                              {formatMediumDate(row.next_stage.date, lang)}
                            </span>
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  )
}
