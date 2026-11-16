import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { decimalInput } from "../errors"
import { activeLang, type IrrigationSystem } from "../types"
import {
  reasonPayload,
  reportErrors,
  requireReason,
  submitAction,
  useBlockVersion,
  type StepSaveProps,
} from "./blockWrite"
import {
  decimalWire,
  integerWire,
  liveDecimalMessage,
  liveIntegerMessage,
  submitDecimalMessage,
  submitIntegerMessage,
} from "./numbers"
import { IRRIGATION_FORM_ID } from "./steps"
import { useCalcPreview } from "./useCalcPreview"
import {
  CalculatedField,
  Chip,
  ExplainerCard,
  FieldError,
  OptionalTag,
  SectionLabel,
  TextField,
  panelClass,
  showServerNumber,
  type ExplainerLine,
} from "./wizardUi"

const SYSTEMS = [
  "drip",
  "subsurface_drip",
  "micro_sprinkler",
  "bubbler",
  "sprinkler",
] as const satisfies readonly IrrigationSystem[]

const irrigationSchema = z
  .object({
    system: z.enum(SYSTEMS),
    entry_mode: z.enum(["layout", "typed_flow"]),
    laterals_per_row: z.string(),
    emitter_spacing_m: z.string(),
    emitter_flow_lph: z.string(),
    typed_flow_m3h: z.string(),
    flow_meter: z.boolean(),
  })
  .superRefine((values, ctx) => {
    const checks: Array<[string, string | null]> =
      values.entry_mode === "layout"
        ? [
            ["laterals_per_row", submitIntegerMessage(values.laterals_per_row)],
            ["emitter_spacing_m", submitDecimalMessage(values.emitter_spacing_m)],
            ["emitter_flow_lph", submitDecimalMessage(values.emitter_flow_lph)],
          ]
        : [["typed_flow_m3h", submitDecimalMessage(values.typed_flow_m3h)]]
    for (const [path, message] of checks) {
      if (message === null) continue
      ctx.addIssue({ code: "custom", message, path: [path] })
    }
  })

type IrrigationValues = z.infer<typeof irrigationSchema>

type IrrigationPreview = {
  q_ha_m3h: string | null
  q_block_m3h: string | null
  rate_mm_h: string | null
  row_m_per_ha: string | null
  lateral_m_per_ha: string | null
  emitters_per_ha: string | null
  source: "calculated"
}

function initialValues(block: StepSaveProps["block"]): IrrigationValues {
  const layout = block.irrigation_layout
  return {
    system: layout?.system ?? "drip",
    entry_mode: layout?.entry_mode === "typed_flow" ? "typed_flow" : "layout",
    laterals_per_row: layout?.laterals_per_row != null ? String(layout.laterals_per_row) : "",
    emitter_spacing_m: decimalInput(layout?.emitter_spacing_m ?? null),
    emitter_flow_lph: decimalInput(layout?.emitter_flow_lph ?? null),
    typed_flow_m3h: decimalInput(layout?.typed_flow_m3h ?? null),
    flow_meter: layout?.flow_meter ?? false,
  }
}

