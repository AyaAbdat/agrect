import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import { useAuth } from "../../app/auth"
import { apiGet, apiSend } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { activeLang } from "../blocks/types"
import type { FarmClock } from "../soilwater/types"
import { asNumber, farmToday, isDecimal, wireDecimal } from "../weather/format"
import {
  FieldError,
  LoadError,
  PageSkeleton,
  SourceTag,
  cardClass,
  fieldClass,
  primaryBtn,
} from "../weather/ui"
import { teamErrorState } from "./errors"
import type { AttendanceDay, AttendanceSummary, WorkerList } from "./types"

type DraftRow = {
  worker_id: string
  worker_name: string
  present: boolean
  hours: string
  note: string
}

export function AttendanceTab() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId

  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  const today = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)

  const [date, setDate] = useState<string>("")
  const [summaryFrom, setSummaryFrom] = useState<string>("")
  const [summaryTo, setSummaryTo] = useState<string>("")
  const [rows, setRows] = useState<DraftRow[]>([])
  const [saving, setSaving] = useState(false)
  const [savedBanner, setSavedBanner] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    if (today === null) return
    if (date === "") setDate(today)
    if (summaryFrom === "") setSummaryFrom(`${today.slice(0, 8)}01`)
    if (summaryTo === "") setSummaryTo(today)
  }, [today, date, summaryFrom, summaryTo])

  const workersQuery = useQuery({
    queryKey: ["workers", farmId],
    queryFn: () => apiGet<WorkerList>(`/v1/farms/${farmId}/workers`),
    enabled: farmId !== null,
  })
  const attendanceQuery = useQuery({
    queryKey: ["attendance", farmId, date],
    queryFn: () => apiGet<AttendanceDay>(`/v1/farms/${farmId}/attendance?date=${date}`),
    enabled: farmId !== null && date !== "",
  })

  const rangeValid = summaryFrom !== "" && summaryTo !== "" && summaryTo >= summaryFrom
  const summaryQuery = useQuery({
    queryKey: ["attendance-summary", farmId, summaryFrom, summaryTo],
    queryFn: () =>
      apiGet<AttendanceSummary>(
        `/v1/farms/${farmId}/attendance/summary?from=${summaryFrom}&to=${summaryTo}`,
      ),
    enabled: farmId !== null && rangeValid,
  })

  const activeWorkers = useMemo(
    () => (workersQuery.data?.workers ?? []).filter((worker) => worker.active),
    [workersQuery.data],
  )

  useEffect(() => {
    if (workersQuery.data === undefined || attendanceQuery.data === undefined) return
    const existing = new Map(
      attendanceQuery.data.items.map((item) => [item.worker_id, item]),
    )
    setRows(
      activeWorkers.map((worker) => {
        const saved = existing.get(worker.id)
        return {
          worker_id: worker.id,
          worker_name: worker.name,
          present: saved?.present ?? false,
          hours: saved?.hours ?? "",
          note: saved?.note ?? "",
        }
      }),
    )
    setRowErrors({})
    setFormError(null)
    setSavedBanner(false)
  }, [activeWorkers, workersQuery.data, attendanceQuery.data])

  if (farmId === null) return null
  if (farmQuery.isPending || workersQuery.isLoading || date === "") return <PageSkeleton />
  if (farmQuery.isError || workersQuery.isError || workersQuery.data === undefined) {
    return (
      <LoadError
        onRetry={() => {
          void farmQuery.refetch()
          void workersQuery.refetch()
        }}
      />
    )
  }

  function updateRow(workerId: string, patch: Partial<DraftRow>) {
    setSavedBanner(false)
    setRows((current) =>
      current.map((row) => (row.worker_id === workerId ? { ...row, ...patch } : row)),
    )
  }

  async function saveAttendance() {
    const nextErrors: Record<string, string> = {}
    const items = rows.map((row) => {
      const trimmed = row.hours.trim()
      if (trimmed === "") {
        return {
          worker_id: row.worker_id,
          present: row.present,
          hours: null,
          note: row.note.trim() === "" ? null : row.note.trim(),
        }
      }
      const wired = wireDecimal(trimmed)
      if (wired === null || !isDecimal(trimmed) || Number(wired) < 0) {
        nextErrors[row.worker_id] = "team.errors.hoursInvalid"
      }
      return {
        worker_id: row.worker_id,
        present: row.present,
        hours: wired,
        note: row.note.trim() === "" ? null : row.note.trim(),
      }
    })
    setRowErrors(nextErrors)
    setFormError(null)
    if (Object.keys(nextErrors).length > 0) return

    setSaving(true)
    try {
      await apiSend<AttendanceDay>("PUT", `/v1/farms/${farmId}/attendance`, {
        date,
        items,
      })
    } catch (error) {
      setSaving(false)
      const parsed = teamErrorState(error)
      setFormError(parsed.form ?? "team.errors.save")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["attendance", farmId] })
    await queryClient.invalidateQueries({ queryKey: ["attendance-summary", farmId] })
    setSaving(false)
    setSavedBanner(true)
  }

  return (
    <div className="flex flex-col gap-4">
      <section className={cardClass}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-[15px] font-bold">{t("team.attendance.dailyTitle")}</h2>
            <span className="rounded-full bg-mint px-2 py-0.5 text-[10px] font-semibold text-pri">
              {t("journal.source.entered")}
            </span>
          </div>
          <label className="flex items-center gap-2 text-[13px]">
            <span className="font-semibold text-mut">{t("team.attendance.date")}</span>
            <input
              type="date"
              dir="ltr"
              lang="en"
              className="h-9 rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px]"
              value={date}
              onChange={(change) => {
                setDate(change.target.value)
                setSavedBanner(false)
              }}
            />
          </label>
        </div>

        {attendanceQuery.isLoading ? (
          <div className="mt-4 h-32 animate-pulse rounded-xl bg-[#E5E7EB]" />
        ) : attendanceQuery.isError ? (
          <div className="mt-4">
            <LoadError onRetry={() => void attendanceQuery.refetch()} />
          </div>
        ) : activeWorkers.length === 0 ? (
          <p className="px-2 py-10 text-center text-[13px] text-mut">
            {t("team.attendance.noActiveWorkers")}
          </p>
        ) : (
          <>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[640px] text-start text-[13px]">
                <thead className="text-[11px] uppercase tracking-wide text-mut">
                  <tr className="border-b border-line">
                    <th className="py-2 text-start font-semibold">{t("team.workers.name")}</th>
                    <th className="py-2 text-start font-semibold">
                      {t("team.attendance.present")}
                    </th>
                    <th className="py-2 text-start font-semibold">
                      {t("team.attendance.hours")}
                    </th>
                    <th className="py-2 text-start font-semibold">
                      {t("team.attendance.note")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.worker_id} className="border-b border-line last:border-b-0">
                      <td className="py-3 pe-3 font-semibold">{row.worker_name}</td>
                      <td className="py-3 pe-3">
                        <button
                          type="button"
                          role="switch"
                          aria-checked={row.present}
                          onClick={() => updateRow(row.worker_id, { present: !row.present })}
                          className={`inline-flex h-8 items-center rounded-full px-3 text-[12px] font-semibold ${
                            row.present
                              ? "bg-pri text-white"
                              : "border border-[#C7D2C9] bg-white text-mut"
                          }`}
                        >
                          {t(
                            row.present
                              ? "team.attendance.presentYes"
                              : "team.attendance.presentNo",
                          )}
                        </button>
                      </td>
                      <td className="w-36 py-3 pe-3">
                        <input
                          className={fieldClass}
                          inputMode="decimal"
                          dir="ltr"
                          lang="en"
                          placeholder={t("team.attendance.hoursPlaceholder")}
                          value={row.hours}
                          aria-invalid={rowErrors[row.worker_id] !== undefined}
                          onChange={(change) =>
                            updateRow(row.worker_id, { hours: change.target.value })
                          }
                        />
                        <FieldError message={rowErrors[row.worker_id]} />
                      </td>
                      <td className="py-3">
                        <input
                          className={fieldClass}
                          placeholder={t("team.attendance.notePlaceholder")}
                          value={row.note}
                          onChange={(change) =>
                            updateRow(row.worker_id, { note: change.target.value })
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {formError !== null ? <FieldError message={formError} /> : null}
            {savedBanner ? (
              <p className="mt-3 text-[12px] font-semibold text-pri">
                {t("team.attendance.saved")}
              </p>
            ) : null}

            <div className="mt-4 flex justify-end">
              <button
                type="button"
                className={`${primaryBtn} disabled:opacity-60`}
                disabled={saving}
                onClick={() => void saveAttendance()}
              >
                {t("team.attendance.save")}
              </button>
            </div>
          </>
        )}
      </section>

      <section className={cardClass}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-[15px] font-bold">{t("team.attendance.summaryTitle")}</h2>
            <SourceTag kind="calculated" />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[13px]">
            <label className="flex items-center gap-2">
              <span className="font-semibold text-mut">{t("team.attendance.from")}</span>
              <input
                type="date"
                dir="ltr"
                lang="en"
                className="h-9 rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px]"
                value={summaryFrom}
                onChange={(change) => setSummaryFrom(change.target.value)}
              />
            </label>
            <span className="text-mut">–</span>
            <label className="flex items-center gap-2">
              <span className="font-semibold text-mut">{t("team.attendance.to")}</span>
              <input
                type="date"
                dir="ltr"
                lang="en"
                className="h-9 rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px]"
                value={summaryTo}
                onChange={(change) => setSummaryTo(change.target.value)}
              />
            </label>
          </div>
        </div>

        {!rangeValid ? (
          <p className="mt-3 text-[12px] text-red">{t("team.errors.rangeInvalid")}</p>
        ) : summaryQuery.isLoading ? (
          <div className="mt-4 h-28 animate-pulse rounded-xl bg-[#E5E7EB]" />
        ) : summaryQuery.isError || summaryQuery.data === undefined ? (
          <div className="mt-4">
            <LoadError onRetry={() => void summaryQuery.refetch()} />
          </div>
        ) : summaryQuery.data.workers.length === 0 ? (
          <p className="px-2 py-8 text-center text-[13px] text-mut">
            {t("team.attendance.summaryEmpty")}
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[480px] text-start text-[13px]">
              <thead className="text-[11px] uppercase tracking-wide text-mut">
                <tr className="border-b border-line">
                  <th className="py-2 text-start font-semibold">{t("team.workers.name")}</th>
                  <th className="py-2 text-end font-semibold">
                    {t("team.attendance.daysPresent")}
                  </th>
                  <th className="py-2 text-end font-semibold">
                    {t("team.attendance.hours")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {summaryQuery.data.workers.map((row) => (
                  <tr key={row.worker_id} className="border-b border-line last:border-b-0">
                    <td className="py-3 font-semibold">{row.worker_name}</td>
                    <td className="py-3 text-end" dir="ltr">
                      {formatNumber(row.days_present, 0, lang)}
                    </td>
                    <td className="py-3 text-end" dir="ltr">
                      {formatNumber(asNumber(row.hours), 1, lang)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
