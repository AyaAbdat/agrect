import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import { activeLang, localizedName, type BlockDetail } from "../blocks/types"
import { decimalInput, isDecimal, wireDecimal } from "../weather/format"
import {
  ChoiceChip,
  FieldError,
  FieldLabel,
  LoadError,
  PageHeader,
  PageSkeleton,
  SourceTag,
  cardClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { show, thetaPercent } from "./display"
import { soilErrorKey } from "./errors"
import { DateField, Help, NumberField } from "./fields"
import type { SoilProfile, SoilTexture } from "./types"

const schema = z
  .object({
    texture_mode: z.enum(["class", "percent"]),
    texture_class_id: z.string(),
    sand_pct: z.string(),
    silt_pct: z.string(),
    clay_pct: z.string(),
    root_depth_m: z.string(),
    dry_down_pct: z.string(),
    full_on: z.string(),
    organic_matter_pct: z.string(),
    compaction: z.enum(["", "loose", "normal", "compacted"]),
    infiltration_mode: z.enum(["texture", "ring_test"]),
    infiltration_mm_h: z.string(),
    reason: z.string(),
  })
  .superRefine((values, ctx) => {
    requireDecimal(values.root_depth_m, "root_depth_m", "soil.errors.rootRequired", ctx)
    requireDecimal(values.dry_down_pct, "dry_down_pct", "soil.errors.dryDownRequired", ctx)
    if (values.full_on.trim() === "") {
      ctx.addIssue({ code: "custom", path: ["full_on"], message: "soil.errors.fullOnRequired" })
    }
    if (values.texture_mode === "class" && values.texture_class_id === "") {
      ctx.addIssue({
        code: "custom",
        path: ["texture_class_id"],
        message: "soil.errors.textureRequired",
      })
    }
    if (values.texture_mode === "percent") {
      requireDecimal(values.sand_pct, "sand_pct", "soil.errors.percentRequired", ctx)
      requireDecimal(values.silt_pct, "silt_pct", "soil.errors.percentRequired", ctx)
      requireDecimal(values.clay_pct, "clay_pct", "soil.errors.percentRequired", ctx)
    }
    if (values.organic_matter_pct.trim() !== "" && !isDecimal(values.organic_matter_pct)) {
      ctx.addIssue({ code: "custom", path: ["organic_matter_pct"], message: "soil.errors.number" })
    }
    if (values.infiltration_mode === "ring_test") {
      requireDecimal(
        values.infiltration_mm_h,
        "infiltration_mm_h",
        "soil.errors.infiltrationRequired",
        ctx,
      )
    }
  })

type FormValues = z.infer<typeof schema>

const blank: FormValues = {
  texture_mode: "class",
  texture_class_id: "",
  sand_pct: "",
  silt_pct: "",
  clay_pct: "",
  root_depth_m: "",
  dry_down_pct: "",
  full_on: "",
  organic_matter_pct: "",
  compaction: "",
  infiltration_mode: "texture",
  infiltration_mm_h: "",
  reason: "",
}

const SERVER_FIELDS = [
  "root_depth_m",
  "dry_down_pct",
  "sand_pct",
  "silt_pct",
  "clay_pct",
  "texture_class_id",
  "reason",
] as const

function valuesFrom(soil: SoilProfile): FormValues {
  return {
    texture_mode: soil.texture_mode ?? "class",
    texture_class_id: soil.texture_class?.id ?? "",
    sand_pct: decimalInput(soil.sand_pct),
    silt_pct: decimalInput(soil.silt_pct),
    clay_pct: decimalInput(soil.clay_pct),
    root_depth_m: decimalInput(soil.root_depth_m),
    dry_down_pct: decimalInput(soil.dry_down_pct),
    full_on: soil.full_on ?? "",
    organic_matter_pct: decimalInput(soil.organic_matter_pct),
    compaction: soil.compaction ?? "",
    infiltration_mode: soil.infiltration_source === "ring_test" ? "ring_test" : "texture",
    infiltration_mm_h: decimalInput(soil.infiltration_mm_h),
    reason: "",
  }
}

export function SoilSetupPage() {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const { blockId } = useParams()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [formError, setFormError] = useState<string | null>(null)
  const seeded = useRef(false)
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const soilQuery = useQuery({
    queryKey: ["soil", blockId],
    queryFn: () => apiGet<SoilProfile>(`/v1/blocks/${blockId}/soil`),
    enabled: blockId !== undefined,
  })
  const texturesQuery = useQuery({
    queryKey: ["catalog", "soil-textures"],
    queryFn: () => apiGet<SoilTexture[]>("/v1/catalog/soil-textures"),
  })
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: blank,
  })
  const { reset, setError, setValue, watch } = form

  useEffect(() => {
    if (seeded.current || soilQuery.data === undefined) return
    seeded.current = true
    reset(valuesFrom(soilQuery.data))
  }, [soilQuery.data, reset])

  if (blockId === undefined) return null
  if (blockQuery.isPending || soilQuery.isPending || texturesQuery.isPending) return <PageSkeleton />
  if (
    blockQuery.isError ||
    soilQuery.isError ||
    texturesQuery.isError ||
    blockQuery.data === undefined ||
    soilQuery.data === undefined ||
    texturesQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void blockQuery.refetch()
          void soilQuery.refetch()
          void texturesQuery.refetch()
        }}
      />
    )
  }

  const soil = soilQuery.data
  const textures = texturesQuery.data
  const mode = watch("texture_mode")
  const classId = watch("texture_class_id")
  const compaction = watch("compaction")
  const infiltrationMode = watch("infiltration_mode")
  const version = soil.version

  async function onSubmit(values: FormValues) {
    setFormError(null)
    if (version !== null && values.reason.trim() === "") {
      setError("reason", { message: "soil.errors.reasonRequired" })
      return
    }
    const measured = values.infiltration_mode === "ring_test"
    const payload = {
      texture_mode: values.texture_mode,
      texture_class_id: values.texture_mode === "class" ? values.texture_class_id : null,
      sand_pct: values.texture_mode === "percent" ? wireDecimal(values.sand_pct) : null,
      silt_pct: values.texture_mode === "percent" ? wireDecimal(values.silt_pct) : null,
      clay_pct: values.texture_mode === "percent" ? wireDecimal(values.clay_pct) : null,
      root_depth_m: wireDecimal(values.root_depth_m),
      dry_down_pct: wireDecimal(values.dry_down_pct),
      full_on: values.full_on,
      organic_matter_pct: wireDecimal(values.organic_matter_pct),
      compaction: values.compaction === "" ? null : values.compaction,
      infiltration_mm_h: measured ? wireDecimal(values.infiltration_mm_h) : null,
      infiltration_source: values.infiltration_mode,
      ...(version === null ? {} : { reason: values.reason.trim() }),
    }
    try {
      await apiSend<SoilProfile>(
        "PUT",
        `/v1/blocks/${blockId}/soil`,
        payload,
        version === null ? undefined : { "If-Match": String(version) },
      )
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 409 || error.status === 428) {
          setFormError("soil.errors.conflict")
          await queryClient.invalidateQueries({ queryKey: ["soil", blockId] })
          return
        }
        let known = false
        for (const field of SERVER_FIELDS) {
          const code = error.fields[field]
          if (code === undefined) continue
          setError(field, { message: soilErrorKey(code) })
          known = true
        }
        if (!known) setFormError("soil.errors.save")
        return
      }
      setFormError("soil.errors.save")
      return
    }
    setValue("reason", "")
    await queryClient.invalidateQueries({ queryKey: ["soil", blockId] })
    await queryClient.invalidateQueries({ queryKey: ["water-balance", blockId] })
    await queryClient.invalidateQueries({ queryKey: ["irrigation-today", blockId] })
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("soil.setupCrumb")}
        title={t("soil.setupTitle")}
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
        <form className={cardClass} onSubmit={form.handleSubmit(onSubmit)}>
          <div className="mb-4 flex gap-4 border-b border-line">
            <Tab
              selected={mode === "class"}
              onClick={() => setValue("texture_mode", "class")}
              label={t("soil.textureTab")}
            />
            <Tab
              selected={mode === "percent"}
              onClick={() => setValue("texture_mode", "percent")}
              label={t("soil.percentTab")}
            />
          </div>
          {mode === "class" ? (
            <div>
              <FieldLabel label={t("soil.textureTab")} tag="required" />
              <div className="flex flex-wrap gap-2">
                {textures.map((texture) => (
                  <TextureChip
                    key={texture.id}
                    texture={texture}
                    lang={lang}
                    selected={classId === texture.id}
                    onClick={() => setValue("texture_class_id", texture.id, { shouldValidate: true })}
                  />
                ))}
              </div>
              <Help>{t("soil.textureHelp")}</Help>
              <FieldError message={form.formState.errors.texture_class_id?.message} />
            </div>
          ) : (
            <div>
              <div className="grid grid-cols-3 gap-3">
                <NumberField
                  label={t("soil.sand")}
                  unit="%"
                  tag="required"
                  error={form.formState.errors.sand_pct?.message}
                  registration={form.register("sand_pct")}
                />
                <NumberField
                  label={t("soil.silt")}
                  unit="%"
                  tag="required"
                  error={form.formState.errors.silt_pct?.message}
                  registration={form.register("silt_pct")}
                />
                <NumberField
                  label={t("soil.clay")}
                  unit="%"
                  tag="required"
                  error={form.formState.errors.clay_pct?.message}
                  registration={form.register("clay_pct")}
                />
              </div>
              <Help>{t("soil.percentNote")}</Help>
            </div>
          )}
          <div className="mt-4 grid grid-cols-3 gap-3">
            <NumberField
              label={t("soil.rootDepth")}
              unit={t("soil.unitM")}
              tag="required"
              help={t("soil.rootHelp")}
              placeholder="0.00"
              error={form.formState.errors.root_depth_m?.message}
              registration={form.register("root_depth_m")}
            />
            <NumberField
              label={t("soil.dryDown")}
              unit="%"
              tag="required"
              help={t("soil.dryHelp")}
              placeholder="0"
              error={form.formState.errors.dry_down_pct?.message}
              registration={form.register("dry_down_pct")}
            />
            <DateField
              label={t("soil.fullOn")}
              help={t("soil.fullHelp")}
              error={form.formState.errors.full_on?.message}
              registration={form.register("full_on")}
            />
          </div>
          <div className="mt-4 rounded-xl border border-line bg-[#F7F8F7] p-4">
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-[14px] font-bold">{t("soil.moreTitle")}</h2>
              <span className="rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
                {t("weather.optional")}
              </span>
            </div>
            <p className="mt-1 text-[12px] text-mut">{t("soil.moreHelp")}</p>
            <div className="mt-3 grid grid-cols-2 gap-4">
              <NumberField
                label={t("soil.organic")}
                unit="%"
                tag="optional"
                placeholder="0.0"
                error={form.formState.errors.organic_matter_pct?.message}
                registration={form.register("organic_matter_pct")}
              />
              <div>
                <FieldLabel label={t("soil.compaction")} tag="optional" />
                <div className="flex flex-wrap gap-2">
                  <ChoiceChip
                    selected={compaction === "loose"}
                    onClick={() => setValue("compaction", compaction === "loose" ? "" : "loose")}
                  >
                    {t("soil.loose")}
                  </ChoiceChip>
                  <ChoiceChip
                    selected={compaction === "normal"}
                    onClick={() => setValue("compaction", compaction === "normal" ? "" : "normal")}
                  >
                    {t("soil.normal")}
                  </ChoiceChip>
                  <ChoiceChip
                    selected={compaction === "compacted"}
                    onClick={() =>
                      setValue("compaction", compaction === "compacted" ? "" : "compacted")
                    }
                  >
                    {t("soil.compacted")}
                  </ChoiceChip>
                </div>
              </div>
              <div className="col-span-2">
                <FieldLabel label={t("soil.infiltration")} tag="optional" />
                <div className="flex flex-wrap gap-2">
                  <ChoiceChip
                    selected={infiltrationMode === "texture"}
                    onClick={() => setValue("infiltration_mode", "texture")}
                  >
                    {t("soil.fromTexture")}
                  </ChoiceChip>
                  <ChoiceChip
                    selected={infiltrationMode === "ring_test"}
                    onClick={() => setValue("infiltration_mode", "ring_test")}
                  >
                    {t("soil.measured")}
                  </ChoiceChip>
                </div>
                <div className="mt-3 max-w-xs">
                  {infiltrationMode === "ring_test" ? (
                    <NumberField
                      label={t("soil.rate")}
                      unit={t("soil.unitMmH")}
                      error={form.formState.errors.infiltration_mm_h?.message}
                      registration={form.register("infiltration_mm_h")}
                    />
                  ) : (
                    <div>
                      <FieldLabel label={t("soil.rate")} />
                      <div className="flex h-10 items-center justify-between rounded-[10px] border border-line bg-white px-3 text-mut">
                        <span>{t("common.missing")}</span>
                        <SourceTag kind="estimated" />
                      </div>
                    </div>
                  )}
                </div>
                <Help>{t("soil.rateHelp")}</Help>
              </div>
            </div>
          </div>
          {version !== null ? (
            <label className="mt-4 block">
              <FieldLabel label={t("soil.reason")} tag="required" />
              <input
                className="h-10 w-full rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px] outline-none focus:ring-2 focus:ring-mint"
                {...form.register("reason")}
              />
              <FieldError message={form.formState.errors.reason?.message} />
            </label>
          ) : null}
          <div className="mt-4 flex items-center justify-end gap-3">
            <FieldError message={formError ?? undefined} />
            <Button type="submit" className={primaryBtn} disabled={form.formState.isSubmitting}>
              {t("soil.save")}
            </Button>
          </div>
        </form>
        <aside className={cardClass}>
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-[15px] font-bold">{t("soil.holdsTitle")}</h2>
            <SourceTag kind="calculated" />
          </div>
          <HoldRow label={t("soil.fieldCapacity")} value={thetaPercent(soil.theta_fc, lang)} unit="%" />
          <HoldRow label={t("soil.wiltingPoint")} value={thetaPercent(soil.theta_wp, lang)} unit="%" />
          <HoldRow label={t("soil.rootHolds")} value={show(soil.taw_mm, lang)} unit="mm" />
          <HoldRow label={t("soil.raw")} value={show(soil.raw_mm, lang)} unit="mm" />
        </aside>
      </div>
    </div>
  )
}

