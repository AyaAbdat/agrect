import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { apiSend } from "../../lib/api"
import { decimalInput } from "../weather/format"
import { FieldError, FieldLabel, fieldClass, outlineBtn, primaryBtn } from "../weather/ui"
import { clockHm, sameIds } from "./display"
import { Help } from "./dialog"
import { optionalWire, positiveWire, stationErrorState } from "./errors"
import type { Pump, WaterSource, WindowDraft } from "./types"

const FORM_ID = "pump-form"

function windowsDiffer(saved: Pump | null, draft: WindowDraft[]): boolean {
  const rows = saved?.windows ?? []
  if (rows.length !== draft.length) return true
  return rows.some((row, index) => {
    const item = draft[index]
    return item === undefined || clockHm(row.start_time) !== item.start || clockHm(row.end_time) !== item.end
  })
}

function blocksDiffer(saved: Pump | null, servesAll: boolean, ids: string[]): boolean {
  if (saved === null) return !servesAll
  if (saved.serves_all_blocks !== servesAll) return true
  if (servesAll) return false
  return !sameIds(
    saved.blocks.map((block) => block.id),
    ids,
  )
}

export function PumpDrawer({
  open,
  onOpenChange,
  farmId,
  pump,
  blocks,
  sources,
  selectSourceId,
  onSourceSelected,
  onAddSource,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  farmId: string
  pump: Pump | null
  blocks: { id: string; name: string }[]
  sources: WaterSource[]
  selectSourceId: string | null
  onSourceSelected: () => void
  onAddSource: () => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const created = useRef<Pump | null>(null)
  const preserve = useRef(false)
  const openKey = useRef<string | null>(null)
  const [name, setName] = useState("")
  const [flow, setFlow] = useState("")
  const [servesAll, setServesAll] = useState(true)
  const [blockIds, setBlockIds] = useState<string[]>([])
  const [pressure, setPressure] = useState("")
  const [sourceId, setSourceId] = useState("")
  const [windows, setWindows] = useState<WindowDraft[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function applyPump(source: Pump | null) {
    created.current = null
    setName(source?.name ?? "")
    setFlow(decimalInput(source?.flow_m3h ?? null))
    setServesAll(source?.serves_all_blocks ?? true)
    setBlockIds(source?.blocks.map((block) => block.id) ?? [])
    setPressure(decimalInput(source?.pressure_bar ?? null))
    setSourceId(source?.water_source?.id ?? "")
    setWindows(
      source?.windows.map((window) => ({
        start: clockHm(window.start_time),
        end: clockHm(window.end_time),
      })) ?? [],
    )
    setErrors({})
    setFormError(null)
  }

  useEffect(() => {
    if (!open) {
      if (!preserve.current) openKey.current = null
      return
    }
    const key = pump?.id ?? "new"
    if (preserve.current) {
      preserve.current = false
      openKey.current = key
      return
    }
    if (openKey.current === key) return
    openKey.current = key
    applyPump(pump)
  }, [open, pump])

  useEffect(() => {
    if (selectSourceId === null) return
    setSourceId(selectSourceId)
    onSourceSelected()
  }, [selectSourceId, onSourceSelected])

  function toggleBlock(id: string) {
    setBlockIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]))
  }

  function updateWindow(index: number, patch: Partial<WindowDraft>) {
    setWindows((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)))
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (name.trim() === "") next.name = "station.errors.nameRequired"
    const flowParsed = positiveWire(flow)
    if (!flowParsed.ok || flowParsed.wire === null) {
      next.flow_m3h = flowParsed.empty ? "station.errors.flowRequired" : "station.errors.flowPositive"
    }
    const pressureParsed = optionalWire(pressure)
    if (!pressureParsed.ok) next.pressure_bar = "station.errors.number"
    const filled = windows.filter((row) => row.start !== "" || row.end !== "")
    if (filled.some((row) => row.start === "" || row.end === "")) {
      next.windows = "station.errors.windowInvalid"
    }
    if (!servesAll && blockIds.length === 0) next.block_ids = "station.errors.blockRequired"
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0 || flowParsed.wire === null || !pressureParsed.ok) return

    const base = created.current ?? pump
    const creating = base === null
    const windowsNeedPut = windowsDiffer(base, filled)
    const blocksNeedPut = !creating && !servesAll && blocksDiffer(base, servesAll, blockIds)
    const pumpBody = {
      name: name.trim(),
      flow_m3h: flowParsed.wire,
      serves_all_blocks: servesAll,
      pressure_bar: pressureParsed.wire,
      water_source_id: sourceId === "" ? null : sourceId,
    }
    setSaving(true)
    let current = base
    try {
      if (current === null) {
        current = await apiSend<Pump>("POST", `/v1/farms/${farmId}/station/pumps`, {
          ...pumpBody,
          ...(servesAll ? {} : { block_ids: blockIds }),
        })
      } else {
        current = await apiSend<Pump>("PATCH", `/v1/pumps/${current.id}`, pumpBody, {
          "If-Match": String(current.version),
        })
      }
      created.current = current
      if (windowsNeedPut) {
        current = await apiSend<Pump>(
          "PUT",
          `/v1/pumps/${current.id}/windows`,
          { windows: filled.map((row) => ({ start_time: row.start, end_time: row.end })) },
          { "If-Match": String(current.version) },
        )
        created.current = current
      }
      if (blocksNeedPut) {
        current = await apiSend<Pump>(
          "PUT",
          `/v1/pumps/${current.id}/blocks`,
          { block_ids: blockIds },
          { "If-Match": String(current.version) },
        )
        created.current = current
      }
      await queryClient.invalidateQueries({ queryKey: ["station", farmId] })
      await queryClient.invalidateQueries({ queryKey: ["capacity-check", farmId] })
      created.current = null
      setSaving(false)
      onOpenChange(false)
    } catch (error) {
      if (created.current !== null) {
        await queryClient.invalidateQueries({ queryKey: ["station", farmId] })
      }
      const parsed = stationErrorState(error)
      setErrors(parsed.fields)
      setFormError(parsed.form)
      setSaving(false)
    }
  }

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={t("nav.station")}
      title={t(pump === null ? "station.drawerAdd" : "station.drawerEdit")}
      footer={
        <div className="flex justify-end gap-2">
          <button type="button" className={outlineBtn} onClick={() => onOpenChange(false)}>
            {t("station.cancel")}
          </button>
          <button type="submit" form={FORM_ID} className={`${primaryBtn} disabled:opacity-60`} disabled={saving}>
            {t("station.save")}
          </button>
        </div>
      }
    >
      <form id={FORM_ID} className="flex flex-col gap-4" onSubmit={(event) => void onSubmit(event)}>
        {formError !== null ? <p className="text-[12px] text-red">{t(formError)}</p> : null}
        <label className="block">
          <FieldLabel label={t("station.name")} tag="required" />
          <input
            className={fieldClass}
            value={name}
            aria-invalid={errors.name !== undefined}
            onChange={(event) => setName(event.target.value)}
          />
          <FieldError message={errors.name} />
        </label>
        <label className="block">
          <FieldLabel label={t("station.flow")} tag="required" />
          <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
            <input
              className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
              inputMode="decimal"
              dir="ltr"
              lang="en"
              value={flow}
              aria-invalid={errors.flow_m3h !== undefined}
              onChange={(event) => setFlow(event.target.value)}
            />
            <span className="text-[12px] text-mut">{t("station.unitFlow")}</span>
          </span>
          <Help>{t("station.flowHelp")}</Help>
          <FieldError message={errors.flow_m3h} />
        </label>
        <fieldset>
          <FieldLabel label={t("station.blocksLabel")} />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              aria-pressed={servesAll}
              className={`inline-flex h-8 items-center rounded-full px-3 text-[12px] font-semibold ${servesAll ? "bg-pri text-white" : "border border-[#C7D2C9] bg-white"}`}
              onClick={() => setServesAll(true)}
            >
              {t("station.allBlocks")}
            </button>
            <button
              type="button"
              aria-pressed={!servesAll}
              className={`inline-flex h-8 items-center rounded-full px-3 text-[12px] font-semibold ${servesAll ? "border border-[#C7D2C9] bg-white" : "bg-pri text-white"}`}
              onClick={() => setServesAll(false)}
            >
              {t("station.onlySome")}
            </button>
          </div>
          {!servesAll ? (
            blocks.length === 0 ? (
              <p className="mt-3 text-[13px] text-mut">{t("station.noBlocks")}</p>
            ) : (
              <ul className="mt-3 flex flex-col gap-2">
                {blocks.map((block) => (
                  <li key={block.id}>
                    <label className="flex items-center gap-2 text-[13px]">
                      <input
                        type="checkbox"
                        className="size-4"
                        checked={blockIds.includes(block.id)}
                        onChange={() => toggleBlock(block.id)}
                      />
                      <span>{block.name}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )
          ) : null}
          <Help>{t("station.blocksHelp")}</Help>
          <FieldError message={errors.block_ids} />
        </fieldset>
        <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#9CA3AF]">
          {t("station.optionalSkip")}
        </p>
        <label className="block">
          <FieldLabel label={t("station.pressure")} tag="optional" />
          <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
            <input
              className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
              inputMode="decimal"
              dir="ltr"
              lang="en"
              value={pressure}
              aria-invalid={errors.pressure_bar !== undefined}
              onChange={(event) => setPressure(event.target.value)}
            />
            <span className="text-[12px] text-mut">{t("station.unitBar")}</span>
          </span>
          <FieldError message={errors.pressure_bar} />
        </label>
        <div>
          <FieldLabel label={t("station.source")} tag="optional" />
          <select
            className={fieldClass}
            value={sourceId}
            aria-invalid={errors.water_source_id !== undefined}
            onChange={(event) => setSourceId(event.target.value)}
          >
            <option value="">{t("station.sourceNone")}</option>
            {sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="mt-2 text-[13px] font-semibold text-pri"
            onClick={() => {
              preserve.current = true
              onAddSource()
            }}
          >
            {t("station.addSource")}
          </button>
          <FieldError message={errors.water_source_id} />
        </div>
        <div>
          <FieldLabel label={t("station.hoursAvailable")} tag="optional" />
          <div className="flex flex-col gap-2">
            {windows.map((row, index) => (
              <div key={index} className="flex items-end gap-2">
                <label className="min-w-0 flex-1">
                  <span className="mb-1 block text-[12px] text-mut">{t("station.windowStart")}</span>
                  <input
                    type="time"
                    dir="ltr"
                    lang="en"
                    className={fieldClass}
                    value={row.start}
                    onChange={(event) => updateWindow(index, { start: event.target.value })}
                  />
                </label>
                <label className="min-w-0 flex-1">
                  <span className="mb-1 block text-[12px] text-mut">{t("station.windowEnd")}</span>
                  <input
                    type="time"
                    dir="ltr"
                    lang="en"
                    className={fieldClass}
                    value={row.end}
                    onChange={(event) => updateWindow(index, { end: event.target.value })}
                  />
                </label>
                <button
                  type="button"
                  className={outlineBtn}
                  onClick={() => setWindows((current) => current.filter((_, rowIndex) => rowIndex !== index))}
                >
                  {t("station.removeWindow")}
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            className={`${outlineBtn} mt-2`}
            onClick={() => setWindows((current) => [...current, { start: "", end: "" }])}
          >
            {t("station.addWindow")}
          </button>
          <Help>{t("station.hoursHelp")}</Help>
          <FieldError message={errors.windows} />
        </div>
        <label className="block">
          <span className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold">{t("station.injector")}</span>
            <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
              {t("settings.phase2")}
            </span>
          </span>
          <select className={`${fieldClass} disabled:bg-[#F7F8F7] disabled:text-mut`} disabled>
            <option value="">{t("common.missing")}</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold">{t("station.flowMeter")}</span>
            <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
              {t("settings.phase2")}
            </span>
          </span>
          <select className={`${fieldClass} disabled:bg-[#F7F8F7] disabled:text-mut`} disabled>
            <option value="">{t("common.missing")}</option>
          </select>
        </label>
      </form>
    </Drawer>
  )
}
