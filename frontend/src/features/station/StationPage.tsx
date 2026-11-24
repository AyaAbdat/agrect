import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "../../app/auth"
import { apiGet, apiSend } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { activeLang, type BlockListItem } from "../blocks/types"
import { LoadError, PageHeader, PageSkeleton, cardClass, primaryBtn } from "../weather/ui"
import { flowText, windowsLabel } from "./display"
import { ConfirmDialog } from "./dialog"
import { stationErrorState } from "./errors"
import { PumpDrawer } from "./PumpDrawer"
import type { FarmStation, Pump } from "./types"
import { WaterSourceDrawer } from "./WaterSourceDrawer"

function OptionalTag() {
  const { t } = useTranslation()
  return (
    <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
      {t("weather.optional")}
    </span>
  )
}

export function StationPage() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId
  const [pumpOpen, setPumpOpen] = useState(false)
  const [editing, setEditing] = useState<Pump | null>(null)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [sourceIntent, setSourceIntent] = useState<"list" | "add">("list")
  const [returnToPump, setReturnToPump] = useState(false)
  const [selectSourceId, setSelectSourceId] = useState<string | null>(null)
  const holdPump = useRef(false)
  const [pendingDelete, setPendingDelete] = useState<Pump | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const stationQuery = useQuery({
    queryKey: ["station", farmId],
    queryFn: () => apiGet<FarmStation>(`/v1/farms/${farmId}/station`),
    enabled: farmId !== null,
  })
  const blocksQuery = useQuery({
    queryKey: ["blocks", farmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${farmId}/blocks`),
    enabled: farmId !== null,
  })
  const clearSourceSelection = useCallback(() => setSelectSourceId(null), [])
  useEffect(() => {
    if (pumpOpen) holdPump.current = false
  }, [pumpOpen])

  if (farmId === null) return null
  if (stationQuery.isPending || blocksQuery.isPending) return <PageSkeleton />
  if (stationQuery.isError || blocksQuery.isError || stationQuery.data === undefined || blocksQuery.data === undefined) {
    return (
      <LoadError
        onRetry={() => {
          void queryClient.invalidateQueries({ queryKey: ["station", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["blocks", farmId] })
        }}
      />
    )
  }

  const station = stationQuery.data
  const pumps = station.pumps
  const blocks = blocksQuery.data.map((block) => ({ id: block.id, name: block.name }))
  const missing = t("common.missing")

  function openCreate() {
    setEditing(null)
    setPumpOpen(true)
  }

  async function confirmDelete() {
    if (pendingDelete === null) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiSend("DELETE", `/v1/pumps/${pendingDelete.id}`, undefined, {
        "If-Match": String(pendingDelete.version),
      })
    } catch (error) {
      const parsed = stationErrorState(error)
      setDeleting(false)
      setDeleteError(parsed.form ?? "station.errors.delete")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["station", farmId] })
    await queryClient.invalidateQueries({ queryKey: ["capacity-check", farmId] })
    setDeleting(false)
    setPendingDelete(null)
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("nav.farm")}
        title={t("nav.station")}
        sub={t("station.sub")}
        actions={
          <button type="button" className={primaryBtn} onClick={openCreate}>
            {t("station.addPump")}
          </button>
        }
      />
      <div className="rounded-xl bg-mint px-4 py-3 text-[13px] text-pri">{t("station.info")}</div>
      <section className={cardClass}>
        <h2 className="text-[16px] font-bold">{t("station.pumps")}</h2>
        {pumps.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
            <p className="text-[16px] font-bold">{t("station.emptyTitle")}</p>
            <p className="max-w-[420px] text-[13px] text-mut">{t("station.emptyText")}</p>
            <button type="button" className={primaryBtn} onClick={openCreate}>
              {t("station.addPump")}
            </button>
          </div>
        ) : (
          <>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[720px] text-start text-[13px]">
                <thead className="text-[11px] uppercase tracking-wide text-mut">
                  <tr className="border-b border-line">
                    <th className="py-2 text-start font-semibold">{t("station.colName")}</th>
                    <th className="py-2 text-start font-semibold">{t("station.colFlow")}</th>
                    <th className="py-2 text-start font-semibold">{t("station.colBlocks")}</th>
                    <th className="py-2 text-start font-semibold">{t("station.colPressure")}</th>
                    <th className="py-2 text-start font-semibold">{t("station.colHours")}</th>
                    <th className="py-2 text-start font-semibold">
                      <span className="sr-only">{t("station.rowMenu")}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {pumps.map((pump) => {
                    const blockLabel = pump.serves_all_blocks
                      ? t("station.allBlocks")
                      : pump.blocks.length === 0
                        ? missing
                        : pump.blocks.map((block) => block.name).join(", ")
                    const pressure =
                      pump.pressure_bar === null
                        ? missing
                        : `${flowText(pump.pressure_bar, lang)} ${t("station.unitBar")}`
                    return (
                      <tr key={pump.id} className="border-b border-line last:border-b-0">
                        <td className="py-3 font-semibold">{pump.name}</td>
                        <td className="py-3" dir="ltr">
                          {flowText(pump.flow_m3h, lang)}
                        </td>
                        <td className="py-3">{blockLabel}</td>
                        <td className="py-3" dir="ltr">
                          {pressure}
                        </td>
                        <td className="py-3" dir="ltr">
                          {windowsLabel(pump.windows, t("station.allDay"))}
                        </td>
                        <td className="py-3 text-end">
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              className="inline-flex size-8 items-center justify-center rounded-full text-[16px] text-mut"
                              aria-label={t("station.rowMenu")}
                            >
                              ⋯
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() => {
                                  setEditing(pump)
                                  setPumpOpen(true)
                                }}
                              >
                                {t("station.edit")}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => {
                                  setDeleteError(null)
                                  setPendingDelete(pump)
                                }}
                              >
                                {t("station.delete")}
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
            <p className="mt-3 text-[13px] text-mut">
              {t("station.total", {
                count: formatNumber(pumps.length, 0, lang),
                flow: flowText(station.totals.pumps_flow_m3h, lang),
              })}
            </p>
          </>
        )}
      </section>
      <div className="grid grid-cols-2 gap-4">
        <section className={cardClass}>
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-[16px] font-bold">{t("station.moreTitle")}</h2>
            <OptionalTag />
          </div>
          <button
            type="button"
            className="mt-2 flex w-full items-center justify-between gap-3 border-b border-line py-3 text-start"
            onClick={() => {
              setReturnToPump(false)
              setSourceIntent("list")
              setSourceOpen(true)
            }}
          >
            <span className="font-semibold">{t("station.waterSources")}</span>
            <span className="text-mut" dir="ltr">
              {formatNumber(station.water_sources.length, 0, lang)}
            </span>
          </button>
          <div className="flex items-start justify-between gap-3 border-b border-line py-3">
            <span className="font-semibold">{t("station.hoursRow")}</span>
            <span className="text-end text-[13px] text-mut">{t("station.hoursRowText")}</span>
          </div>
          <div className="flex items-center justify-between gap-3 py-3 text-mut" aria-disabled="true">
            <span className="font-semibold">{t("station.injectors")}</span>
            <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold">
              {t("settings.phase2")}
            </span>
          </div>
        </section>
        <section className={cardClass}>
          <h2 className="text-[16px] font-bold">{t("station.capacityTitle")}</h2>
          <p className="mt-1 text-mut">{t("station.capacitySub")}</p>
          <Link to="/station/capacity" className={`mt-4 inline-flex items-center ${primaryBtn}`}>
            {t("station.openCapacity")}
          </Link>
        </section>
      </div>
      <PumpDrawer
        open={pumpOpen}
        onOpenChange={(next) => {
          setPumpOpen(next)
          if (!next && !holdPump.current) setEditing(null)
        }}
        farmId={farmId}
        pump={editing}
        blocks={blocks}
        sources={station.water_sources}
        selectSourceId={selectSourceId}
        onSourceSelected={clearSourceSelection}
        onAddSource={() => {
          holdPump.current = true
          setReturnToPump(true)
          setSourceIntent("add")
          setPumpOpen(false)
          setSourceOpen(true)
        }}
      />
      <WaterSourceDrawer
        open={sourceOpen}
        onOpenChange={(next) => {
          setSourceOpen(next)
          if (!next && returnToPump) {
            setReturnToPump(false)
            setPumpOpen(true)
          }
        }}
        farmId={farmId}
        sources={station.water_sources}
        intent={sourceIntent}
        onCreated={(id) => setSelectSourceId(id)}
      />
      {pendingDelete !== null ? (
        <ConfirmDialog
          title={t("station.deleteTitle")}
          text={t("station.deleteText")}
          error={deleteError === null ? null : t(deleteError)}
          cancelLabel={t("station.cancel")}
          confirmLabel={t("station.deleteConfirm")}
          pending={deleting}
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => void confirmDelete()}
        />
      ) : null}
    </div>
  )
}
