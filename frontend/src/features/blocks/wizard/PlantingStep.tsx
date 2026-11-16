import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery } from "@tanstack/react-query"
import { useLayoutEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { apiGet } from "../../../lib/api"
import { decimalInput } from "../errors"
import {
  activeLang,
  localizedName,
  type CatalogCrop,
  type CatalogVariety,
  type DensityInput,
} from "../types"
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
  submitYearMessage,
  yearPayload,
} from "./numbers"
import { PLANTING_FORM_ID } from "./steps"
import { useCalcPreview } from "./useCalcPreview"
import {
  CalculatedField,
  Chip,
  ExplainerCard,
  FieldError,
  FieldLabel,
  InlineError,
  SectionLabel,
  TextField,
  fieldClass,
  panelClass,
  showServerNumber,
  type ExplainerLine,
} from "./wizardUi"

const plantingSchema = z
  .object({
    crop_id: z.string().min(1, "blocks.errors.cropRequired"),
    variety: z.string(),
    variety_text: z.string(),
    rootstock: z.string(),
    planting_year: z.string(),
    density_input: z.enum(["spacing", "density", "count"]),
    row_spacing_m: z.string(),
    tree_spacing_m: z.string(),
    trees_per_ha: z.string(),
    trees_count: z.string(),
  })
  .superRefine((values, ctx) => {
    const yearNow = new Date().getFullYear()
    const checks: Array<[string, string | null]> = [
      ["planting_year", submitYearMessage(values.planting_year, yearNow)],
      ["row_spacing_m", submitDecimalMessage(values.row_spacing_m)],
    ]
    if (values.density_input === "spacing") {
      checks.push(["tree_spacing_m", submitDecimalMessage(values.tree_spacing_m)])
    }
    if (values.density_input === "density") {
      checks.push(["trees_per_ha", submitIntegerMessage(values.trees_per_ha)])
    }
    if (values.density_input === "count") {
      checks.push(["trees_count", submitIntegerMessage(values.trees_count)])
    }
    for (const [path, message] of checks) {
      if (message === null) continue
      ctx.addIssue({ code: "custom", message, path: [path] })
    }
  })

type PlantingValues = z.infer<typeof plantingSchema>

type PlantingPreview = {
  trees_per_ha: number | null
  tree_spacing_m: string | null
  trees_in_block: number | null
  source: "calculated"
}

function initialValues(block: StepSaveProps["block"]): PlantingValues {
  const planting = block.plantings[0]
  const variety =
    planting?.variety_id != null
      ? planting.variety_id
      : planting?.variety_text != null && planting.variety_text !== ""
        ? "other"
        : ""
  const mode = planting?.density_input ?? "spacing"
  return {
    crop_id: block.crop?.id ?? "",
    variety,
    variety_text: planting?.variety_text ?? "",
    rootstock: planting?.rootstock ?? "",
    planting_year: planting?.planting_year != null ? String(planting.planting_year) : "",
    density_input: mode,
    row_spacing_m: decimalInput(planting?.row_spacing_m ?? null),
    tree_spacing_m: decimalInput(planting?.tree_spacing_m ?? null),
    trees_per_ha: planting?.trees_per_ha != null ? String(planting.trees_per_ha) : "",
    trees_count: planting?.trees_count != null ? String(planting.trees_count) : "",
  }
}

function plantingBody(values: PlantingValues) {
  const mode = values.density_input
  return {
    variety_id: values.variety !== "" && values.variety !== "other" ? values.variety : null,
    variety_text:
      values.variety === "other" && values.variety_text.trim() !== ""
        ? values.variety_text.trim()
        : null,
    rootstock: values.rootstock.trim() === "" ? null : values.rootstock.trim(),
    planting_year: yearPayload(values.planting_year),
    density_input: mode,
    row_spacing_m: decimalWire(values.row_spacing_m),
    tree_spacing_m: mode === "spacing" ? decimalWire(values.tree_spacing_m) : null,
    trees_per_ha: mode === "density" ? integerWire(values.trees_per_ha) : null,
    trees_count: mode === "count" ? integerWire(values.trees_count) : null,
    area_ha: null,
  }
}

