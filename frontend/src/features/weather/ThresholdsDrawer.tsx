import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { Drawer } from "../../components/Drawer"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import { UNIT_TEMP_C, UNIT_VPD_KPA } from "../../lib/units"
import { thresholdErrorKey } from "./errors"
import { decimalInput, isDecimal, wireDecimal } from "./format"
import type { Thresholds } from "./types"
import { FieldError, FieldLabel, fieldClass, primaryBtn } from "./ui"

const schema = z.object({
  frost_c: z.string().refine((value) => value.trim() === "" || isDecimal(value), "weather.errors.number"),
  heat_c: z.string().refine((value) => value.trim() === "" || isDecimal(value), "weather.errors.number"),
  vpd_limit_kpa: z
    .string()
    .refine((value) => value.trim() === "" || isDecimal(value), "weather.errors.number"),
  chill_season_start: z.string(),
})

type FormValues = z.infer<typeof schema>

const empty: FormValues = {
  frost_c: "",
  heat_c: "",
  vpd_limit_kpa: "",
  chill_season_start: "",
}

function toForm(row: Thresholds): FormValues {
  return {
    frost_c: decimalInput(row.frost_c),
    heat_c: decimalInput(row.heat_c),
    vpd_limit_kpa: decimalInput(row.vpd_limit_kpa),
    chill_season_start: row.chill_season_start ?? "",
  }
}

export function ThresholdsDrawer({
  farmId,
  open,
  onOpenChange,
}: {
  farmId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [formError, setFormError] = useState<string | null>(null)
  const query = useQuery({
    queryKey: ["thresholds", farmId],
    queryFn: () => apiGet<Thresholds>(`/v1/farms/${farmId}/thresholds`),
  })
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: empty,
  })
  const { reset, setError } = form
  useEffect(() => {
    if (!open || query.data === undefined) return
    reset(toForm(query.data))
    setFormError(null)
  }, [open, query.data, reset])

  async function onSubmit(values: FormValues) {
    setFormError(null)
    try {
      await apiSend<Thresholds>("PUT", `/v1/farms/${farmId}/thresholds`, {
        frost_c: wireDecimal(values.frost_c),
        heat_c: wireDecimal(values.heat_c),
        vpd_limit_kpa: wireDecimal(values.vpd_limit_kpa),
        chill_season_start: values.chill_season_start === "" ? null : values.chill_season_start,
      })
    } catch (error) {
      if (error instanceof ApiError) {
        const frost = error.fields.frost_c
        const heat = error.fields.heat_c
        const vpd = error.fields.vpd_limit_kpa
        if (frost !== undefined) setError("frost_c", { message: thresholdErrorKey(frost) })
        if (heat !== undefined) setError("heat_c", { message: thresholdErrorKey(heat) })
        if (vpd !== undefined) setError("vpd_limit_kpa", { message: thresholdErrorKey(vpd) })
        if (frost === undefined && heat === undefined && vpd === undefined) {
          setFormError("weather.errors.save")
        }
        return
      }
      setFormError("weather.errors.save")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["thresholds", farmId] })
    await queryClient.invalidateQueries({ queryKey: ["weather", farmId] })
    onOpenChange(false)
  }

  const pending = form.formState.isSubmitting
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={t("weather.thresholdsCrumb")}
      title={t("weather.thresholdsTitle")}
      footer={
        <Button
          type="submit"
          form="thresholds-form"
          className={primaryBtn}
          disabled={pending}
        >
          {t("weather.save")}
        </Button>
      }
    >
      <form id="thresholds-form" className="flex flex-col gap-4" onSubmit={form.handleSubmit(onSubmit)}>
        <p className="text-[13px] text-mut">{t("weather.emptyHelp")}</p>
        <label className="block">
          <FieldLabel label={t("weather.frostThreshold")} tag="optional" />
          <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] pe-3 focus-within:ring-2 focus-within:ring-mint">
            <input className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none" inputMode="decimal" autoComplete="off" {...form.register("frost_c")} />
            <span className="text-mut">{UNIT_TEMP_C}</span>
          </span>
          <FieldError message={form.formState.errors.frost_c?.message} />
        </label>
        <label className="block">
          <FieldLabel label={t("weather.heatThreshold")} tag="optional" />
          <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] pe-3 focus-within:ring-2 focus-within:ring-mint">
            <input className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none" inputMode="decimal" autoComplete="off" {...form.register("heat_c")} />
            <span className="text-mut">{UNIT_TEMP_C}</span>
          </span>
          <FieldError message={form.formState.errors.heat_c?.message} />
        </label>
        <label className="block">
          <FieldLabel label={t("weather.vpdLimit")} tag="optional" />
          <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] pe-3 focus-within:ring-2 focus-within:ring-mint">
            <input className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none" inputMode="decimal" autoComplete="off" {...form.register("vpd_limit_kpa")} />
            <span className="text-mut">{UNIT_VPD_KPA}</span>
          </span>
          <FieldError message={form.formState.errors.vpd_limit_kpa?.message} />
        </label>
        <label className="block">
          <FieldLabel label={t("weather.chillStart")} tag="optional" />
          <input type="date" className={fieldClass} {...form.register("chill_season_start")} />
          <FieldError message={form.formState.errors.chill_season_start?.message} />
        </label>
        <FieldError message={formError ?? undefined} />
      </form>
    </Drawer>
  )
}