function Tab({
  selected,
  onClick,
  label,
}: {
  selected: boolean
  onClick: () => void
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`-mb-px border-b-2 pb-2 text-[13px] font-semibold ${
        selected ? "border-pri text-pri" : "border-transparent text-mut"
      }`}
    >
      {label}
    </button>
  )
}

function TextureChip({
  texture,
  lang,
  selected,
  onClick,
}: {
  texture: SoilTexture
  lang: string
  selected: boolean
  onClick: () => void
}) {
  const { t } = useTranslation()
  const ready =
    texture.theta_fc_min !== null &&
    texture.theta_fc_max !== null &&
    texture.theta_wp_min !== null &&
    texture.theta_wp_max !== null
  const tip = ready
    ? t("soil.textureRange", {
        fcMin: thetaPercent(texture.theta_fc_min, lang),
        fcMax: thetaPercent(texture.theta_fc_max, lang),
        wpMin: thetaPercent(texture.theta_wp_min, lang),
        wpMax: thetaPercent(texture.theta_wp_max, lang),
        citation: texture.citation ?? "",
      })
    : t("soil.textureNoData")
  return (
    <span className="group relative">
      <button
        type="button"
        aria-pressed={selected}
        onClick={onClick}
        className={`inline-flex h-8 items-center rounded-full px-3 text-[12px] font-semibold ${
          selected ? "bg-pri text-white" : "border border-[#C7D2C9] bg-white text-text"
        }`}
      >
        {localizedName(texture.name, lang)}
      </button>
      <span
        role="tooltip"
        className="absolute start-0 top-full z-20 mt-1 hidden w-72 rounded-lg border border-line bg-white p-2 text-[11px] leading-snug text-text shadow group-hover:block group-focus-within:block"
      >
        {tip}
      </span>
    </span>
  )
}

function HoldRow({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="border-b border-line py-3 last:border-b-0">
      <p className="text-[12px] text-mut">{label}</p>
      <p className="mt-1 text-[18px] font-bold">
        {value} <span className="text-[12px] font-medium text-mut">{unit}</span>
      </p>
    </div>
  )
}

function requireDecimal(
  value: string,
  path: string,
  emptyKey: string,
  ctx: { addIssue: (issue: { code: "custom"; path: string[]; message: string }) => void },
) {
  if (value.trim() === "") {
    ctx.addIssue({ code: "custom", path: [path], message: emptyKey })
    return
  }
  if (!isDecimal(value)) {
    ctx.addIssue({ code: "custom", path: [path], message: "soil.errors.number" })
  }
}
