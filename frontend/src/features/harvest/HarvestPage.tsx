import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "../../app/auth"
import { apiGet, apiSend } from "../../lib/api"
import { varietyName } from "../blocks/display"
import {
  activeLang,
  type BlockDetail,
  type BlockListItem,
  type CatalogVariety,
} from "../blocks/types"
import { ConfirmDialog } from "../station/dialog"
import type { FarmClock } from "../soilwater/types"
import { farmToday, formatMediumDate } from "../weather/format"
import {
  ChoiceChip,
  LoadError,
  PageHeader,
  PageSkeleton,
  SourceTag,
  cardClass,
  primaryBtn,
} from "../weather/ui"
import {
  basisLabel,
  densityText,
  entryInSeason,
  massText,
  quantityText,
  seasonYears,
  unitLabel,
} from "./display"
import { harvestErrorState } from "./errors"
import { RegisterHarvestDrawer } from "./RegisterHarvestDrawer"
import type { HarvestEntry, HarvestFarmSummary, HarvestList } from "./types"

type Tab = "registration" | "forecast"

function PhaseTag({ label }: { label: string }) {
  return (
    <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
      {label}
    </span>
  )
}

export function HarvestPage() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId
  const [tab, setTab] = useState<Tab>("registration")
  const [season, setSeason] = useState<number | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editing, setEditing] = useState<HarvestEntry | null>(null)
  const [pendingDelete, setPendingDelete] = useState<HarvestEntry | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  const today = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)
  const currentYear = today === null ? null : Number(today.slice(0, 4))
  const selectedSeason = season ?? currentYear
  const blocksQuery = useQuery({
    queryKey: ["blocks", farmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${farmId}/blocks`),
    enabled: farmId !== null,
  })
  const blocks = blocksQuery.data ?? []
  const completeBlocks = blocks.filter((block) => block.status === "complete")
  const summaryQuery = useQuery({
    queryKey: ["harvest-summary", farmId, selectedSeason],
    queryFn: () =>
      apiGet<HarvestFarmSummary>(
        `/v1/farms/${farmId}/harvest/summary?season=${selectedSeason ?? 0}`,
      ),
    enabled: farmId !== null && selectedSeason !== null,
  })
  const harvestQueries = useQueries({
    queries: completeBlocks.map((block) => ({
      queryKey: ["harvest", block.id],
      queryFn: () => apiGet<HarvestList>(`/v1/blocks/${block.id}/harvest`),
    })),
  })
  const detailQueries = useQueries({
    queries: completeBlocks.map((block) => ({
      queryKey: ["block", block.id],
      queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${block.id}`),
    })),
  })
  const cropIds = useMemo(() => {
    const ids = new Set<string>()
    for (const query of detailQueries) {
      const cropId = query.data?.crop?.id
      if (cropId !== undefined) ids.add(cropId)
    }
    return [...ids]
  }, [detailQueries])
  const varietyQueries = useQueries({
    queries: cropIds.map((cropId) => ({
      queryKey: ["catalog", "varieties", cropId],
      queryFn: () => apiGet<CatalogVariety[]>(`/v1/catalog/crops/${cropId}/varieties`),
    })),
  })

  if (farmId === null) return null
  const harvestLoading = harvestQueries.some((query) => query.isLoading)
  const detailLoading = detailQueries.some((query) => query.isLoading)
  const varietyLoading = varietyQueries.some((query) => query.isLoading)
  if (
    farmQuery.isPending ||
    blocksQuery.isPending ||
    summaryQuery.isLoading ||
    harvestLoading ||
    detailLoading ||
    varietyLoading ||
    selectedSeason === null
  ) {
    return <PageSkeleton />
  }
  const harvestFailed = harvestQueries.some((query) => query.isError)
  const detailFailed = detailQueries.some((query) => query.isError)
  const varietyFailed = varietyQueries.some((query) => query.isError)
  if (
    farmQuery.isError ||
    blocksQuery.isError ||
    summaryQuery.isError ||
    harvestFailed ||
    detailFailed ||
    varietyFailed ||
    farmQuery.data === undefined ||
    blocksQuery.data === undefined ||
    summaryQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void queryClient.invalidateQueries({ queryKey: ["farm", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["blocks", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["harvest-summary", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["harvest"] })
          void queryClient.invalidateQueries({ queryKey: ["block"] })
          void queryClient.invalidateQueries({ queryKey: ["catalog", "varieties"] })
        }}
      />
    )
  }

  const zone = farmQuery.data.timezone
  const summary = summaryQuery.data
  const missing = t("common.missing")
  const blockById = new Map(completeBlocks.map((block) => [block.id, block]))
  const detailById = new Map<string, BlockDetail>()
  for (const query of detailQueries) {
    if (query.data !== undefined) detailById.set(query.data.id, query.data)
  }
  const varietiesByCrop = new Map<string, CatalogVariety[]>()
  cropIds.forEach((cropId, index) => {
    const data = varietyQueries[index]?.data
    if (data !== undefined) varietiesByCrop.set(cropId, data)
  })
  const valveName = (blockId: string, valveId: string | null): string | null => {
    if (valveId === null) return null
    const detail = detailById.get(blockId)
    return detail?.valves.find((valve) => valve.id === valveId)?.name ?? null
  }
  const varietyFor = (blockId: string): string => {
    const detail = detailById.get(blockId)
    if (detail === undefined) return missing
    const cropId = detail.crop?.id
    const named = varietyName(
      detail.plantings[0],
      cropId === undefined ? [] : (varietiesByCrop.get(cropId) ?? []),
    )
    return named ?? missing
  }

  const entries: HarvestEntry[] = []
  for (const query of harvestQueries) {
    if (query.data === undefined) continue
    for (const entry of query.data.entries) {
      if (entryInSeason(entry, selectedSeason)) entries.push(entry)
    }
  }
  entries.sort((left, right) => {
    if (left.date !== right.date) return right.date.localeCompare(left.date)
    if (left.pass_no !== right.pass_no) return right.pass_no - left.pass_no
    return right.id.localeCompare(left.id)
  })

  const blockSummaries = summary.blocks
    .filter((row) => row.passes > 0 || asPositive(row.kg_total))
    .map((row) => ({
      ...row,
      name: blockById.get(row.block_id)?.name ?? missing,
    }))
    .sort((left, right) => left.name.localeCompare(right.name, lang))

  function openCreate() {
    setEditing(null)
    setDrawerOpen(true)
  }

  function openEdit(entry: HarvestEntry) {
    setEditing(entry)
    setDrawerOpen(true)
  }

  async function confirmDelete() {
    if (pendingDelete === null) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiSend(
        "DELETE",
        `/v1/blocks/${pendingDelete.block_id}/harvest/${pendingDelete.id}`,
        undefined,
        { "If-Match": String(pendingDelete.version) },
      )
    } catch (error) {
      const parsed = harvestErrorState(error)
      setDeleting(false)
      setDeleteError(parsed.form ?? "harvest.errors.delete")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["harvest"] })
    await queryClient.invalidateQueries({ queryKey: ["harvest-summary", farmId] })
    setDeleting(false)
    setPendingDelete(null)
  }

  const years = seasonYears(selectedSeason)
  const farmKg = massText(summary.farm.kg_total, lang)
  const farmDensity =
    summary.farm.kg_ha === null ? missing : densityText(summary.farm.kg_ha, lang)

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("nav.farm")}
        title={t("nav.harvest")}
        sub={t("harvest.sub")}
        actions={
          <button type="button" className={primaryBtn} onClick={openCreate}>
            {t("harvest.register")}
          </button>
        }
      />
      <div className="flex flex-wrap gap-2">
        <ChoiceChip selected={tab === "registration"} onClick={() => setTab("registration")}>
          {t("harvest.tabRegistration")}
        </ChoiceChip>
        <ChoiceChip selected={tab === "forecast"} onClick={() => setTab("forecast")}>
          {t("harvest.tabForecast")}
        </ChoiceChip>
      </div>

      {tab === "forecast" ? (
        <section className={`${cardClass} flex flex-col items-center gap-3 px-6 py-16 text-center`}>
          <PhaseTag label={t("harvest.phase3")} />
          <p className="text-[16px] font-bold">{t("harvest.forecastEmpty")}</p>
        </section>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3">
            <section className={cardClass}>
              <p className="text-[12px] text-mut">{t("harvest.harvestedTile")}</p>
              <p className="mt-2 text-[20px] font-bold leading-tight" dir="ltr">
                {farmKg}{" "}
                <span className="text-[12px] font-medium text-mut">{t("harvest.unit.kg")}</span>
              </p>
            </section>
            <section className={cardClass}>
              <div className="flex items-start justify-between gap-2">
                <p className="min-w-0 text-[12px] text-mut">{t("harvest.yieldTile")}</p>
                {summary.farm.kg_ha !== null ? <SourceTag kind="calculated" /> : null}
              </div>
              <p className="mt-2 text-[20px] font-bold leading-tight" dir="ltr">
                {farmDensity}{" "}
                <span className="text-[12px] font-medium text-mut">{t("overview.yieldUnit")}</span>
              </p>
              <p className="mt-1 text-[12px] text-mut">{t("overview.onNetArea")}</p>
            </section>
            <section className={cardClass}>
              <div className="flex items-start justify-between gap-2">
                <p className="min-w-0 text-[12px] text-mut">{t("harvest.forecastTile")}</p>
                <PhaseTag label={t("harvest.phase3")} />
              </div>
              <p className="mt-2 text-[20px] font-bold leading-tight">{missing}</p>
            </section>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label className="text-[13px] font-semibold" htmlFor="harvest-season">
              {t("harvest.season")}
            </label>
            <select
              id="harvest-season"
              className="h-9 rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px]"
              value={selectedSeason}
              onChange={(change) => setSeason(Number(change.target.value))}
            >
              {years.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>

          <section className={cardClass}>
            <h2 className="text-[16px] font-bold">{t("harvest.registrations")}</h2>
            {entries.length === 0 ? (
              <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
                <p className="text-[16px] font-bold">{t("harvest.emptyTitle")}</p>
                <p className="max-w-[420px] text-[13px] text-mut">{t("harvest.emptyText")}</p>
                <button type="button" className={primaryBtn} onClick={openCreate}>
                  {t("harvest.register")}
                </button>
              </div>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[960px] text-start text-[13px]">
                  <thead className="text-[11px] uppercase tracking-wide text-mut">
                    <tr className="border-b border-line">
                      <th className="py-2 text-start font-semibold">{t("harvest.colDate")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colBlock")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colVariety")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colPass")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colQuantity")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colUnit")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colKg")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colKgHa")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colBasis")}</th>
                      <th className="py-2 text-start font-semibold">
                        <span className="sr-only">{t("harvest.rowMenu")}</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((entry) => (
                      <tr key={entry.id} className="border-b border-line last:border-b-0">
                        <td className="py-3">
                          <span className="inline-flex items-center gap-2">
                            {formatMediumDate(entry.date, lang)}
                            {entry.preharvest_warning !== null ? (
                              <span
                                className="inline-flex size-5 items-center justify-center rounded-full bg-[#FEF3C7] text-[12px] text-amb"
                                title={t("harvest.preharvestTitle")}
                              >
                                !
                              </span>
                            ) : null}
                          </span>
                        </td>
                        <td className="py-3 font-semibold">
                          {blockById.get(entry.block_id)?.name ?? missing}
                        </td>
                        <td className="py-3">{varietyFor(entry.block_id)}</td>
                        <td className="py-3" dir="ltr">
                          {entry.pass_no}
                        </td>
                        <td className="py-3" dir="ltr">
                          {quantityText(entry.quantity, entry.unit, lang)}
                        </td>
                        <td className="py-3">{unitLabel(entry.unit, t)}</td>
                        <td className="py-3" dir="ltr">
                          {massText(entry.kg, lang)}
                        </td>
                        <td className="py-3" dir="ltr">
                          {densityText(entry.kg_ha, lang)}
                        </td>
                        <td className="py-3">
                          {basisLabel(entry, t, valveName(entry.block_id, entry.valve_id))}
                        </td>
                        <td className="py-3 text-end">
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              className="inline-flex size-8 items-center justify-center rounded-full text-[16px] text-mut"
                              aria-label={t("harvest.rowMenu")}
                            >
                              ⋯
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => openEdit(entry)}>
                                {t("harvest.edit")}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => {
                                  setDeleteError(null)
                                  setPendingDelete(entry)
                                }}
                              >
                                {t("harvest.delete")}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {blockSummaries.length > 0 ? (
            <section className={cardClass}>
              <h2 className="text-[16px] font-bold">{t("harvest.byBlock")}</h2>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[480px] text-start text-[13px]">
                  <thead className="text-[11px] uppercase tracking-wide text-mut">
                    <tr className="border-b border-line">
                      <th className="py-2 text-start font-semibold">{t("harvest.colBlock")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colKg")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colKgHa")}</th>
                      <th className="py-2 text-start font-semibold">{t("harvest.colPasses")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {blockSummaries.map((row) => (
                      <tr key={row.block_id} className="border-b border-line last:border-b-0">
                        <td className="py-3 font-semibold">{row.name}</td>
                        <td className="py-3" dir="ltr">
                          {massText(row.kg_total, lang)}
                        </td>
                        <td className="py-3" dir="ltr">
                          {row.kg_ha === null ? missing : densityText(row.kg_ha, lang)}
                        </td>
                        <td className="py-3" dir="ltr">
                          {row.passes}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </>
      )}

      <RegisterHarvestDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        farmId={farmId}
        blocks={completeBlocks}
        timeZone={zone}
        entry={editing}
        entryBlock={editing === null ? null : (detailById.get(editing.block_id) ?? null)}
      />

      {pendingDelete !== null ? (
        <ConfirmDialog
          title={t("harvest.deleteTitle")}
          text={t("harvest.deleteText")}
          error={deleteError === null ? null : t(deleteError)}
          cancelLabel={t("harvest.cancel")}
          confirmLabel={t("harvest.deleteConfirm")}
          pending={deleting}
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => void confirmDelete()}
        />
      ) : null}
    </div>
  )
}

function asPositive(value: string): boolean {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0
}