export function IrrigationStep({ block, reason, onReasonError, onBusy }: StepSaveProps) {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { write, finish } = useBlockVersion(block)
  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<IrrigationValues>({
    resolver: zodResolver(irrigationSchema),
    defaultValues: initialValues(block),
  })
  const system = form.watch("system")
  const entry = form.watch("entry_mode")
  const laterals = form.watch("laterals_per_row")
  const spacing = form.watch("emitter_spacing_m")
  const emitterFlow = form.watch("emitter_flow_lph")
  const typedFlow = form.watch("typed_flow_m3h")
  const flowMeter = form.watch("flow_meter")
  const rowSpacing = block.plantings[0]?.row_spacing_m ?? null
  const previewBody =
    entry === "layout"
      ? {
          entry_mode: "layout" as const,
          row_spacing_m: rowSpacing,
          laterals_per_row: integerWire(laterals),
          emitter_spacing_m: decimalWire(spacing),
          emitter_flow_lph: decimalWire(emitterFlow),
          net_area_ha: block.net_area_ha,
        }
      : {
          entry_mode: "typed_flow" as const,
          typed_flow_m3h: decimalWire(typedFlow),
          typed_flow_basis: "block" as const,
          net_area_ha: block.net_area_ha,
        }
  const preview = useCalcPreview<IrrigationPreview>("/v1/calc/registry/irrigation", previewBody)
  const live: Record<string, string> = {}
  if (entry === "layout") {
    const lateralsMessage = liveIntegerMessage(laterals)
    if (lateralsMessage !== null) live.laterals_per_row = lateralsMessage
    const spacingMessage = liveDecimalMessage(spacing)
    if (spacingMessage !== null) live.emitter_spacing_m = spacingMessage
    const flowMessage = liveDecimalMessage(emitterFlow)
    if (flowMessage !== null) live.emitter_flow_lph = flowMessage
  } else {
    const typedMessage = liveDecimalMessage(typedFlow)
    if (typedMessage !== null) live.typed_flow_m3h = typedMessage
  }

  function message(name: keyof IrrigationValues): string | undefined {
    return form.formState.errors[name]?.message ?? live[name] ?? preview.fieldErrors[name]
  }

  async function persist(values: IrrigationValues, event: { nativeEvent?: Event }) {
    const layoutMode = values.entry_mode === "layout"
    onBusy(true)
    try {
      const saved = await write("PUT", `/v1/blocks/${block.id}/irrigation-layout`, {
        system: values.system,
        entry_mode: values.entry_mode,
        laterals_per_row: layoutMode ? integerWire(values.laterals_per_row) : null,
        emitter_spacing_m: layoutMode ? decimalWire(values.emitter_spacing_m) : null,
        emitter_flow_lph: layoutMode ? decimalWire(values.emitter_flow_lph) : null,
        typed_flow_m3h: layoutMode ? null : decimalWire(values.typed_flow_m3h),
        typed_flow_basis: layoutMode ? null : "block",
        flow_meter: values.flow_meter,
        ...reasonPayload(block, reason),
      })
      await finish(saved, submitAction(event), 5)
    } catch (error) {
      const outcome = reportErrors(error, (field, key) => {
        if (field === "reason") {
          onReasonError(key)
          return true
        }
        if (
          field === "laterals_per_row" ||
          field === "emitter_spacing_m" ||
          field === "emitter_flow_lph" ||
          field === "typed_flow_m3h" ||
          field === "system" ||
          field === "entry_mode"
        ) {
          form.setError(field, { message: key })
          return true
        }
        return false
      })
      if (outcome === "version") setFormError("blocks.errors.version")
      else if (outcome === "save" || outcome === "partial") setFormError("blocks.errors.save")
    } finally {
      onBusy(false)
    }
  }

  const flowPerHa = showServerNumber(preview.data?.q_ha_m3h ?? null, 2, lang)
  const blockFlow = showServerNumber(preview.data?.q_block_m3h ?? null, 2, lang)
  const rate = showServerNumber(preview.data?.rate_mm_h ?? null, 2, lang)
  const lines: ExplainerLine[] =
    entry === "layout"
      ? [
          {
            id: "row",
            formula: t("blocks.flowFormula.row"),
            label: t("blocks.flowFormula.rowLabel"),
            value: showServerNumber(preview.data?.row_m_per_ha ?? null, 0, lang),
          },
          {
            id: "lateral",
            formula: t("blocks.flowFormula.lateral"),
            label: t("blocks.flowFormula.lateralLabel"),
            value: showServerNumber(preview.data?.lateral_m_per_ha ?? null, 0, lang),
          },
          {
            id: "emitters",
            formula: t("blocks.flowFormula.emitters"),
            label: t("blocks.flowFormula.emittersLabel"),
            value: showServerNumber(preview.data?.emitters_per_ha ?? null, 0, lang),
          },
          {
            id: "qha",
            formula: t("blocks.flowFormula.qHa"),
            label: t("blocks.flowFormula.qHaLabel"),
            value: flowPerHa,
          },
          {
            id: "qblock",
            formula: t("blocks.flowFormula.qBlock"),
            label: t("blocks.flowFormula.qBlockLabel"),
            value: blockFlow,
          },
          {
            id: "rate",
            formula: t("blocks.flowFormula.rate"),
            label: t("blocks.flowFormula.rateLabel"),
            value: rate,
          },
        ]
      : [
          {
            id: "typed-ha",
            formula: t("blocks.flowFormula.typedHa"),
            label: t("blocks.flowFormula.typedHaLabel"),
            value: flowPerHa,
          },
          {
            id: "typed-rate",
            formula: t("blocks.flowFormula.typedRate"),
            label: t("blocks.flowFormula.typedRateLabel"),
            value: rate,
          },
        ]
  const rowMissing = entry === "layout" && rowSpacing === null
  const outsideError = preview.fieldErrors.row_spacing_m ?? preview.fieldErrors.net_area_ha

  return (
    <>
      <form
        id={IRRIGATION_FORM_ID}
        className={`${panelClass} flex flex-col gap-4`}
        noValidate
        onSubmit={(event) => {
          setFormError(null)
          const reasonOk = requireReason(block, reason, onReasonError)
          void form.handleSubmit((values) => {
            if (!reasonOk) return
            void persist(values, event)
          })(event)
        }}
      >
        <div>
          <SectionLabel>{t("blocks.system")}</SectionLabel>
          <div className="mt-2 flex flex-wrap gap-2">
            {SYSTEMS.map((item) => (
              <Chip
                key={item}
                selected={system === item}
                onClick={() => form.setValue("system", item)}
              >
                {t(`blocks.systems.${item}`)}
              </Chip>
            ))}
          </div>
          <FieldError message={message("system")} />
        </div>
        <div>
          <SectionLabel>{t("blocks.flow")}</SectionLabel>
          <div className="mt-2 flex flex-wrap gap-2">
            <Chip
              selected={entry === "layout"}
              onClick={() => form.setValue("entry_mode", "layout")}
            >
              {t("blocks.flowLayout")}
            </Chip>
            <Chip
              selected={entry === "typed_flow"}
              onClick={() => form.setValue("entry_mode", "typed_flow")}
            >
              {t("blocks.flowTyped")}
            </Chip>
          </div>
        </div>
        <div key={entry} className="grid grid-cols-3 gap-3">
          {entry === "layout" ? (
            <>
              <TextField
                label={t("blocks.lateralsPerRow")}
                placeholder={t("blocks.placeholderInt")}
                inputMode="numeric"
                error={message("laterals_per_row")}
                registration={form.register("laterals_per_row")}
              />
              <TextField
                label={t("blocks.emitterSpacing")}
                unit={t("blocks.unitM")}
                placeholder={t("blocks.placeholderDecimal")}
                inputMode="decimal"
                error={message("emitter_spacing_m")}
                registration={form.register("emitter_spacing_m")}
              />
              <TextField
                label={t("blocks.emitterFlow")}
                unit={t("blocks.unitLph")}
                placeholder={t("blocks.placeholderDecimal")}
                inputMode="decimal"
                error={message("emitter_flow_lph")}
                registration={form.register("emitter_flow_lph")}
              />
            </>
          ) : (
            <TextField
              label={t("blocks.blockFlow")}
              unit={t("blocks.unitFlow")}
              placeholder={t("blocks.placeholderDecimal")}
              inputMode="decimal"
              error={message("typed_flow_m3h")}
              registration={form.register("typed_flow_m3h")}
            />
          )}
        </div>
        <div className="grid grid-cols-3 gap-3">
          <CalculatedField
            label={t("blocks.flowPerHa")}
            value={flowPerHa}
            unit={t("blocks.unitFlow")}
          />
          <CalculatedField
            label={t("blocks.applicationRate")}
            value={rate}
            unit={t("blocks.unitMmh")}
          />
          <CalculatedField
            label={t("blocks.blockFlow")}
            value={blockFlow}
            unit={t("blocks.unitFlow")}
          />
        </div>
        {rowMissing ? <p className="text-[12px] text-mut">{t("blocks.rowSpacingNeeded")}</p> : null}
        <FieldError message={outsideError} />
        <section className="rounded-xl border border-line p-4">
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-[14px] font-bold">{t("blocks.flowMeterTitle")}</h2>
            <OptionalTag />
          </div>
          <p className="mt-1 text-[12px] text-mut">{t("blocks.flowMeterHelp")}</p>
          <Button
            type="button"
            variant={flowMeter ? "default" : "outline"}
            aria-pressed={flowMeter}
            className="mt-3 h-9 rounded-full px-4"
            onClick={() => form.setValue("flow_meter", !flowMeter)}
          >
            {flowMeter ? t("blocks.meterAdded") : t("blocks.addFlowMeter")}
          </Button>
        </section>
        {preview.error !== null ? <p className="text-[12px] text-red">{t(preview.error)}</p> : null}
        {formError !== null ? <p className="text-[12px] text-red">{t(formError)}</p> : null}
      </form>
      <ExplainerCard
        title={t("blocks.flowExplainerTitle")}
        lines={lines}
        footnote={t("blocks.flowFormula.footnote")}
      />
    </>
  )
}
