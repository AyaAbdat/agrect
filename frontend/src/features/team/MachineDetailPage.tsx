import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "../../app/auth"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { activeLang } from "../blocks/types"
import type { FarmClock } from "../soilwater/types"
import { asNumber, farmToday, formatMediumDate, isDecimal, wireDecimal } from "../weather/format"
import {
  FieldError,
  FieldLabel,
  LoadError,
  PageSkeleton,
  SourceTag,
  cardClass,
  fieldClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { teamErrorKey, teamErrorState } from "./errors"
import { MachineDrawer } from "./MachineDrawer"
import { MaintenanceDrawer } from "./MaintenanceDrawer"
import type { MachineDetail, MaintenanceItem } from "./types"

function seasonYears(): number[] {
  const current = new Date().getFullYear()
  return [current, current - 1, current - 2, current - 3]
}

function intervalText(
  item: MaintenanceItem,
  lang: string,
  t: (key: string, opts?: Record<string, string>) => string,
): string {
  const parts: string[] = []
  if (item.interval_h !== null) {
    parts.push(
      t("team.machines.hoursValue", {
        hours: formatNumber(asNumber(item.interval_h), 0, lang),
      }),
    )
  }
  if (item.interval_days !== null) {
    parts.push(
      t("team.machines.daysValue", {
        days: formatNumber(item.interval_days, 0, lang),
      }),
    )
  }
  if (parts.length === 0) return t("common.missing")
  return t("team.machines.maintenance.every", { interval: parts.join(" / ") })
}

function lastDoneText(
  item: MaintenanceItem,
  lang: string,
  t: (key: string, opts?: Record<string, string>) => string,
): string {
  const parts: string[] = []
  if (item.last_done_date !== null) {
    parts.push(formatMediumDate(item.last_done_date, lang))
  }
  if (item.last_done_h !== null) {
    parts.push(
      t("team.machines.hoursValue", {
        hours: formatNumber(asNumber(item.last_done_h), 1, lang),
      }),
    )
  }
  return parts.length > 0 ? parts.join(" · ") : t("common.missing")
}

function nextDueText(
  item: MaintenanceItem,
  lang: string,
  t: (key: string, opts?: Record<string, string>) => string,
): string | null {
  const parts: string[] = []
  if (item.due.next_due_date !== null) {
    parts.push(formatMediumDate(item.due.next_due_date, lang))
  }
  if (item.due.next_due_h !== null) {
    parts.push(
      t("team.machines.hoursValue", {
        hours: formatNumber(asNumber(item.due.next_due_h), 1, lang),
      }),
    )
  }
  return parts.length > 0 ? parts.join(" · ") : null
}

function MaintenanceStatusBadge({ item }: { item: MaintenanceItem }) {
  const { t } = useTranslation()
  if (item.due.overdue) {
    return (
      <span className="inline-flex rounded-full bg-[#FEE2E2] px-2 py-0.5 text-[11px] font-semibold text-red">
        {t("team.machines.maintenance.statusOverdue")}
      </span>
    )
  }
  if (item.due.due_by_hours || item.due.due_by_date) {
    return (
      <span className="inline-flex rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[11px] font-semibold text-amb">
        {t("team.machines.maintenance.statusDue")}
      </span>
    )
  }
  if (
    item.last_done_date === null &&
    item.last_done_h === null &&
    item.due.next_due_date === null &&
    item.due.next_due_h === null
  ) {
    return (
      <span className="inline-flex rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[11px] font-semibold text-mut">
        {t("team.machines.maintenance.statusNeverDone")}
      </span>
    )
  }
  return (
    <span className="inline-flex rounded-full bg-mint px-2 py-0.5 text-[11px] font-semibold text-pri">
      {t("team.machines.maintenance.statusOk")}
    </span>
  )
}

export function MachineDetailPage() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { machineId } = useParams()
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId
  const [season, setSeason] = useState<number>(new Date().getFullYear())
  const [editMachineOpen, setEditMachineOpen] = useState(false)
  const [maintDrawerOpen, setMaintDrawerOpen] = useState(false)
  const [editingMaint, setEditingMaint] = useState<MaintenanceItem | null>(null)
  const [doneTarget, setDoneTarget] = useState<MaintenanceItem | null>(null)
  const [doneDate, setDoneDate] = useState("")
  const [doneHours, setDoneHours] = useState("")
  const [doneErrors, setDoneErrors] = useState<Record<string, string>>({})
  const [doneFormError, setDoneFormError] = useState<string | null>(null)
  const [markingDone, setMarkingDone] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<MaintenanceItem | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  const detailQuery = useQuery({
    queryKey: ["machine", machineId, season],
    queryFn: () => apiGet<MachineDetail>(`/v1/machines/${machineId}?season=${season}`),
    enabled: machineId !== undefined,
  })

  if (machineId === undefined || farmId === null) return null
  if (detailQuery.isLoading) return <PageSkeleton />
  if (detailQuery.isError || detailQuery.data === undefined) {
    return <LoadError onRetry={() => void detailQuery.refetch()} />
  }

  const machine = detailQuery.data
  const uses = machine.uses_this_season
  const todayIso =
    farmQuery.data !== undefined
      ? farmToday(farmQuery.data.timezone)
      : new Date().toISOString().slice(0, 10)

  function refreshAll() {
    void queryClient.invalidateQueries({ queryKey: ["machine", machineId] })
    void queryClient.invalidateQueries({ queryKey: ["machines", farmId] })
    void queryClient.invalidateQueries({ queryKey: ["maintenance-due", farmId] })
  }

  function openMarkDone(item: MaintenanceItem) {
    setDoneTarget(item)
    setDoneDate(todayIso)
    setDoneHours("")
    setDoneErrors({})
    setDoneFormError(null)
  }

  async function submitMarkDone(event: FormEvent) {
    event.preventDefault()
    if (doneTarget === null) return
    const next: Record<string, string> = {}
    if (doneDate.trim() === "") next.date = "journal.errors.date"
    const hoursWire = wireDecimal(doneHours)
    if (doneHours.trim() !== "") {
      if (hoursWire === null || !isDecimal(doneHours) || Number(hoursWire) < 0) {
        next.engine_hours = "team.machines.errors.hoursInvalid"
      }
    }
    setDoneErrors(next)
    setDoneFormError(null)
    if (Object.keys(next).length > 0) return

    setMarkingDone(true)
    try {
      await apiSend<MaintenanceItem>(
        "POST",
        `/v1/maintenance/${doneTarget.id}/done`,
        {
          date: doneDate.trim(),
          engine_hours: doneHours.trim() === "" ? null : hoursWire,
        },
        { "If-Match": String(doneTarget.version) },
      )
    } catch (error) {
      setMarkingDone(false)
      const parsed = teamErrorState(error)
      setDoneErrors(parsed.fields)
      setDoneFormError(parsed.form)
      return
    }
    setMarkingDone(false)
    setDoneTarget(null)
    refreshAll()
  }

  async function confirmDeleteMaint() {
    if (deleteTarget === null) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiSend("DELETE", `/v1/maintenance/${deleteTarget.id}`, undefined, {
        "If-Match": String(deleteTarget.version),
      })
    } catch (error) {
      setDeleting(false)
      setDeleteError(error instanceof ApiError ? teamErrorKey(error.code) : "team.errors.save")
      return
    }
    setDeleting(false)
    setDeleteTarget(null)
    refreshAll()
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            to="/team?tab=machines"
            className="text-[12px] font-semibold text-pri hover:underline"
          >
            {t("team.machines.backToMachines")}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2.5">
            <h1 className="text-[24px] font-bold leading-tight">{machine.name}</h1>
            <span className="inline-flex rounded-full border border-line px-2.5 py-0.5 text-[11px] font-semibold text-mut">
              {t(`team.machines.types.${machine.type}`)}
            </span>
            <span
              className={`inline-flex rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                machine.status === "ok" ? "bg-mint text-pri" : "bg-[#FEF3C7] text-amb"
              }`}
            >
              {t(`team.machines.statuses.${machine.status}`)}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-[13px]">
            <span className="font-semibold text-mut">{t("costs.season")}</span>
            <select
              className="h-9 rounded-full border border-line bg-white px-3 text-[13px]"
              dir="ltr"
              value={season}
              onChange={(change) => setSeason(Number(change.target.value))}
            >
              {seasonYears().map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className={outlineBtn}
            onClick={() => setEditMachineOpen(true)}
          >
            {t("journal.edit")}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <section className={cardClass}>
          <div className="flex items-center justify-between gap-2">
            <p className="text-[12px] font-semibold text-mut">
              {t("team.machines.currentEngineHours")}
            </p>
            {machine.current_engine_hours !== null ? <SourceTag kind="calculated" /> : null}
          </div>
          <p className="mt-2 text-[22px] font-bold" dir="ltr">
            {machine.current_engine_hours !== null
              ? t("team.machines.hoursValue", {
                  hours: formatNumber(asNumber(machine.current_engine_hours), 1, lang),
                })
              : t("common.missing")}
          </p>
          {machine.engine_hours_reading !== null ? (
            <p className="mt-1 text-[12px] text-mut">
              {t("team.machines.lastReadingLine", {
                hours: formatNumber(asNumber(machine.engine_hours_reading), 1, lang),
                date:
                  machine.reading_date !== null
                    ? formatMediumDate(machine.reading_date, lang)
                    : t("common.missing"),
              })}
            </p>
          ) : null}
        </section>

        <section className={cardClass}>
          <div className="flex items-center justify-between gap-2">
            <p className="text-[12px] font-semibold text-mut">
              {t("team.machines.usesThisSeason", { season: String(uses.season) })}
            </p>
            <SourceTag kind="calculated" />
          </div>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <p className="text-[11px] text-mut">{t("team.machines.hours")}</p>
              <p className="text-[16px] font-bold" dir="ltr">
                {t("team.machines.hoursValue", {
                  hours: formatNumber(asNumber(uses.hours), 1, lang),
                })}
              </p>
            </div>
            <div>
              <p className="text-[11px] text-mut">{t("team.machines.fuel")}</p>
              <p className="text-[16px] font-bold" dir="ltr">
                {t("team.machines.litersValue", {
                  liters: formatNumber(asNumber(uses.fuel_l), 1, lang),
                })}
              </p>
            </div>
            <div>
              <p className="text-[11px] text-mut">{t("team.machines.area")}</p>
              <p className="text-[16px] font-bold" dir="ltr">
                {t("team.machines.areaValue", {
                  area: formatNumber(asNumber(uses.area_ha), 2, lang),
                })}
              </p>
            </div>
            <div>
              <p className="text-[11px] text-mut">{t("team.machines.avgWorkRate")}</p>
              <p className="text-[16px] font-bold" dir="ltr">
                {uses.avg_work_rate_ha_h !== null
                  ? t("team.machines.workRateValue", {
                      rate: formatNumber(asNumber(uses.avg_work_rate_ha_h), 2, lang),
                    })
                  : t("common.missing")}
              </p>
            </div>
          </div>
        </section>
      </div>

      <section className={cardClass}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-[15px] font-bold">{t("team.machines.maintenance.title")}</h2>
          <button
            type="button"
            className={primaryBtn}
            onClick={() => {
              setEditingMaint(null)
              setMaintDrawerOpen(true)
            }}
          >
            {t("team.machines.maintenance.add")}
          </button>
        </div>

        {machine.maintenance.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
            <p className="text-[14px] font-bold">{t("team.machines.maintenance.emptyTitle")}</p>
            <p className="max-w-[420px] text-[13px] text-mut">
              {t("team.machines.maintenance.emptyText")}
            </p>
            <button
              type="button"
              className={outlineBtn}
              onClick={() => {
                setEditingMaint(null)
                setMaintDrawerOpen(true)
              }}
            >
              {t("team.machines.maintenance.add")}
            </button>
          </div>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[760px] text-start text-[13px]">
              <thead className="text-[11px] uppercase tracking-wide text-mut">
                <tr className="border-b border-line">
                  <th className="py-2 text-start font-semibold">
                    {t("team.machines.maintenance.task")}
                  </th>
                  <th className="py-2 text-start font-semibold">
                    {t("team.machines.maintenance.interval")}
                  </th>
                  <th className="py-2 text-start font-semibold">
                    {t("team.machines.maintenance.lastDone")}
                  </th>
                  <th className="py-2 text-start font-semibold">
                    {t("team.machines.maintenance.nextDue")}
                  </th>
                  <th className="py-2 text-start font-semibold">{t("team.machines.status")}</th>
                  <th className="py-2 text-end font-semibold">
                    <span className="sr-only">{t("journal.rowMenu")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {machine.maintenance.map((item) => {
                  const nextText = nextDueText(item, lang, t)
                  return (
                    <tr key={item.id} className="border-b border-line last:border-b-0">
                      <td className="py-3 font-semibold">{item.task}</td>
                      <td className="py-3">{intervalText(item, lang, t)}</td>
                      <td className="py-3" dir="ltr">
                        {lastDoneText(item, lang, t)}
                      </td>
                      <td className="py-3">
                        {nextText !== null ? (
                          <span className="inline-flex items-center gap-1.5">
                            <span dir="ltr">{nextText}</span>
                            <SourceTag kind="calculated" />
                          </span>
                        ) : (
                          <span className="text-mut">{t("common.missing")}</span>
                        )}
                      </td>
                      <td className="py-3">
                        <MaintenanceStatusBadge item={item} />
                      </td>
                      <td className="py-3 text-end">
                        <div className="inline-flex items-center gap-2">
                          <button
                            type="button"
                            className={`${outlineBtn} h-8 px-3 text-[12px]`}
                            onClick={() => openMarkDone(item)}
                          >
                            {t("team.machines.maintenance.markDone")}
                          </button>
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              className="inline-flex size-8 items-center justify-center rounded-full text-[16px] text-mut"
                              aria-label={t("journal.rowMenu")}
                            >
                              ⋯
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() => {
                                  setEditingMaint(item)
                                  setMaintDrawerOpen(true)
                                }}
                              >
                                {t("journal.edit")}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => {
                                  setDeleteTarget(item)
                                  setDeleteError(null)
                                }}
                              >
                                {t("journal.delete")}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <MachineDrawer
        open={editMachineOpen}
        onOpenChange={setEditMachineOpen}
        farmId={farmId}
        machine={machine}
        onSaved={refreshAll}
      />

      <MaintenanceDrawer
        open={maintDrawerOpen}
        onOpenChange={setMaintDrawerOpen}
        machineId={machine.id}
        machineName={machine.name}
        item={editingMaint}
        onSaved={refreshAll}
      />

      {doneTarget !== null ? (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="maint-done-title"
            className="w-full max-w-sm rounded-2xl bg-white p-5"
          >
            <h2 id="maint-done-title" className="text-[16px] font-bold">
              {t("team.machines.maintenance.markDoneTitle")}
            </h2>
            <p className="mt-1 text-[13px] text-mut">{doneTarget.task}</p>
            <form
              className="mt-4 flex flex-col gap-3"
              onSubmit={(event) => void submitMarkDone(event)}
            >
              <label className="block">
                <FieldLabel label={t("inventories.date")} tag="required" />
                <input
                  type="date"
                  dir="ltr"
                  lang="en"
                  className={fieldClass}
                  value={doneDate}
                  aria-invalid={doneErrors.date !== undefined}
                  onChange={(change) => setDoneDate(change.target.value)}
                />
                <FieldError message={doneErrors.date} />
              </label>
              <label className="block">
                <FieldLabel label={t("team.machines.engineHours")} tag="optional" />
                <input
                  className={fieldClass}
                  inputMode="decimal"
                  dir="ltr"
                  lang="en"
                  placeholder={
                    machine.current_engine_hours !== null
                      ? formatNumber(asNumber(machine.current_engine_hours), 1, lang)
                      : ""
                  }
                  value={doneHours}
                  aria-invalid={doneErrors.engine_hours !== undefined}
                  onChange={(change) => setDoneHours(change.target.value)}
                />
                <FieldError message={doneErrors.engine_hours} />
              </label>
              {doneFormError !== null ? <FieldError message={doneFormError} /> : null}
              <div className="mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  className={outlineBtn}
                  onClick={() => setDoneTarget(null)}
                  disabled={markingDone}
                >
                  {t("journal.cancel")}
                </button>
                <button type="submit" className={primaryBtn} disabled={markingDone}>
                  {t("journal.save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {deleteTarget !== null ? (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="maint-delete-title"
            className="w-full max-w-sm rounded-2xl bg-white p-5"
          >
            <h2 id="maint-delete-title" className="text-[16px] font-bold">
              {t("team.machines.maintenance.deleteTitle")}
            </h2>
            <p className="mt-2 text-[13px] text-mut">
              {t("team.machines.maintenance.deleteText", { task: deleteTarget.task })}
            </p>
            {deleteError !== null ? (
              <p className="mt-2 text-[12px] text-red">{t(deleteError)}</p>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className={outlineBtn}
                onClick={() => {
                  setDeleteTarget(null)
                  setDeleteError(null)
                }}
                disabled={deleting}
              >
                {t("journal.cancel")}
              </button>
              <button
                type="button"
                className={`${primaryBtn} disabled:opacity-60`}
                onClick={() => void confirmDeleteMaint()}
                disabled={deleting}
              >
                {t("journal.delete")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