export function PlantingStep({ block, reason, onReasonError, onBusy }: StepSaveProps) {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { write, finish } = useBlockVersion(block)
  const [formError, setFormError] = useState<string | null>(null)
  const cropsQuery = useQuery({
    queryKey: ["catalog", "crops"],
    queryFn: () => apiGet<CatalogCrop[]>("/v1/catalog/crops"),
  })
  const form = useForm<PlantingValues>({
    resolver: zodResolver(plantingSchema),
    defaultValues: initialValues(block),
  })
  const cropId = form.watch("crop_id")
  const variety = form.watch("variety")
  const mode = form.watch("density_input")
  const row = form.watch("row_spacing_m")
  const tree = form.watch("tree_spacing_m")
  const perHa = form.watch("trees_per_ha")
  const count = form.watch("trees_count")
  const varietiesQuery = useQuery({
    queryKey: ["catalog", "varieties", cropId],
    queryFn: () => apiGet<CatalogVariety[]>(`/v1/catalog/crops/${cropId}/varieties`),
    enabled: cropId !== "",
  })
  const previewBody = {
    mode,
    row_spacing_m: decimalWire(row),
    tree_spacing_m: mode === "spacing" ? decimalWire(tree) : null,
    trees_per_ha: mode === "density" ? integerWire(perHa) : null,
    trees_count: mode === "count" ? integerWire(count) : null,
    net_area_ha: block.net_area_ha,
  }
  const preview = useCalcPreview<PlantingPreview>("/v1/calc/registry/planting", previewBody)

  useLayoutEffect(() => {
    onBusy(cropsQuery.isPending)
    return () => onBusy(false)
  }, [cropsQuery.isPending, onBusy])

  const live: Record<string, string> = {}
  const rowLive = liveDecimalMessage(row)
  if (rowLive !== null) live.row_spacing_m = rowLive
  if (mode === "spacing") {
    const message = liveDecimalMessage(tree)
    if (message !== null) live.tree_spacing_m = message
  }
  if (mode === "density") {
    const message = liveIntegerMessage(perHa)
    if (message !== null) live.trees_per_ha = message
  }
  if (mode === "count") {
    const message = liveIntegerMessage(count)
    if (message !== null) live.trees_count = message
  }

  function message(name: keyof PlantingValues): string | undefined {
    return form.formState.errors[name]?.message ?? live[name] ?? preview.fieldErrors[name]
  }

  function chooseCrop(id: string) {
    if (form.getValues("crop_id") === id) return
    form.setValue("crop_id", id, { shouldValidate: form.formState.isSubmitted })
    form.setValue("variety", "")
    form.setValue("variety_text", "")
    form.clearErrors("crop_id")
  }

  function chooseMode(next: DensityInput) {
    form.setValue("density_input", next)
  }

  async function persist(values: PlantingValues, event: { nativeEvent?: Event }) {
    const action = submitAction(event)
    onBusy(true)
    try {
      const patch: {
        crop_id: string
        training_system_id?: null
        training_other?: null
        reason?: string
      } = { crop_id: values.crop_id, ...reasonPayload(block, reason) }
      if (block.crop?.id !== values.crop_id) {
        patch.training_system_id = null
        patch.training_other = null
      }
      await write("PATCH", `/v1/blocks/${block.id}`, patch)
      const saved = await write("PUT", `/v1/blocks/${block.id}/plantings`, {
        plantings: [plantingBody(values)],
        ...reasonPayload(block, reason),
      })
      await finish(saved, action, 3)
    } catch (error) {
      const outcome = reportErrors(error, (field, key) => {
        if (field === "reason") {
          onReasonError(key)
          return true
        }
        if (field === "crop_id") {
          form.setError("crop_id", { message: key })
          return true
        }
        if (field === "plantings.0.variety_id") {
          form.setError("variety", { message: key })
          return true
        }
        if (
          field === "row_spacing_m" ||
          field === "tree_spacing_m" ||
          field === "trees_per_ha" ||
          field === "trees_count" ||
          field === "planting_year"
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

  const treesPerHa = showServerNumber(preview.data?.trees_per_ha ?? null, 0, lang)
  const treeSpacing = showServerNumber(preview.data?.tree_spacing_m ?? null, 2, lang)
  const treesInBlock = showServerNumber(preview.data?.trees_in_block ?? null, 0, lang)
  const lines: ExplainerLine[] =
    mode === "count"
      ? [
          {
            id: "count-density",
            formula: t("blocks.treeFormula.count1"),
            label: t("blocks.treeFormula.count1Label"),
            value: treesPerHa,
          },
          {
            id: "count-spacing",
            formula: t("blocks.treeFormula.count2"),
            label: t("blocks.treeFormula.count2Label"),
            value: treeSpacing,
          },
        ]
      : [
          {
            id: "spacing-density",
            formula: t("blocks.treeFormula.spacing1"),
            label: t("blocks.treeFormula.spacing1Label"),
            value: treesPerHa,
          },
          {
            id: "spacing-block",
            formula: t("blocks.treeFormula.spacing2"),
            label: t("blocks.treeFormula.spacing2Label"),
            value: treesInBlock,
          },
        ]
  const crops = cropsQuery.data ?? []
  const varieties = varietiesQuery.data ?? []
  const varietiesPending = cropId !== "" && varietiesQuery.isPending

  return (
    <>
      <form
        id={PLANTING_FORM_ID}
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
          <SectionLabel>{t("blocks.crop")}</SectionLabel>
          {cropsQuery.isPending ? (
            <p className="mt-2 text-[13px] text-mut">{t("common.loading")}</p>
          ) : null}
          {cropsQuery.isError ? (
            <InlineError onRetry={() => void cropsQuery.refetch()} />
          ) : null}
          {cropsQuery.isSuccess && crops.length === 0 ? (
            <p className="mt-2 text-[13px] text-mut">{t("blocks.emptyCrops")}</p>
          ) : null}
          {crops.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {crops.map((crop) => (
                <Chip
                  key={crop.id}
                  selected={cropId === crop.id}
                  onClick={() => chooseCrop(crop.id)}
                >
                  {localizedName(crop.name, lang)}
                </Chip>
              ))}
            </div>
          ) : null}
          <FieldError message={message("crop_id")} />
        </div>
        <section className="rounded-xl border border-line p-4">
          <h2 className="text-[15px] font-bold">{t("blocks.plantingCard", { n: 1 })}</h2>
          <div className="mt-3 grid grid-cols-3 gap-3">
            <div className="min-w-0">
              <FieldLabel label={t("blocks.variety")} />
              <select
                className={fieldClass}
                disabled={cropId === "" || varietiesPending}
                {...form.register("variety")}
              >
                <option value="">
                  {varietiesPending ? t("common.loading") : t("blocks.choose")}
                </option>
                {varieties.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
                <option value="other">{t("blocks.varietyOther")}</option>
              </select>
              <FieldError message={message("variety")} />
              {cropId !== "" && varietiesQuery.isError ? (
                <InlineError onRetry={() => void varietiesQuery.refetch()} />
              ) : null}
              {cropId !== "" && varietiesQuery.isSuccess && varieties.length === 0 ? (
                <p className="mt-1 text-[12px] text-mut">{t("blocks.emptyVarieties")}</p>
              ) : null}
              {variety === "other" ? (
                <input
                  className={`${fieldClass} mt-2`}
                  placeholder={t("blocks.varietyText")}
                  autoComplete="off"
                  {...form.register("variety_text")}
                />
              ) : null}
            </div>
            <TextField
              label={t("blocks.rootstock")}
              placeholder={t("blocks.rootstockPlaceholder")}
              inputMode="text"
              registration={form.register("rootstock")}
            />
            <TextField
              label={t("blocks.plantingYear")}
              placeholder={t("blocks.yearPlaceholder")}
              inputMode="numeric"
              error={message("planting_year")}
              registration={form.register("planting_year")}
            />
          </div>
          <div className="mt-4">
            <h3 className="text-[13px] font-semibold">{t("blocks.spacingTitle")}</h3>
            <p className="mt-1 text-[12px] text-mut">{t("blocks.spacingHelp")}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Chip selected={mode === "spacing"} onClick={() => chooseMode("spacing")}>
                {t("blocks.density.spacing")}
              </Chip>
              <Chip selected={mode === "density"} onClick={() => chooseMode("density")}>
                {t("blocks.density.density")}
              </Chip>
              <Chip selected={mode === "count"} onClick={() => chooseMode("count")}>
                {t("blocks.density.count")}
              </Chip>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-3">
              <TextField
                label={t("blocks.rowSpacing")}
                unit={t("blocks.unitM")}
                placeholder={t("blocks.placeholderDecimal")}
                inputMode="decimal"
                error={message("row_spacing_m")}
                registration={form.register("row_spacing_m")}
              />
              {mode === "spacing" ? (
                <TextField
                  label={t("blocks.treeSpacing")}
                  unit={t("blocks.unitM")}
                  placeholder={t("blocks.placeholderDecimal")}
                  inputMode="decimal"
                  error={message("tree_spacing_m")}
                  registration={form.register("tree_spacing_m")}
                />
              ) : null}
              {mode === "density" ? (
                <TextField
                  label={t("blocks.treesPerHa")}
                  unit={t("blocks.unitTreesHa")}
                  placeholder={t("blocks.placeholderInt")}
                  inputMode="numeric"
                  error={message("trees_per_ha")}
                  registration={form.register("trees_per_ha")}
                />
              ) : null}
              {mode === "count" ? (
                <TextField
                  label={t("blocks.density.count")}
                  unit={t("blocks.unitTrees")}
                  placeholder={t("blocks.placeholderInt")}
                  inputMode="numeric"
                  error={message("trees_count")}
                  registration={form.register("trees_count")}
                />
              ) : null}
              {mode === "density" ? (
                <CalculatedField
                  label={t("blocks.treeSpacing")}
                  value={treeSpacing}
                  unit={t("blocks.unitM")}
                />
              ) : (
                <CalculatedField
                  label={t("blocks.treesPerHa")}
                  value={treesPerHa}
                  unit={t("blocks.unitTreesHa")}
                />
              )}
            </div>
            <div className="mt-3">
              <CalculatedField
                label={t("blocks.treesInBlock")}
                value={treesInBlock}
                unit={t("blocks.unitTrees")}
                help={t("blocks.treesInBlockHelp")}
                error={preview.fieldErrors.net_area_ha}
              />
            </div>
          </div>
        </section>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" variant="outline" disabled className="h-9 rounded-full px-4">
            {t("blocks.addPlanting")}
          </Button>
          <p className="text-[12px] text-mut">{t("blocks.addPlantingHelp")}</p>
        </div>
        {preview.error !== null ? <p className="text-[12px] text-red">{t(preview.error)}</p> : null}
        {formError !== null ? <p className="text-[12px] text-red">{t(formError)}</p> : null}
      </form>
      <ExplainerCard title={t("blocks.treesExplainerTitle")} lines={lines} />
    </>
  )
}
