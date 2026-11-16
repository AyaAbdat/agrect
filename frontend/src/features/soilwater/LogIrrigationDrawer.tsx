import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import { useAuth } from "../../app/auth"
import { Drawer } from "../../components/Drawer"
import { ApiError, apiSend } from "../../lib/api"
import { UNIT_MM } from "../../lib/units"
import { activeLang, type BlockValve } from "../blocks/types"
import { asNumber } from "../weather/format"
import { FieldError, FieldLabel, SourceTag, fieldClass, outlineBtn, primaryBtn } from "../weather/ui"
import { farmDateAndTime, farmWallIso, mm2 } from "./display"
import { soilErrorKey } from "./errors"
import { refreshWater } from "./refresh"
import type { IrrigationEvent, IrrigationPreview } from "./types"

const FORM_ID = "log-irrigation"

function whole(value: string): number | null {
  if (!/^\d+$/.test(value.trim())) return null
  return Number(value)
}

function runMinutes(hoursText: string, minutesText: string): number | null {
  const hours = whole(hoursText)
  const minutes = whole(minutesText)
  if (hours === null || minutes === null || minutes > 59) return null
  return hours * 60 + minutes
}

export function LogIrrigationDrawer({
  open,
  onOpenChange,
  blockId,
  blockName,
  valves,
  timeZone,
  today,
  event,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  blockId: string
  blockName: string
  valves: BlockValve[]
  timeZone: string
  today: string
  event: IrrigationEvent | null
}) {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const queryClient = useQueryClient()
  const { currentFarmId } = useAuth()
  const ordered = [...valves].sort((left, right) => left.sort - right.sort)
  const [date, setDate] = useState(today)
  const [time, setTime] = useState("")
  const [hours, setHours] = useState("0")
  const [minutes, setMinutes] = useState("0")
  const [selected, setSelected] = useState<string[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [notReady, setNotReady] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [preview, setPreview] = useState<IrrigationPreview | null>(null)
  const [saving, setSaving] = useState(false)
  const duration = runMinutes(hours, minutes)
  const valveKey = [...selected].sort().join(",")
  const knownIds = ordered.map((valve) => valve.id).join(",")

  useEffect(() => {
    if (!open) return
    const ids = knownIds === "" ? [] : knownIds.split(",")
    if (event === null) {
      setDate(today)
      setTime("")
      setHours("0")
      setMinutes("0")
      setSelected(ids)
    } else {
      const parts = farmDateAndTime(event.start_at, timeZone)
      setDate(parts.date)
      setTime(parts.time)
      setHours(String(Math.floor(event.duration_min / 60)))
      setMinutes(String(event.duration_min % 60))
      const known = new Set(ids)
      setSelected(event.valve_ids.filter((id) => known.has(id)))
    }
    setErrors({})
    setNotReady(false)
    setFormError(null)
    setPreview(null)
  }, [open, event, today, timeZone, knownIds])

  useEffect(() => {
    if (!open || duration === null || duration <= 0 || selected.length === 0) {
      setPreview(null)
      return
    }
    let cancelled = false
    const handle = window.setTimeout(() => {
      void apiSend<IrrigationPreview>("POST", "/v1/calc/soilwater/irrigation", {
        block_id: blockId,
        valve_ids: selected,
        duration_min: duration,
      })
        .then((body) => {
          if (cancelled) return
          setPreview(body)
          setNotReady(false)
        })
        .catch((error: unknown) => {
          if (cancelled) return
          setPreview(null)
          if (error instanceof ApiError && error.fields.irrigation === "irrigation.block_not_ready") {
            setNotReady(true)
          }
        })
    }, 300)
    return () => {
      cancelled = true
      window.clearTimeout(handle)
    }
  }, [open, blockId, duration, valveKey, selected])

  function toggle(id: string) {
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  async function onSubmit(submitEvent: FormEvent) {
    submitEvent.preventDefault()
    const next: Record<string, string> = {}
    if (selected.length === 0) next.valves = "soil.errors.valveRequired"
    const minuteValue = whole(minutes)
    if (minuteValue === null || minuteValue > 59) next.minutes = "soil.errors.minutesRange"
    if (duration === null || duration <= 0) {
      if (next.minutes === undefined) next.run = "soil.errors.runTime"
    }
    if (time.trim() === "") next.time = "soil.errors.startRequired"
    if (date.trim() === "") next.date = "soil.errors.dateRequired"
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0 || duration === null || duration <= 0) return
    setSaving(true)
    setNotReady(false)
    const payload = {
      valve_ids: selected,
      start_at: farmWallIso(date, time, timeZone),
      duration_min: duration,
    }
    try {
      if (event === null) {
        await apiSend("POST", `/v1/blocks/${blockId}/irrigation-events`, payload)
      } else {
        await apiSend(
          "PATCH",
          `/v1/blocks/${blockId}/irrigation-events/${event.id}`,
          payload,
          { "If-Match": String(event.version) },
        )
      }
    } catch (error) {
      setSaving(false)
      if (error instanceof ApiError) {
        if (error.status === 409 || error.status === 428) {
          setFormError("soil.errors.conflict")
          return
        }
        if (error.fields.irrigation === "irrigation.block_not_ready") {
          setNotReady(true)
          return
        }
        const valveCode = error.fields.valve_ids
        if (valveCode !== undefined) {
          setErrors((current) => ({ ...current, valves: soilErrorKey(valveCode) }))
          return
        }
      }
      setFormError("soil.errors.save")
      return
    }
    await refreshWater(queryClient, blockId, currentFarmId)
    setSaving(false)
    onOpenChange(false)
  }

  const runoff = asNumber(preview?.runoff_mm)

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={t("soil.setupCrumb")}
      title={t(event === null ? "soil.drawerTitle" : "soil.drawerEditTitle")}
      footer={
        <div className="flex justify-end gap-2">
          <button type="button" className={outlineBtn} onClick={() => onOpenChange(false)}>
            {t("soil.cancel")}
          </button>
          <button type="submit" form={FORM_ID} className={primaryBtn} disabled={saving}>
            {t("soil.save")}
          </button>
        </div>
      }
    >
      <form id={FORM_ID} className="flex flex-col gap-4" onSubmit={(submitEvent) => void onSubmit(submitEvent)}>
        <label className="block">
          <FieldLabel label={t("soil.block")} tag="required" />
          <select className={`${fieldClass} disabled:bg-[#F7F8F7] disabled:text-mut`} value={blockId} disabled>
            <option value={blockId}>{blockName}</option>
          </select>
        </label>
        <fieldset>
          <FieldLabel label={t("soil.valvesOpen")} tag="required" />
          {ordered.length === 0 ? (
            <p className="text-[13px] text-mut">{t("soil.noValves")}</p>
          ) : (
            <div className="flex flex-col gap-2">
              {ordered.map((valve) => (
                <label key={valve.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selected.includes(valve.id)}
                    onChange={() => toggle(valve.id)}
                  />
                  <span>{valve.name}</span>
                </label>
              ))}
            </div>
          )}
          <FieldError message={errors.valves} />
        </fieldset>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <FieldLabel label={t("soil.date")} tag="required" />
            <input
              type="date"
              dir="ltr"
              lang="en"
              className={fieldClass}
              value={date}
              aria-invalid={errors.date !== undefined}
              onChange={(change) => setDate(change.target.value)}
            />
            <FieldError message={errors.date} />
          </label>
          <label className="block">
            <FieldLabel label={t("soil.startTime")} tag="required" />
            <input
              type="time"
              dir="ltr"
              lang="en"
              className={fieldClass}
              value={time}
              aria-invalid={errors.time !== undefined}
              onChange={(change) => setTime(change.target.value)}
            />
            <FieldError message={errors.time} />
          </label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <FieldLabel label={t("soil.runHours")} tag="required" />
            <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
              <input
                className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
                inputMode="numeric"
                dir="ltr"
                lang="en"
                value={hours}
                aria-invalid={errors.run !== undefined}
                onChange={(change) => setHours(change.target.value)}
              />
              <span className="text-[12px] text-mut">{t("soil.hoursUnit")}</span>
            </span>
            <FieldError message={errors.run} />
          </label>
          <label className="block">
            <FieldLabel label={t("soil.runMinutes")} />
            <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
              <input
                className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
                inputMode="numeric"
                dir="ltr"
                lang="en"
                value={minutes}
                aria-invalid={errors.minutes !== undefined}
                onChange={(change) => setMinutes(change.target.value)}
              />
              <span className="text-[12px] text-mut">{t("soil.minutesUnit")}</span>
            </span>
            <FieldError message={errors.minutes} />
          </label>
        </div>
        <section className="rounded-xl bg-[#F7F8F7] p-3">
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-[15px] font-bold">{t("soil.waterApplied")}</h2>
            <SourceTag kind="calculated" />
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-3">
            <div>
              <dt className="text-[12px] text-mut">{t("soil.depth")}</dt>
              <dd className="text-[18px] font-bold">
                {mm2(preview?.depth_mm, lang)}{" "}
                <span className="text-[12px] font-medium text-mut">{UNIT_MM}</span>
              </dd>
            </div>
            <div>
              <dt className="text-[12px] text-mut">{t("soil.volume")}</dt>
              <dd className="text-[18px] font-bold">
                {mm2(preview?.volume_m3, lang)}{" "}
                <span className="text-[12px] font-medium text-mut">{t("soil.unitM3")}</span>
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-[13px]">
            {t("soil.entering")}{" "}
            <span className="font-semibold">
              {mm2(preview?.soil_mm, lang)} {UNIT_MM}
            </span>
          </p>
          {runoff !== null && runoff > 0 ? (
            <p className="mt-1 text-[13px] text-amb">
              {t("soil.runoff")}{" "}
              <span className="font-semibold">
                {mm2(runoff, lang)} {UNIT_MM}
              </span>
            </p>
          ) : null}
          <p className="mt-3 text-[12px] text-mut">{t("soil.flowNote")}</p>
        </section>
        {notReady ? (
          <p className="text-[12px] text-red">
            {t("soil.errors.blockNotReady")}{" "}
            <Link to={`/blocks/${blockId}/setup`} className="font-semibold text-pri">
              {t("soil.setupLink")}
            </Link>
          </p>
        ) : null}
        {formError !== null ? <FieldError message={formError} /> : null}
      </form>
    </Drawer>
  )
}
