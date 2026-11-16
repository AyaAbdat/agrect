import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import type { BlockDetail } from "../blocks/types"
import { EnteredTag } from "../blocks/wizard/wizardUi"
import { decimalInput, isDecimal, wireDecimal } from "../weather/format"
import {
  FieldError,
  FieldLabel,
  LoadError,
  PageHeader,
  PageSkeleton,
  cardClass,
  fieldClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { soilErrorKey } from "./errors"
import { Help, NumberField } from "./fields"
import type { IrrigationSettings } from "./types"

const schema = z.object({
  efficiency: z.string().superRefine((value, ctx) => {
    if (value.trim() === "") {
      ctx.addIssue({ code: "custom", message: "soil.errors.efficiencyRequired" })
      return
    }
    if (!isDecimal(value)) ctx.addIssue({ code: "custom", message: "soil.errors.number" })
  }),
  kc: z.string().superRefine((value, ctx) => {
    if (value.trim() === "") {
      ctx.addIssue({ code: "custom", message: "soil.errors.kcRequired" })
      return
    }
    if (!isDecimal(value)) ctx.addIssue({ code: "custom", message: "soil.errors.number" })
  }),
  reason: z.string(),
})

type FormValues = z.infer<typeof schema>

const blank: FormValues = { efficiency: "", kc: "", reason: "" }

function valuesFrom(settings: IrrigationSettings): FormValues {
  return {
    efficiency: decimalInput(settings.efficiency),
    kc: decimalInput(settings.kc),
    reason: "",
  }
}

export function IrrigationSettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { blockId } = useParams()
  const [formError, setFormError] = useState<string | null>(null)
  const seeded = useRef(false)
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const settingsQuery = useQuery({
    queryKey: ["irrigation-settings", blockId],
    queryFn: () => apiGet<IrrigationSettings>(`/v1/blocks/${blockId}/irrigation-settings`),
    enabled: blockId !== undefined,
  })
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: blank,
  })
  const { reset, setError, setValue } = form

  useEffect(() => {
    if (seeded.current || settingsQuery.data === undefined) return
    seeded.current = true
    reset(valuesFrom(settingsQuery.data))
  }, [settingsQuery.data, reset])

  if (blockId === undefined) return null
  if (blockQuery.isPending || settingsQuery.isPending) return <PageSkeleton />
  if (
    blockQuery.isError ||
    settingsQuery.isError ||
    blockQuery.data === undefined ||
    settingsQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void blockQuery.refetch()
          void settingsQuery.refetch()
        }}
      />
    )
  }

  const version = settingsQuery.data.version

  async function onSubmit(values: FormValues) {
    setFormError(null)
    if (version !== null && values.reason.trim() === "") {
      setError("reason", { message: "soil.errors.reasonRequired" })
      return
    }
    const efficiency = wireDecimal(values.efficiency)
    const kc = wireDecimal(values.kc)
    if (efficiency === null || kc === null) return
    try {
      await apiSend<IrrigationSettings>(
        "PUT",
        `/v1/blocks/${blockId}/irrigation-settings`,
        {
          efficiency,
          kc,
          kc_source: "entered",
          ...(version === null ? {} : { reason: values.reason.trim() }),
        },
        version === null ? undefined : { "If-Match": String(version) },
      )
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 409 || error.status === 428) {
          setFormError("soil.errors.conflict")
          await queryClient.invalidateQueries({ queryKey: ["irrigation-settings", blockId] })
          return
        }
        const efficiencyCode = error.fields.efficiency
        const kcCode = error.fields.kc
        const reasonCode = error.fields.reason
        if (efficiencyCode !== undefined) setError("efficiency", { message: soilErrorKey(efficiencyCode) })
        if (kcCode !== undefined) setError("kc", { message: soilErrorKey(kcCode) })
        if (reasonCode !== undefined) setError("reason", { message: soilErrorKey(reasonCode) })
        if (efficiencyCode === undefined && kcCode === undefined && reasonCode === undefined) {
          setFormError("soil.errors.save")
        }
        return
      }
      setFormError("soil.errors.save")
      return
    }
    setValue("reason", "")
    await queryClient.invalidateQueries({ queryKey: ["irrigation-settings", blockId] })
    await queryClient.invalidateQueries({ queryKey: ["water-balance", blockId] })
    await queryClient.invalidateQueries({ queryKey: ["irrigation-today", blockId] })
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("soil.settingsCrumb")}
        title={t("soil.settingsTitle")}
        sub={blockQuery.data.name}
        actions={
          <Link
            to={`/blocks/${blockId}/soil-water`}
            className={`inline-flex items-center ${outlineBtn}`}
          >
            {t("soil.back")}
          </Link>
        }
      />
      <div className="grid grid-cols-[minmax(0,1fr)_280px] items-start gap-4">
        <form className={`${cardClass} flex flex-col gap-4`} onSubmit={form.handleSubmit(onSubmit)}>
          <NumberField
            label={t("soil.systemEfficiency")}
            tag="required"
            help={t("soil.efficiencyHelp")}
            placeholder="0.00"
            error={form.formState.errors.efficiency?.message}
            registration={form.register("efficiency")}
          />
          <div className="rounded-xl bg-mint px-4 py-3">
            <p className="text-[14px] font-semibold text-pri">{t("soil.applyBox")}</p>
            <p className="mt-1 text-[13px] text-pri">{t("soil.applyBoxHelp")}</p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="mb-1.5 flex items-start justify-between gap-2">
                <span className="text-[13px] font-semibold">{t("soil.stage")}</span>
                <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
                  {t("soil.phase2")}
                </span>
              </span>
              <select disabled className={`${fieldClass} text-mut`} defaultValue="">
                <option value="">{t("soil.chooseStage")}</option>
              </select>
              <Help>{t("soil.stageHelp")}</Help>
            </div>
            <label className="block min-w-0">
              <span className="mb-1.5 flex items-start justify-between gap-2">
                <span className="text-[13px] font-semibold">{t("soil.kc")}</span>
                <span className="flex items-center gap-1">
                  <EnteredTag />
                  <span className="shrink-0 rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[10px] font-semibold text-amb">
                    {t("weather.required")}
                  </span>
                </span>
              </span>
              <input
                className={fieldClass}
                inputMode="decimal"
                dir="ltr"
                lang="en"
                placeholder="0.00"
                autoComplete="off"
                aria-invalid={form.formState.errors.kc !== undefined}
                {...form.register("kc")}
              />
              <Help>{t("soil.kcHelp")}</Help>
              <FieldError message={form.formState.errors.kc?.message} />
            </label>
          </div>
          {version !== null ? (
            <label className="block">
              <FieldLabel label={t("soil.reason")} tag="required" />
              <input className={fieldClass} {...form.register("reason")} />
              <FieldError message={form.formState.errors.reason?.message} />
            </label>
          ) : null}
          <div className="flex items-center justify-end gap-3">
            <FieldError message={formError ?? undefined} />
            <Button type="submit" className={primaryBtn} disabled={form.formState.isSubmitting}>
              {t("soil.save")}
            </Button>
          </div>
        </form>
        <aside className={cardClass}>
          <h2 className="text-[15px] font-bold">{t("soil.howTitle")}</h2>
          <div className="mt-4 border-b border-line pb-3">
            <p className="text-[14px] font-semibold">{t("soil.howCrop")}</p>
            <p className="mt-1 text-[12px] text-mut">{t("soil.howCropHelp")}</p>
          </div>
          <div className="pt-3">
            <p className="text-[14px] font-semibold">{t("soil.howApply")}</p>
            <p className="mt-1 text-[12px] text-mut">{t("soil.howApplyHelp")}</p>
          </div>
        </aside>
      </div>
    </div>
  )
}
