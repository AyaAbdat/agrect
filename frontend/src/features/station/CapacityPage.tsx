import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import { useAuth } from "../../app/auth"
import { apiGet, apiSend } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { activeLang, type BlockDetail, type BlockListItem } from "../blocks/types"
import {
  ChoiceChip,
  FieldError,
  FieldLabel,
  FormulaTip,
  LoadError,
  PageHeader,
  PageSkeleton,
  SourceTag,
  cardClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { flowText, groupedValveLabel, hoursText, isPositive, shiftClock } from "./display"
import { stationErrorState } from "./errors"
import type { CapacityCheck, CapacityChoice, CapacityMode, ValveFlow } from "./types"

const CHOICES: CapacityChoice[] = ["priority", "share", "more_shifts"]

function choiceKey(choice: CapacityChoice): string {
  if (choice === "share") return "station.choiceShare"
  if (choice === "more_shifts") return "station.choiceShifts"
  return "station.choicePriority"
}

export function CapacityPage() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId
  const [mode, setMode] = useState<CapacityMode>("today")
  const [choice, setChoice] = useState<CapacityChoice | null>(null)
  const [priorityIds, setPriorityIds] = useState<string[]>([])
  const [reason, setReason] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const checkQuery = useQuery({
    queryKey: ["capacity-check", farmId, mode],
    queryFn: () => apiGet<CapacityCheck>(`/v1/farms/${farmId}/capacity-check?mode=${mode}`),
    enabled: farmId !== null,
  })
  const blocksQuery = useQuery({
    queryKey: ["blocks", farmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${farmId}/blocks`),
    enabled: farmId !== null,
  })
  const valveBlockIds = useMemo(() => {
    const check = checkQuery.data
    if (check === undefined) return []
    const ids = new Set<string>()
    for (const shift of check.shifts) {
      for (const valve of shift.valves) ids.add(valve.block_id)
    }
    for (const valve of check.cannot_supply) ids.add(valve.block_id)
    return [...ids]
  }, [checkQuery.data])
  const detailQueries = useQueries({
    queries: valveBlockIds.map((id) => ({
      queryKey: ["block", id],
      queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${id}`),
    })),
  })

  if (farmId === null) return null
  const detailsLoading = detailQueries.some((query) => query.isLoading)
  const detailsFailed = detailQueries.some((query) => query.isError)
  if (checkQuery.isPending || blocksQuery.isPending || detailsLoading) return <PageSkeleton />
  if (
    checkQuery.isError ||
    blocksQuery.isError ||
    detailsFailed ||
    checkQuery.data === undefined ||
    blocksQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void queryClient.invalidateQueries({ queryKey: ["capacity-check", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["blocks", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["block"] })
        }}
      />
    )
  }

  const check = checkQuery.data
  const summary = check.summary
  const blocks = blocksQuery.data
  const missing = t("common.missing")
  const blockNames = new Map(blocks.map((block) => [block.id, block.name]))
  const valveNames = new Map<string, string>()
  const valveSorts = new Map<string, number>()
  for (const query of detailQueries) {
    if (query.data === undefined) continue
    for (const valve of query.data.valves) {
      valveNames.set(valve.id, valve.name)
      valveSorts.set(valve.id, valve.sort)
    }
  }
  const short = isPositive(summary.short_by_m3h)
  const showDecision = short || check.cannot_supply.length > 0
  const hoursKnown = summary.hours_available !== null

  function label(valves: ValveFlow[]): string {
    return groupedValveLabel(
      valves,
      (id) => blockNames.get(id) ?? missing,
      (id) => valveNames.get(id) ?? missing,
      (id) => valveSorts.get(id) ?? 0,
    )
  }

  function togglePriority(id: string) {
    setPriorityIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]))
  }

  async function saveDecision() {
    const next: Record<string, string> = {}
    if (choice === null) next.choice = "station.errors.choiceRequired"
    if (choice === "priority" && priorityIds.length === 0) next.block_ids = "station.errors.priorityRequired"
    if (reason.trim() === "") next.reason = "station.errors.reasonRequired"
    setErrors(next)
    setFormError(null)
    setSaved(false)
    if (Object.keys(next).length > 0 || choice === null) return
    setSaving(true)
    try {
      await apiSend("POST", `/v1/farms/${farmId}/capacity-decisions`, {
        choice,
        reason: reason.trim(),
        mode,
        block_ids: choice === "priority" ? priorityIds : null,
      })
    } catch (error) {
      const parsed = stationErrorState(error)
      setErrors(parsed.fields)
      setFormError(parsed.form)
      setSaving(false)
      return
    }
    setSaving(false)
    setSaved(true)
  }

  const cannotList = check.cannot_supply.map((valve) => label([valve])).join(", ")
  const noDoseNames = check.no_dose_blocks.map((id) => blockNames.get(id) ?? missing).join(", ")

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("nav.station")}
        title={t("station.capacityTitle")}
        sub={t("station.capacitySub")}
        actions={
          <Link to="/station" className={`inline-flex items-center ${outlineBtn}`}>
            {t("station.back")}
          </Link>
        }
      />
      <div className="flex flex-wrap gap-2">
        <ChoiceChip
          selected={mode === "today"}
          onClick={() => {
            setMode("today")
            setSaved(false)
          }}
        >
          {t("station.today")}
        </ChoiceChip>
        <ChoiceChip
          selected={mode === "peak_week"}
          onClick={() => {
            setMode("peak_week")
            setSaved(false)
          }}
        >
          {t("station.peakWeek")}
        </ChoiceChip>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <section className={cardClass}>
          <div className="flex items-start justify-between gap-2">
            <p className="text-[12px] text-mut">{t("station.flowTile")}</p>
            <SourceTag kind="calculated" />
          </div>
          <p className="mt-2 text-[22px] font-bold" dir="ltr">
            {flowText(summary.open_together_flow_m3h, lang)}{" "}
            <span className="text-[12px] font-medium text-mut">{t("station.unitFlow")}</span>
          </p>
          <p className="mt-1 text-[13px] text-mut" dir="ltr">
            {t("station.ofPumps", { flow: flowText(summary.pumps_flow_m3h, lang) })}
          </p>
          {short ? (
            <span className="mt-2 inline-flex rounded-full bg-[#FEE2E2] px-2 py-0.5 text-[11px] font-semibold text-red">
              {t("station.shortBy", { flow: flowText(summary.short_by_m3h, lang) })}
            </span>
          ) : null}
        </section>
        <section className={cardClass}>
          <div className="flex items-start justify-between gap-2">
            <p className="text-[12px] text-mut">{t("station.hoursTile")}</p>
            <div className="flex items-center gap-2">
              <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
                {t("weather.optional")}
              </span>
              <SourceTag kind="calculated" />
            </div>
          </div>
          {hoursKnown ? (
            <>
              <p className="mt-2 text-[22px] font-bold" dir="ltr">
                {hoursText(summary.hours_needed, lang)}{" "}
                <span className="text-[12px] font-medium text-mut">{t("station.unitHour")}</span>
              </p>
              <p className="mt-1 text-[13px] text-mut" dir="ltr">
                {t("station.ofHours", {
                  hours: hoursText(summary.hours_available, lang),
                  unit: t("station.unitHour"),
                })}
              </p>
              {summary.fits_in_hours === false ? (
                <span className="mt-2 inline-flex rounded-full bg-[#FEE2E2] px-2 py-0.5 text-[11px] font-semibold text-red">
                  {t("station.hoursShort")}
                </span>
              ) : null}
            </>
          ) : (
            <p className="mt-3 text-[13px] text-mut">{t("station.hoursUnset")}</p>
          )}
        </section>
      </div>
      <section className={cardClass}>
        <div className="flex items-center gap-2">
          <h2 className="text-[16px] font-bold">{t("station.shiftsTitle")}</h2>
          <FormulaTip text={t("station.formula")} />
        </div>
        {check.shifts.length === 0 ? (
          <p className="mt-4 text-[13px] text-mut">{t("station.shiftsEmpty")}</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[640px] text-start text-[13px]">
              <thead className="text-[11px] uppercase tracking-wide text-mut">
                <tr className="border-b border-line">
                  <th className="py-2 text-start font-semibold">{t("station.colShift")}</th>
                  <th className="py-2 text-start font-semibold">{t("station.colValves")}</th>
                  <th className="py-2 text-start font-semibold">
                    <span className="inline-flex items-center gap-2">
                      {t("station.colShiftFlow")}
                      <SourceTag kind="calculated" />
                    </span>
                  </th>
                  <th className="py-2 text-start font-semibold">
                    <span className="inline-flex items-center gap-2">
                      {t("station.colTime")}
                      <SourceTag kind="calculated" />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {check.shifts.map((shift, index) => (
                  <tr key={index} className="border-b border-line last:border-b-0">
                    <td className="py-3 font-semibold">
                      {t("station.shiftName", { n: formatNumber(index + 1, 0, lang) })}
                    </td>
                    <td className="py-3">{label(shift.valves)}</td>
                    <td className="py-3" dir="ltr">
                      {flowText(shift.flow_m3h, lang)}
                    </td>
                    <td className="py-3" dir="ltr">
                      {shiftClock(shift.time_min, lang)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {check.cannot_supply.length > 0 ? (
          <p className="mt-3 rounded-xl bg-[#FEF3C7] px-4 py-3 text-[13px] text-amb">
            {t("station.cannotSupply", { list: cannotList })}
          </p>
        ) : null}
        {check.no_dose_blocks.length > 0 ? (
          <p className="mt-3 text-[13px] text-mut">
            {t(mode === "today" ? "station.noDose" : "station.noDosePeak", { list: noDoseNames })}
          </p>
        ) : null}
      </section>
      {showDecision ? (
        <section className={cardClass}>
          <h2 className="text-[16px] font-bold">{t("station.shortTitle")}</h2>
          <div className="mt-3 grid grid-cols-3 gap-3">
            {CHOICES.map((item) => (
              <button
                key={item}
                type="button"
                aria-pressed={choice === item}
                className={`rounded-2xl border p-3 text-start text-[13px] font-semibold ${
                  choice === item ? "border-pri bg-mint" : "border-line bg-white"
                }`}
                onClick={() => setChoice(item)}
              >
                {t(choiceKey(item))}
              </button>
            ))}
          </div>
          <FieldError message={errors.choice} />
          {choice === "priority" ? (
            <div className="mt-4">
              <FieldLabel label={t("station.priorityBlocks")} tag="required" />
              {blocks.length === 0 ? (
                <p className="text-[13px] text-mut">{t("station.noBlocks")}</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {blocks.map((block) => (
                    <li key={block.id}>
                      <label className="flex items-center gap-2 text-[13px]">
                        <input
                          type="checkbox"
                          className="size-4"
                          checked={priorityIds.includes(block.id)}
                          onChange={() => togglePriority(block.id)}
                        />
                        <span>{block.name}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
              <FieldError message={errors.block_ids} />
            </div>
          ) : null}
          <label className="mt-4 block">
            <FieldLabel label={t("station.reason")} tag="required" />
            <textarea
              className="min-h-24 w-full rounded-[10px] border border-[#C7D2C9] bg-white px-3 py-2 text-[13px] outline-none focus:ring-2 focus:ring-mint"
              value={reason}
              aria-invalid={errors.reason !== undefined}
              onChange={(event) => setReason(event.target.value)}
            />
            <FieldError message={errors.reason} />
          </label>
          {formError !== null ? <p className="mt-2 text-[12px] text-red">{t(formError)}</p> : null}
          {saved ? (
            <p role="status" className="mt-3 rounded-xl bg-mint px-4 py-3 text-[13px] text-pri">
              {t("station.decisionSaved")}
            </p>
          ) : null}
          <button
            type="button"
            className={`${primaryBtn} mt-4 disabled:opacity-60`}
            disabled={saving}
            onClick={() => void saveDecision()}
          >
            {t("station.saveDecision")}
          </button>
        </section>
      ) : (
        <p className="rounded-xl bg-mint px-4 py-3 text-[13px] text-pri">{t("station.okLine")}</p>
      )}
    </div>
  )
}
