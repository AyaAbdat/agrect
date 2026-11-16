import { useEffect, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { SatelliteMap } from "../../../components/map/SatelliteMap"
import { formatNumber } from "../../../lib/format"
import { activeLang, type BlockDetail } from "../types"
import {
  reasonPayload,
  reportErrors,
  requireReason,
  submitAction,
  useBlockVersion,
  type StepSaveProps,
} from "./blockWrite"
import { integerKind, integerWire, liveIntegerMessage, submitIntegerMessage } from "./numbers"
import { VALVES_FORM_ID } from "./steps"
import { useCalcPreview } from "./useCalcPreview"
import {
  CalculatedField,
  FieldError,
  FieldLabel,
  SourceTag,
  fieldClass,
  showServerNumber,
} from "./wizardUi"

type Draft = {
  key: string
  from: string
  to: string
  typed: string | null
}

type ValvePreview = {
  row_from: number
  row_to: number
  area_ha: string | null
  q_m3h: string | null
}

type IrrigationPreview = {
  q_block_m3h: string | null
  valves: ValvePreview[]
}

let valveKey = 0

function nextValveKey(): string {
  valveKey += 1
  return `valve-${valveKey}`
}

function rowsTotalOf(value: string): number | null {
  if (integerKind(value) !== "ok") return null
  return Number(value.trim())
}

function requiredWhole(value: string): string | null {
  if (value.trim() === "") return "blocks.errors.whole"
  return submitIntegerMessage(value)
}

function draftsFrom(block: BlockDetail): Draft[] {
  const sorted = [...block.valves].sort((left, right) => left.sort - right.sort)
  if (sorted.length > 0) {
    return sorted.map((valve) => ({
      key: valve.id,
      from: String(valve.row_from),
      to: String(valve.row_to),
      typed: valve.typed_q_m3h,
    }))
  }
  if (block.rows_total !== null && block.rows_total > 0) {
    return [{ key: nextValveKey(), from: "1", to: String(block.rows_total), typed: null }]
  }
  return []
}

function nextFreeRange(valves: Draft[], rowsTotal: number | null): { from: string; to: string } {
  if (rowsTotal === null) return { from: "", to: "" }
  const covered = new Set<number>()
  for (const valve of valves) {
    const from = integerWire(valve.from)
    const to = integerWire(valve.to)
    if (from === null || to === null) continue
    const start = Number(from)
    const end = Number(to)
    if (start > end) continue
    for (let row = Math.max(1, start); row <= Math.min(rowsTotal, end); row += 1) {
      covered.add(row)
    }
  }
  let start: number | null = null
  for (let row = 1; row <= rowsTotal; row += 1) {
    if (!covered.has(row) && start === null) start = row
    if (covered.has(row) && start !== null) {
      return { from: String(start), to: String(row - 1) }
    }
  }
  if (start !== null) return { from: String(start), to: String(rowsTotal) }
  return { from: "", to: "" }
}

function previewPayload(block: BlockDetail, rows: string, valves: Draft[]) {
  const layout = block.irrigation_layout
  const planting = block.plantings[0]
  const sent = valves.flatMap((valve) => {
    const from = integerWire(valve.from)
    const to = integerWire(valve.to)
    if (from === null || to === null) return []
    return [
      {
        row_from: from,
        row_to: to,
        typed_q_m3h: valve.typed,
      },
    ]
  })
  const shared = {
    net_area_ha: block.net_area_ha,
    rows_total: integerWire(rows),
    valves: sent,
  }
  if (layout?.entry_mode === "typed_flow") {
    return {
      entry_mode: "typed_flow" as const,
      typed_flow_m3h: layout.typed_flow_m3h,
      typed_flow_basis: layout.typed_flow_basis,
      ...shared,
    }
  }
  if (layout?.entry_mode === "per_tree") {
    return {
      entry_mode: "per_tree" as const,
      trees_per_ha: planting?.trees_per_ha ?? null,
      emitters_per_tree: layout.emitters_per_tree,
      flow_per_emitter_lph: layout.flow_per_emitter_lph,
      ...shared,
    }
  }
  return {
    entry_mode: "layout" as const,
    row_spacing_m: planting?.row_spacing_m ?? null,
    laterals_per_row: layout?.laterals_per_row ?? null,
    emitter_spacing_m: layout?.emitter_spacing_m ?? null,
    emitter_flow_lph: layout?.emitter_flow_lph ?? null,
    ...shared,
  }
}

export function ValvesStep({ block, reason, onReasonError, onBusy }: StepSaveProps) {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { write, finish } = useBlockVersion(block)
  const [rows, setRows] = useState(block.rows_total === null ? "" : String(block.rows_total))
  const [valves, setValves] = useState<Draft[]>(() => draftsFrom(block))
  const autoTo = useRef<string | null>(
    block.valves.length <= 1 && block.rows_total !== null ? String(block.rows_total) : null,
  )
  const [rowsError, setRowsError] = useState<string | null>(null)
  const [rowFieldErrors, setRowFieldErrors] = useState<Record<string, string>>({})
  const [saveErrors, setSaveErrors] = useState<Record<number, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const body = useMemo(() => previewPayload(block, rows, valves), [block, rows, valves])
  const preview = useCalcPreview<IrrigationPreview>("/v1/calc/registry/irrigation", body)

  useEffect(() => {
    const total = rowsTotalOf(rows)
    if (total === null) return
    const next = String(total)
    setValves((current) => {
      if (current.length === 0) {
        autoTo.current = next
        return [{ key: nextValveKey(), from: "1", to: next, typed: null }]
      }
      const only = current[0]
      if (
        current.length === 1 &&
        only !== undefined &&
        only.from.trim() === "1" &&
        autoTo.current !== null &&
        only.to === autoTo.current
      ) {
        if (only.to === next) return current
        autoTo.current = next
        return [{ ...only, to: next }]
      }
      return current
    })
  }, [rows])

  const sentIndexes = valves.flatMap((valve, index) => {
    if (integerWire(valve.from) === null || integerWire(valve.to) === null) return []
    return [index]
  })

  function previewFor(index: number): ValvePreview | undefined {
    const sentIndex = sentIndexes.indexOf(index)
    if (sentIndex < 0) return undefined
    return preview.data?.valves[sentIndex]
  }

  function serverError(index: number): string | undefined {
    const sentIndex = sentIndexes.indexOf(index)
    const previewError =
      sentIndex < 0 ? undefined : preview.fieldErrors[`valves.${sentIndex}.row_from`]
    return rowFieldErrors[valves[index]?.key ?? ""] ?? saveErrors[index] ?? previewError
  }

  function updateValve(key: string, patch: Partial<Draft>) {
    setValves((current) =>
      current.map((valve) => (valve.key === key ? { ...valve, ...patch } : valve)),
    )
    setSaveErrors({})
    setRowFieldErrors((current) => {
      if (current[key] === undefined) return current
      const next = { ...current }
      delete next[key]
      return next
    })
  }

  async function persist(event: { nativeEvent?: Event }) {
    const rowsMessage = requiredWhole(rows)
    setRowsError(rowsMessage)
    const nextFieldErrors: Record<string, string> = {}
    for (const valve of valves) {
      const message = requiredWhole(valve.from) ?? requiredWhole(valve.to)
      if (message !== null) nextFieldErrors[valve.key] = message
    }
    setRowFieldErrors(nextFieldErrors)
    setSaveErrors({})
    setFormError(null)
    if (!requireReason(block, reason, onReasonError)) return
    if (rowsMessage !== null || Object.keys(nextFieldErrors).length > 0) return
    onBusy(true)
    try {
      const savedRows = await write("PATCH", `/v1/blocks/${block.id}`, {
        rows_total: Number(rows.trim()),
        ...reasonPayload(block, reason),
      })
      const saved = await write("PUT", `/v1/blocks/${savedRows.id}/valves`, {
        valves: valves.map((valve, index) => ({
          name: `V${index + 1}`,
          row_from: Number(valve.from.trim()),
          row_to: Number(valve.to.trim()),
          typed_q_m3h: valve.typed,
        })),
        ...reasonPayload(block, reason),
      })
      await finish(saved, submitAction(event), 6)
    } catch (error) {
      const found: Record<number, string> = {}
      const outcome = reportErrors(error, (field, key) => {
        if (field === "reason") {
          onReasonError(key)
          return true
        }
        if (field === "rows_total") {
          setRowsError(key)
          return true
        }
        const match = /^valves\.(\d+)\.row_from$/.exec(field)
        if (match !== null) {
          found[Number(match[1])] = key
          return true
        }
        return false
      })
      setSaveErrors(found)
      if (outcome === "version") setFormError("blocks.errors.version")
      else if (outcome === "save" || outcome === "partial") setFormError("blocks.errors.save")
    } finally {
      onBusy(false)
    }
  }

  const blockFlow = showServerNumber(preview.data?.q_block_m3h ?? null, 2, lang)
  const rowsLive = liveIntegerMessage(rows)

  return (
    <>
      <div className="min-w-0 flex-1">
        <p className="mb-2 text-[13px] font-semibold">{t("blocks.outlineYours")}</p>
        <SatelliteMap
          height={560}
          blocks={[{ id: block.id, name: block.name, outline: block.outline }]}
        />
        <p className="mt-2 text-[12px] text-mut">{t("blocks.mapSplitLater")}</p>
      </div>
      <form
        id={VALVES_FORM_ID}
        className="flex w-[380px] shrink-0 flex-col gap-4 rounded-2xl border border-line bg-white p-4"
        noValidate
        onSubmit={(event) => {
          event.preventDefault()
          void persist(event)
        }}
      >
        <p className="text-[13px] text-mut">{t("blocks.valvesIntro")}</p>
        <label className="block">
          <FieldLabel label={t("blocks.rowsInBlock")} tag="entered" />
          <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
            <input
              className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
              inputMode="numeric"
              autoComplete="off"
              value={rows}
              onChange={(event) => {
                setRows(event.target.value)
                setRowsError(null)
              }}
            />
            <span className="text-mut">{t("blocks.unitRows")}</span>
          </span>
          <p className="mt-1 text-[12px] text-mut">{t("blocks.rowsHelp")}</p>
          <FieldError message={rowsError ?? rowsLive ?? undefined} />
        </label>
        {valves.map((valve, index) => {
          const result = previewFor(index)
          const number = formatNumber(index + 1, 0, lang)
          const fromLive = liveIntegerMessage(valve.from)
          const toLive = liveIntegerMessage(valve.to)
          return (
            <section key={valve.key} className="rounded-xl border border-line p-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-[13px] font-bold">
                  {t("blocks.valveCard", {
                    index: number,
                    name: t("blocks.valveName", { index: number }),
                  })}
                </h2>
                {valves.length > 1 ? (
                  <button
                    type="button"
                    className="text-[12px] font-semibold text-red"
                    onClick={() => {
                      setValves((current) => current.filter((item) => item.key !== valve.key))
                      setSaveErrors({})
                    }}
                  >
                    {t("blocks.removeValve")}
                  </button>
                ) : null}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="mb-1.5 block text-[13px] font-semibold">{t("blocks.fromRow")}</span>
                  <input
                    className={fieldClass}
                    inputMode="numeric"
                    autoComplete="off"
                    value={valve.from}
                    onChange={(event) => updateValve(valve.key, { from: event.target.value })}
                  />
                  <FieldError message={fromLive ?? undefined} />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[13px] font-semibold">{t("blocks.toRow")}</span>
                  <input
                    className={fieldClass}
                    inputMode="numeric"
                    autoComplete="off"
                    value={valve.to}
                    onChange={(event) => updateValve(valve.key, { to: event.target.value })}
                  />
                  <FieldError message={toLive ?? undefined} />
                </label>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <CalculatedField
                  label={t("blocks.valveArea")}
                  value={showServerNumber(result?.area_ha ?? null, 2, lang)}
                  unit={t("blocks.unitHa")}
                />
                <CalculatedField
                  label={t("blocks.valveFlow")}
                  value={showServerNumber(result?.q_m3h ?? null, 2, lang)}
                  unit={t("blocks.unitFlow")}
                />
              </div>
              <FieldError message={serverError(index)} />
            </section>
          )
        })}
        <Button
          type="button"
          variant="outline"
          className="h-9 rounded-full px-4"
          onClick={() => {
            const range = nextFreeRange(valves, rowsTotalOf(rows))
            setValves((current) => [
              ...current,
              { key: nextValveKey(), from: range.from, to: range.to, typed: null },
            ])
          }}
        >
          {t("blocks.addValve")}
        </Button>
        <div className="flex items-center justify-between gap-3 border-t border-line pt-3">
          <span className="text-[13px]">{t("blocks.valveFlowSum")}</span>
          <span className="flex items-center gap-2 text-[13px] font-semibold">
            <SourceTag />
            <span>
              {blockFlow} {t("blocks.unitFlow")}
            </span>
          </span>
        </div>
        {preview.error !== null ? <p className="text-[12px] text-red">{t(preview.error)}</p> : null}
        {formError !== null ? <p className="text-[12px] text-red">{t(formError)}</p> : null}
      </form>
    </>
  )
}
