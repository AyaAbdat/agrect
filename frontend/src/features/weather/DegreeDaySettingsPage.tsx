import { zodResolver } from "@hookform/resolvers/zod"
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { useForm, type UseFormRegisterReturn } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { Link, useNavigate, useParams } from "react-router"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  activeLang,
  localizedName,
  type BlockDetail,
  type BlockListItem,
  type CatalogCrop,
} from "../blocks/types"
import { useAuth } from "../../app/auth"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { UNIT_TEMP_C } from "../../lib/units"
import { gddErrorKey } from "./errors"
import { asNumber, decimalInput, formatMediumDate, isDecimal, wireDecimal } from "./format"
import type { BlockGddSetting, GddMethod, GddSetting, GddSettingListItem } from "./types"
import {
  ChoiceChip,
  FieldError,
  FieldLabel,
  LoadError,
  PageHeader,
  PageSkeleton,
  cardClass,
  fieldClass,
  outlineBtn,
  primaryBtn,
} from "./ui"

const schema = z.object({
  crop_id: z.string().min(1, "weather.errors.cropRequired"),
  base_c: z.string().superRefine((value, ctx) => {
    if (value.trim() === "") {
      ctx.addIssue({ code: "custom", message: "weather.errors.baseRequired" })
      return
    }
    if (!isDecimal(value)) {
      ctx.addIssue({ code: "custom", message: "weather.errors.number" })
    }
  }),
  upper_c: z.string().refine((value) => value.trim() === "" || isDecimal(value), "weather.errors.number"),
  method: z.enum(["average", "single_sine"]),
  start_date: z.string().min(1, "weather.errors.startRequired"),
})

type FormValues = z.infer<typeof schema>

const blank: FormValues = {
  crop_id: "",
  base_c: "",
  upper_c: "",
  method: "average",
  start_date: "",
}

function valuesFor(cropId: string, rows: GddSettingListItem[]): FormValues {
  const found = rows.find((row) => row.crop_id === cropId)
  if (found === undefined) {
    return { ...blank, crop_id: cropId }
  }
  return {
    crop_id: found.crop_id,
    base_c: decimalInput(found.base_c),
    upper_c: decimalInput(found.upper_c),
    method: found.method,
    start_date: found.start_date ?? "",
  }
}

