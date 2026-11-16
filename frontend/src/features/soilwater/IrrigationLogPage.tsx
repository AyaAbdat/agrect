import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import { useAuth } from "../../app/auth"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import { UNIT_MM } from "../../lib/units"
import { activeLang, type BlockDetail, type BlockValve } from "../blocks/types"
import { farmToday, formatHour, formatMediumDate } from "../weather/format"
import {
  ChoiceChip,
  LoadError,
  PageHeader,
  PageSkeleton,
  SourceTag,
  cardClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { farmDateAndTime, mm2, runClock } from "./display"
import { LogIrrigationDrawer } from "./LogIrrigationDrawer"
import { monthRange, weekRange, type WaterPeriod } from "./period"
import { refreshWater } from "./refresh"
import type { FarmClock, IrrigationEvent, IrrigationEvents, SoilProfile, WaterBalance } from "./types"

function valveNames(ids: string[], valves: BlockValve[], missing: string): string {
  const byId = new Map(valves.map((valve) => [valve.id, valve]))
  const names = [...ids]
    .sort((left, right) => (byId.get(left)?.sort ?? 0) - (byId.get(right)?.sort ?? 0))
    .flatMap((id) => {
      const name = byId.get(id)?.name
      return name === undefined ? [] : [name]
    })
  return names.length === 0 ? missing : names.join(", ")
}

function eventsPath(
  blockId: string,
  period: WaterPeriod,
  today: string,
  seasonFrom: string | null,
): string {
  const base = `/v1/blocks/${blockId}/irrigation-events`
  if (period === "season") {
    return seasonFrom === null ? base : `${base}?from=${seasonFrom}`
  }
  const range = period === "week" ? weekRange(today) : monthRange(today)
  return `${base}?from=${range.from}&to=${range.to}`
}

export function IrrigationLogPage() {
  const { t, i18n } = useTranslation()
  const { blockId } = useParams()
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [period, setPeriod] = useState<WaterPeriod>("week")
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editing, setEditing] = useState<IrrigationEvent | null>(null)
  const [pendingDelete, setPendingDelete] = useState<IrrigationEvent | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const farmId = currentFarmId
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const soilQuery = useQuery({
    queryKey: ["soil", blockId],
    queryFn: () => apiGet<SoilProfile>(`/v1/blocks/${blockId}/soil`),
    enabled: blockId !== undefined,
  })
  const today = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)
  const needsSeasonStart = soilQuery.isSuccess && soilQuery.data.full_on === null && period === "season"
  const seasonQuery = useQuery({
    queryKey: ["water-balance", blockId, "season"],
    queryFn: () => apiGet<WaterBalance>(`/v1/blocks/${blockId}/water-balance?period=season`),
    enabled: blockId !== undefined && needsSeasonStart,
  })
  const seasonFrom = soilQuery.data?.full_on ?? seasonQuery.data?.rows[0]?.date ?? null
  const seasonReady = period !== "season" || soilQuery.data?.full_on != null || seasonQuery.isSuccess
  const eventsQuery = useQuery({
    queryKey: ["irrigation-events", blockId, period, today, seasonFrom],
    queryFn: () =>
      apiGet<IrrigationEvents>(eventsPath(blockId ?? "", period, today ?? "", seasonFrom)),
    enabled: blockId !== undefined && today !== null && soilQuery.isSuccess && seasonReady,
  })

  if (blockId === undefined || farmId === null) return null
  const loading =
    farmQuery.isPending ||
    blockQuery.isPending ||
    soilQuery.isPending ||
    (needsSeasonStart && seasonQuery.isLoading) ||
    eventsQuery.isLoading
  if (loading) return <PageSkeleton />
  const failed =
    farmQuery.isError ||
    blockQuery.isError ||
    soilQuery.isError ||
    seasonQuery.isError ||
    eventsQuery.isError ||
    farmQuery.data === undefined ||
    blockQuery.data === undefined ||
    eventsQuery.data === undefined
  if (failed) {
    return (
      <LoadError
        onRetry={() => {
          void queryClient.invalidateQueries({ queryKey: ["farm", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["block", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["soil", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["water-balance", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["irrigation-events", blockId] })
        }}
      />
    )
  }

  const zone = farmQuery.data.timezone
  const events = eventsQuery.data.events
  const totals = eventsQuery.data.totals
  const empty = totals.count === 0
  const missing = t("common.missing")
  const periods: { id: WaterPeriod; label: string }[] = [
    { id: "week", label: t("soil.periodWeek") },
    { id: "month", label: t("soil.periodMonth") },
    { id: "season", label: t("soil.periodSeason") },
  ]

  function openCreate() {
    setEditing(null)
    setDrawerOpen(true)
  }

  async function confirmDelete() {
    if (pendingDelete === null) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiSend(
        "DELETE",
        `/v1/blocks/${blockId}/irrigation-events/${pendingDelete.id}`,
        undefined,
        { "If-Match": String(pendingDelete.version) },
      )
    } catch (error) {
      setDeleting(false)
      setDeleteError(
        error instanceof ApiError && (error.status === 409 || error.status === 428)
          ? "soil.errors.conflict"
          : "soil.errors.save",
      )
      return
    }
    await refreshWater(queryClient, blockId, farmId)
    setDeleting(false)
    setPendingDelete(null)
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("soil.setupCrumb")}
        title={t("soil.logTitle")}
        sub={blockQuery.data.name}
        actions={
          <>
            <Link
              to={`/blocks/${blockId}/soil-water`}
              className={`inline-flex items-center ${outlineBtn}`}
            >
              {t("soil.back")}
            </Link>
            <button type="button" className={primaryBtn} onClick={openCreate}>
              {t("soil.logButton")}
            </button>
          </>
        }
      />
      <div className="flex flex-wrap gap-2">
        {periods.map((item) => (
          <ChoiceChip
            key={item.id}
            selected={period === item.id}
            onClick={() => setPeriod(item.id)}
          >
            {item.label}
          </ChoiceChip>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <section className={cardClass}>
          <div className="flex items-center justify-between gap-2">
            <p className="text-[12px] text-mut">{t("soil.applied")}</p>
            <SourceTag kind="calculated" />
          </div>
          <p className="mt-2 text-[22px] font-bold">
            {empty ? missing : mm2(totals.depth_mm, lang)}{" "}
            <span className="text-[12px] font-medium text-mut">{UNIT_MM}</span>
          </p>
        </section>
        <section className={cardClass}>
          <div className="flex items-center justify-between gap-2">
            <p className="text-[12px] text-mut">{t("soil.volume")}</p>
            <SourceTag kind="calculated" />
          </div>
          <p className="mt-2 text-[22px] font-bold">
            {empty ? missing : mm2(totals.volume_m3, lang)}{" "}
            <span className="text-[12px] font-medium text-mut">{t("soil.unitM3")}</span>
          </p>
        </section>
      </div>
      <section className={cardClass}>
        <h2 className="text-[15px] font-bold">{t("soil.irrigations")}</h2>
        {empty ? (
          <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
            <p className="text-[16px] font-bold">{t("soil.logEmptyTitle")}</p>
            <p className="max-w-[420px] text-[13px] text-mut">{t("soil.logEmptyText")}</p>
            <button type="button" className={primaryBtn} onClick={openCreate}>
              {t("soil.logButton")}
            </button>
          </div>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[720px] text-start text-[13px]">
              <thead className="text-[11px] uppercase tracking-wide text-mut">
                <tr className="border-b border-line">
                  <th className="py-2 text-start font-semibold">{t("soil.colDate")}</th>
                  <th className="py-2 text-start font-semibold">{t("soil.colValves")}</th>
                  <th className="py-2 text-start font-semibold">{t("soil.colStart")}</th>
                  <th className="py-2 text-start font-semibold">{t("soil.colRun")}</th>
                  <th className="py-2 text-start font-semibold">{t("soil.colDepth")}</th>
                  <th className="py-2 text-start font-semibold">{t("soil.colVolume")}</th>
                  <th className="py-2 text-start font-semibold">
                    <span className="sr-only">{t("soil.rowMenu")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {events.map((row) => {
                  const local = farmDateAndTime(row.start_at, zone)
                  return (
                    <tr key={row.id} className="border-b border-line last:border-b-0">
                      <td className="py-3">{formatMediumDate(local.date, lang)}</td>
                      <td className="py-3">{valveNames(row.valve_ids, blockQuery.data.valves, missing)}</td>
                      <td className="py-3" dir="ltr">
                        {formatHour(row.start_at, zone)}
                      </td>
                      <td className="py-3" dir="ltr">
                        {runClock(row.duration_min, lang)}
                      </td>
                      <td className="py-3">
                        {mm2(row.depth_mm, lang)} {UNIT_MM}
                      </td>
                      <td className="py-3">
                        {mm2(row.volume_m3, lang)} {t("soil.unitM3")}
                      </td>
                      <td className="py-3 text-end">
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            className="inline-flex size-8 items-center justify-center rounded-full text-[16px] text-mut"
                            aria-label={t("soil.rowMenu")}
                          >
                            ⋯
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => {
                                setEditing(row)
                                setDrawerOpen(true)
                              }}
                            >
                              {t("soil.edit")}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => {
                                setDeleteError(null)
                                setPendingDelete(row)
                              }}
                            >
                              {t("soil.delete")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <LogIrrigationDrawer
        open={drawerOpen}
        onOpenChange={(next) => {
          setDrawerOpen(next)
          if (!next) setEditing(null)
        }}
        blockId={blockId}
        blockName={blockQuery.data.name}
        valves={blockQuery.data.valves}
        timeZone={zone}
        today={today ?? ""}
        event={editing}
      />
      {pendingDelete !== null ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-irrigation-title"
            className="w-full max-w-sm rounded-2xl bg-white p-5"
          >
            <h2 id="delete-irrigation-title" className="text-[16px] font-bold">
              {t("soil.deleteTitle")}
            </h2>
            <p className="mt-2 text-[13px] text-mut">{t("soil.deleteText")}</p>
            {deleteError !== null ? <p className="mt-2 text-[12px] text-red">{t(deleteError)}</p> : null}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className={outlineBtn}
                onClick={() => setPendingDelete(null)}
                disabled={deleting}
              >
                {t("soil.cancel")}
              </button>
              <button type="button" className={primaryBtn} onClick={() => void confirmDelete()} disabled={deleting}>
                {t("soil.deleteConfirm")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