export function DegreeDaySettingsPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { blockId } = useParams()
  const { currentFarmId } = useAuth()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [formError, setFormError] = useState<string | null>(null)
  const [applies, setApplies] = useState<"all" | "chosen">("all")
  const [selected, setSelected] = useState<string[]>([])
  const seeded = useRef(false)
  const farmId = currentFarmId
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const cropsQuery = useQuery({
    queryKey: ["catalog", "crops"],
    queryFn: () => apiGet<CatalogCrop[]>("/v1/catalog/crops"),
  })
  const listQuery = useQuery({
    queryKey: ["gdd-settings", farmId],
    queryFn: () => apiGet<GddSettingListItem[]>(`/v1/farms/${farmId}/gdd-settings`),
    enabled: farmId !== null,
  })
  const farmBlocksQuery = useQuery({
    queryKey: ["blocks", farmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${farmId}/blocks`),
    enabled: farmId !== null,
  })
  const blockIds = (farmBlocksQuery.data ?? []).map((block) => block.id)
  const overrideQueries = useQueries({
    queries: blockIds.map((id) => ({
      queryKey: ["block-gdd-setting", id],
      queryFn: () => apiGet<BlockGddSetting>(`/v1/blocks/${id}/gdd-setting`),
    })),
  })
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: blank,
  })
  const { reset, setError, watch, setValue } = form
  const rows = listQuery.data

  useEffect(() => {
    if (seeded.current || blockQuery.data === undefined || rows === undefined) return
    seeded.current = true
    reset(valuesFor(blockQuery.data.crop?.id ?? "", rows))
  }, [blockQuery.data, rows, reset])

  if (farmId === null || blockId === undefined) return null
  const overridesPending = overrideQueries.some((query) => query.isPending)
  if (
    blockQuery.isPending ||
    cropsQuery.isPending ||
    listQuery.isPending ||
    farmBlocksQuery.isPending ||
    overridesPending
  ) {
    return <PageSkeleton />
  }
  if (
    blockQuery.isError ||
    cropsQuery.isError ||
    listQuery.isError ||
    farmBlocksQuery.isError ||
    overrideQueries.some((query) => query.isError) ||
    blockQuery.data === undefined ||
    cropsQuery.data === undefined ||
    farmBlocksQuery.data === undefined ||
    rows === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void blockQuery.refetch()
          void cropsQuery.refetch()
          void listQuery.refetch()
          void farmBlocksQuery.refetch()
          for (const query of overrideQueries) void query.refetch()
        }}
      />
    )
  }

  const crops = cropsQuery.data
  const farmBlocks = farmBlocksQuery.data
  const views = listedOverrides(farmBlocks, overrideQueries)
  const cropId = watch("crop_id")
  const method = watch("method")
  const items = Object.fromEntries(crops.map((crop) => [crop.id, localizedName(crop.name, lang)]))
  const cropBlocks = farmBlocks.filter(
    (block) => block.status !== "archived" && block.crop?.id === cropId,
  )
  const shownCrops = crops.filter(
    (crop) =>
      rows.some((row) => row.crop_id === crop.id) || views.some((view) => view.cropId === crop.id),
  )

  function loadCrop(nextId: string) {
    if (rows === undefined) return
    reset(valuesFor(nextId, rows))
    setApplies("all")
    setSelected([])
    setFormError(null)
  }

  function pickChosen() {
    setApplies("chosen")
    setSelected(views.filter((view) => view.cropId === cropId).map((view) => view.blockId))
  }

  function toggleBlock(id: string) {
    setFormError(null)
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  async function onSubmit(values: FormValues) {
    setFormError(null)
    const base = wireDecimal(values.base_c)
    if (base === null) return
    const payload = {
      base_c: base,
      upper_c: wireDecimal(values.upper_c),
      method: values.method,
      start_date: values.start_date,
    }
    if (applies === "chosen" && selected.length === 0) {
      setFormError("weather.errors.blocksRequired")
      return
    }
    try {
      if (applies === "chosen") {
        await Promise.all(
          selected.map((id) =>
            apiSend<BlockGddSetting>("PUT", `/v1/blocks/${id}/gdd-setting`, payload),
          ),
        )
      } else {
        await apiSend<GddSetting>("PUT", `/v1/farms/${farmId}/gdd-settings/${values.crop_id}`, payload)
      }
    } catch (error) {
      if (error instanceof ApiError) {
        const baseCode = error.fields.base_c
        const upperCode = error.fields.upper_c
        if (baseCode !== undefined) setError("base_c", { message: gddErrorKey(baseCode) })
        if (upperCode !== undefined) setError("upper_c", { message: gddErrorKey(upperCode) })
        if (baseCode === undefined && upperCode === undefined) setFormError("weather.errors.save")
        return
      }
      setFormError("weather.errors.save")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["gdd-settings", farmId] })
    await queryClient.invalidateQueries({ queryKey: ["gdd-setting", farmId] })
    await queryClient.invalidateQueries({ queryKey: ["block-gdd-setting"] })
    await queryClient.invalidateQueries({ queryKey: ["weather", farmId] })
    void navigate(`/blocks/${blockId}/weather/degree-days`)
  }

  async function removeOverride(id: string) {
    setFormError(null)
    try {
      await apiSend("DELETE", `/v1/blocks/${id}/gdd-setting`)
    } catch {
      setFormError("weather.errors.save")
      return
    }
    setSelected((current) => current.filter((item) => item !== id))
    await queryClient.invalidateQueries({ queryKey: ["block-gdd-setting", id] })
    await queryClient.invalidateQueries({ queryKey: ["weather", farmId] })
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("weather.settingsCrumb")}
        title={t("weather.settingsTitle")}
        sub={t("weather.settingsSub")}
        actions={
          <Link
            to={`/blocks/${blockId}/weather/degree-days`}
            className={`inline-flex items-center ${outlineBtn}`}
          >
            {t("weather.back")}
          </Link>
        }
      />
      <div className="grid grid-cols-[minmax(0,1fr)_280px] items-start gap-4">
        <form className={cardClass} onSubmit={form.handleSubmit(onSubmit)}>
          <div className="grid grid-cols-2 gap-4">
            <label className="block min-w-0">
              <FieldLabel label={t("weather.crop")} tag="required" />
              <Select
                value={cropId === "" ? null : cropId}
                items={items}
                onValueChange={(value) => {
                  if (value !== null) loadCrop(value)
                }}
              >
                <SelectTrigger className="h-10 w-full rounded-[10px] border-[#C7D2C9] text-[13px]">
                  <SelectValue placeholder={t("weather.chooseCrop")} />
                </SelectTrigger>
                <SelectContent>
                  {crops.map((crop) => (
                    <SelectItem key={crop.id} value={crop.id}>
                      {localizedName(crop.name, lang)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FieldError message={form.formState.errors.crop_id?.message} />
            </label>
            <div>
              <FieldLabel label={t("weather.appliesTo")} />
              <div className="flex flex-wrap gap-2">
                <ChoiceChip selected={applies === "all"} onClick={() => setApplies("all")}>
                  {t("weather.allBlocks")}
                </ChoiceChip>
                <ChoiceChip selected={applies === "chosen"} onClick={pickChosen}>
                  {t("weather.chosenBlocks")}
                </ChoiceChip>
              </div>
              {applies === "chosen" ? (
                cropBlocks.length === 0 ? (
                  <p className="mt-3 text-[13px] text-mut">{t("weather.noCropBlocks")}</p>
                ) : (
                  <div className="mt-3">
                    <FieldLabel label={t("weather.blocks")} tag="required" />
                    <ul className="flex flex-col gap-2">
                      {cropBlocks.map((block) => (
                        <li key={block.id}>
                          <label className="flex items-center gap-2 text-[13px]">
                            <input
                              type="checkbox"
                              className="size-4"
                              checked={selected.includes(block.id)}
                              onChange={() => toggleBlock(block.id)}
                            />
                            <span>{block.name}</span>
                          </label>
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              ) : null}
            </div>
            <NumberField
              label={t("weather.base")}
              unit={UNIT_TEMP_C}
              tag="required"
              error={form.formState.errors.base_c?.message}
              registration={form.register("base_c")}
            />
            <NumberField
              label={t("weather.upper")}
              unit={UNIT_TEMP_C}
              tag="optional"
              error={form.formState.errors.upper_c?.message}
              registration={form.register("upper_c")}
            />
            <div className="col-span-2">
              <FieldLabel label={t("weather.method")} tag="required" />
              <div className="flex flex-wrap gap-2">
                <ChoiceChip
                  selected={method === "average"}
                  onClick={() => setValue("method", "average")}
                >
                  {t("weather.simpleAverage")}
                </ChoiceChip>
                <ChoiceChip
                  selected={method === "single_sine"}
                  onClick={() => setValue("method", "single_sine")}
                >
                  {t("weather.singleSine")}
                </ChoiceChip>
              </div>
              <p className="mt-1 text-[12px] text-mut">{t("weather.methodHelp")}</p>
            </div>
            <div>
              <FieldLabel label={t("weather.startFrom")} tag="required" />
              <div className="flex flex-wrap gap-2">
                <ChoiceChip selected>{t("weather.aDate")}</ChoiceChip>
                <ChoiceChip selected={false} disabled badge={t("weather.phase2")}>
                  {t("weather.aStage")}
                </ChoiceChip>
              </div>
            </div>
            <label className="block">
              <FieldLabel label={t("weather.startDate")} tag="required" />
              <input type="date" className={fieldClass} {...form.register("start_date")} />
              <FieldError message={form.formState.errors.start_date?.message} />
            </label>
          </div>
          <div className="mt-4 flex items-center justify-end gap-3">
            <FieldError message={formError ?? undefined} />
            <Button type="submit" className={primaryBtn} disabled={form.formState.isSubmitting}>
              {t("weather.save")}
            </Button>
          </div>
        </form>
        <aside className={cardClass}>
          <h2 className="text-[15px] font-bold">{t("weather.cropsSetUp")}</h2>
          {shownCrops.length === 0 ? (
            <p className="mt-4 text-[13px] text-mut">{t("weather.cropsEmpty")}</p>
          ) : (
            <ul className="mt-3 flex flex-col gap-2">
              {shownCrops.map((crop) => {
                const row = rows.find((item) => item.crop_id === crop.id)
                const overs = views.filter((view) => view.cropId === crop.id)
                return (
                  <li
                    key={crop.id}
                    className={`rounded-xl border ${
                      crop.id === cropId ? "border-pri bg-mint" : "border-line"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => loadCrop(crop.id)}
                      className="w-full px-3 py-2 text-start"
                    >
                      <span className="block text-[13px] font-semibold">
                        {localizedName(crop.name, lang)}
                      </span>
                      {row !== undefined ? (
                        <span className="mt-0.5 block text-[12px] text-mut">
                          {t("weather.cropLine", {
                            base: formatNumber(asNumber(row.base_c), 1, lang),
                            method: methodLabel(row.method, t),
                            since:
                              row.start_date === null
                                ? t("common.missing")
                                : formatMediumDate(row.start_date, lang),
                          })}
                        </span>
                      ) : null}
                    </button>
                    {overs.length > 0 ? (
                      <ul className="flex flex-col gap-2 px-3 pb-3">
                        {overs.map((view) => (
                          <li key={view.blockId} className="flex items-start justify-between gap-2">
                            <span className="text-[12px] text-mut">
                              {t("weather.overrideLine", {
                                block: view.blockName,
                                base: formatNumber(asNumber(view.base_c), 1, lang),
                                method: methodLabel(view.method, t),
                              })}
                            </span>
                            <button
                              type="button"
                              className="shrink-0 text-[12px] font-semibold text-pri"
                              onClick={() => void removeOverride(view.blockId)}
                            >
                              {t("weather.removeOverride")}
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          )}
        </aside>
      </div>
    </div>
  )
}

function listedOverrides(
  blocks: BlockListItem[],
  rows: { data: BlockGddSetting | undefined }[],
): OverrideView[] {
  const found: OverrideView[] = []
  blocks.forEach((block, index) => {
    const setting = rows[index]?.data
    if (
      block.status === "archived" ||
      setting?.method == null ||
      setting.base_c === null ||
      block.crop === null
    ) {
      return
    }
    found.push({
      blockId: block.id,
      blockName: block.name,
      cropId: block.crop.id,
      base_c: setting.base_c,
      method: setting.method,
    })
  })
  return found
}

type OverrideView = {
  blockId: string
  blockName: string
  cropId: string
  base_c: string
  method: GddMethod
}

function methodLabel(method: GddMethod, t: (key: string) => string): string {
  return method === "single_sine" ? t("weather.singleSine") : t("weather.simpleAverage")
}

function NumberField({
  label,
  unit,
  tag,
  error,
  registration,
}: {
  label: string
  unit: string
  tag: "required" | "optional"
  error: string | undefined
  registration: UseFormRegisterReturn
}) {
  return (
    <label className="block min-w-0">
      <FieldLabel label={label} tag={tag} />
      <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] pe-3 focus-within:ring-2 focus-within:ring-mint">
        <input
          className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
          inputMode="decimal"
          autoComplete="off"
          aria-invalid={error !== undefined}
          {...registration}
        />
        <span className="text-mut">{unit}</span>
      </span>
      <FieldError message={error} />
    </label>
  )
}
