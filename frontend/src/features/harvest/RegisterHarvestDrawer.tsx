import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useId, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { apiGet, apiSend } from "../../lib/api"
import type { OperationList } from "../journal/types"
import { varietyName } from "../blocks/display"
import {
  activeLang,
  type BlockDetail,
  type BlockListItem,
  type CatalogVariety,
} from "../blocks/types"
import { Help } from "../station/dialog"
import { decimalInput, farmToday, formatMediumDate, isDecimal, wireDecimal } from "../weather/format"
import {
  ChoiceChip,
  FieldError,
  FieldLabel,
  SourceTag,
  fieldClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import {
  areaText,
  basisNeedsCount,
  densityText,
  massText,
  needsUnitWeight,
  previewPreharvestWarning,
} from "./display"
import { harvestErrorState } from "./errors"
import type {
  GradeRow,
  HarvestBasis,
  HarvestEntry,
  HarvestFields,
  HarvestPreview,
  HarvestQuality,
  HarvestUnit,
  QualityField,
} from "./types"

const FORM_ID = "register-harvest"

function emptyGrade(): GradeRow {
  return { key: crypto.randomUUID(), grade: "", pct: "" }
}

function gradesFromQuality(quality: HarvestQuality | null): GradeRow[] {
  const grades = quality?.size_grade
  if (grades === null || grades === undefined) return [emptyGrade()]
  const rows = Object.entries(grades).map(([grade, pct]) => ({
    key: crypto.randomUUID(),
    grade,
    pct: String(pct),
  }))
  return rows.length === 0 ? [emptyGrade()] : rows
}

function qualityPayload(
  fields: QualityField[],
  values: Record<string, string>,
  grades: GradeRow[],
): HarvestQuality | null {
  const out: HarvestQuality = {
    brix: null,
    size_grade: null,
    waste_pct: null,
    moisture_pct: null,
    protein_pct: null,
    test_weight_kg_hl: null,
  }
  let any = false
  for (const field of fields) {
    if (field === "size_grade") {
      const map: Record<string, number> = {}
      for (const row of grades) {
        const name = row.grade.trim()
        const pct = wireDecimal(row.pct)
        if (name === "" && (pct === null || pct === "")) continue
        if (name === "" || pct === null || !isDecimal(row.pct)) continue
        map[name] = Number(pct)
        any = true
      }
      out.size_grade = Object.keys(map).length === 0 ? null : map
      continue
    }
    const raw = values[field] ?? ""
    const wire = wireDecimal(raw)
    if (wire === null || wire === "") continue
    out[field] = wire
    any = true
  }
  return any ? out : null
}

export function RegisterHarvestDrawer({
  open,
  onOpenChange,
  farmId,
  blocks,
  timeZone,
  entry,
  entryBlock,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  farmId: string
  blocks: BlockListItem[]
  timeZone: string
  entry: HarvestEntry | null
  entryBlock: BlockDetail | null
}) {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const queryClient = useQueryClient()
  const gradeId = useId()
  const today = farmToday(timeZone)
  const [blockId, setBlockId] = useState("")
  const [date, setDate] = useState(today)
  const [passNo, setPassNo] = useState("1")
  const [quantity, setQuantity] = useState("")
  const [unit, setUnit] = useState<HarvestUnit>("kg")
  const [unitWeight, setUnitWeight] = useState("")
  const [basis, setBasis] = useState<HarvestBasis>("block")
  const [valveId, setValveId] = useState("")
  const [basisCount, setBasisCount] = useState("")
  const [qualityValues, setQualityValues] = useState<Record<string, string>>({})
  const [grades, setGrades] = useState<GradeRow[]>([emptyGrade()])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [preview, setPreview] = useState<HarvestPreview | null>(null)
  const [saving, setSaving] = useState(false)

  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: open && blockId !== "",
  })
  const block = blockQuery.data ?? (entryBlock?.id === blockId ? entryBlock : undefined)
  const cropId = block?.crop?.id ?? null
  const fieldsQuery = useQuery({
    queryKey: ["harvest-fields", cropId],
    queryFn: () => apiGet<HarvestFields>(`/v1/catalog/crops/${cropId}/harvest-fields`),
    enabled: open && cropId !== null,
  })
  const varietiesQuery = useQuery({
    queryKey: ["catalog", "varieties", cropId],
    queryFn: () => apiGet<CatalogVariety[]>(`/v1/catalog/crops/${cropId}/varieties`),
    enabled: open && cropId !== null,
  })
  const qualityFields = fieldsQuery.data?.fields ?? []
  const variety =
    varietyName(block?.plantings[0], varietiesQuery.data ?? []) ?? t("common.missing")
  const operationsQuery = useQuery({
    queryKey: ["operations", farmId, blockId],
    queryFn: () => apiGet<OperationList>(`/v1/farms/${farmId}/operations?block_id=${blockId}`),
    enabled: open && farmId !== "" && blockId !== "",
  })
  const preharvestWarning =
    entry?.preharvest_warning ??
    (blockId !== "" && date !== ""
      ? previewPreharvestWarning(
          operationsQuery.data?.operations ?? [],
          date,
          basis === "valve" ? valveId : null,
        )
      : null)

  useEffect(() => {
    if (!open) return
    if (entry === null) {
      const first = blocks[0]
      setBlockId(first?.id ?? "")
      setDate(today)
      setPassNo("1")
      setQuantity("")
      setUnit("kg")
      setUnitWeight("")
      setBasis("block")
      setValveId("")
      setBasisCount("")
      setQualityValues({})
      setGrades([emptyGrade()])
    } else {
      setBlockId(entry.block_id)
      setDate(entry.date)
      setPassNo(String(entry.pass_no))
      setQuantity(decimalInput(entry.quantity))
      setUnit(entry.unit)
      setUnitWeight(decimalInput(entry.unit_weight_kg))
      setBasis(entry.basis)
      setValveId(entry.valve_id ?? "")
      setBasisCount(decimalInput(entry.basis_count))
      setQualityValues({
        brix: decimalInput(entry.quality?.brix),
        waste_pct: decimalInput(entry.quality?.waste_pct),
        moisture_pct: decimalInput(entry.quality?.moisture_pct),
        protein_pct: decimalInput(entry.quality?.protein_pct),
        test_weight_kg_hl: decimalInput(entry.quality?.test_weight_kg_hl),
      })
      setGrades(gradesFromQuality(entry.quality))
    }
    setErrors({})
    setFormError(null)
    setPreview(null)
  }, [open, entry, blocks, today])

  const qtyWire = wireDecimal(quantity)
  const weightWire = wireDecimal(unitWeight)
  const countWire = wireDecimal(basisCount)
  const canPreview =
    blockId !== "" &&
    qtyWire !== null &&
    isDecimal(quantity) &&
    Number(qtyWire) > 0 &&
    (!needsUnitWeight(unit) || (weightWire !== null && isDecimal(unitWeight) && Number(weightWire) > 0)) &&
    (basis !== "valve" || valveId !== "") &&
    (!basisNeedsCount(basis) || (countWire !== null && isDecimal(basisCount) && Number(countWire) > 0))

  useEffect(() => {
    if (!open || !canPreview) {
      setPreview(null)
      return
    }
    let cancelled = false
    const handle = window.setTimeout(() => {
      void apiSend<HarvestPreview>("POST", "/v1/calc/harvest", {
        block_id: blockId,
        quantity: qtyWire,
        unit,
        unit_weight_kg: needsUnitWeight(unit) ? weightWire : null,
        basis,
        valve_id: basis === "valve" ? valveId : null,
        basis_count: basisNeedsCount(basis) ? countWire : null,
      })
        .then((body) => {
          if (!cancelled) setPreview(body)
        })
        .catch(() => {
          if (!cancelled) setPreview(null)
        })
    }, 300)
    return () => {
      cancelled = true
      window.clearTimeout(handle)
    }
  }, [open, canPreview, blockId, qtyWire, unit, weightWire, basis, valveId, countWire])

  async function onSubmit(submitEvent: FormEvent) {
    submitEvent.preventDefault()
    const next: Record<string, string> = {}
    if (blockId === "") next.block_id = "harvest.errors.blockRequired"
    if (date.trim() === "") next.date = "harvest.errors.dateRequired"
    const pass = Number(passNo)
    if (!/^\d+$/.test(passNo.trim()) || pass < 1) next.pass_no = "harvest.errors.passRequired"
    if (qtyWire === null || !isDecimal(quantity) || Number(qtyWire) <= 0) {
      next.quantity = "harvest.errors.quantityPositive"
    }
    if (needsUnitWeight(unit) && (weightWire === null || !isDecimal(unitWeight) || Number(weightWire) <= 0)) {
      next.unit_weight_kg = "harvest.errors.unitWeight"
    }
    if (basis === "valve" && valveId === "") next.valve_id = "harvest.errors.valveRequired"
    if (basisNeedsCount(basis) && (countWire === null || !isDecimal(basisCount) || Number(countWire) <= 0)) {
      next.basis_count =
        basis === "rows" ? "harvest.errors.rowsRequired" : "harvest.errors.treesRequired"
    }
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0) return
    setSaving(true)
    const payload = {
      date,
      pass_no: pass,
      quantity: qtyWire,
      unit,
      unit_weight_kg: needsUnitWeight(unit) ? weightWire : null,
      basis,
      valve_id: basis === "valve" ? valveId : null,
      basis_count: basisNeedsCount(basis) ? countWire : null,
      quality: qualityPayload(qualityFields, qualityValues, grades),
    }
    try {
      if (entry === null) {
        await apiSend("POST", `/v1/blocks/${blockId}/harvest`, payload)
      } else {
        await apiSend("PATCH", `/v1/blocks/${blockId}/harvest/${entry.id}`, payload, {
          "If-Match": String(entry.version),
        })
      }
    } catch (error) {
      setSaving(false)
      const parsed = harvestErrorState(error)
      setErrors(parsed.fields)
      setFormError(parsed.form)
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["harvest"] })
    await queryClient.invalidateQueries({ queryKey: ["harvest-summary", farmId] })
    setSaving(false)
    onOpenChange(false)
  }

  const units: HarvestUnit[] = ["kg", "t", "crate", "bin"]
  const bases: HarvestBasis[] = ["block", "valve", "rows", "trees"]
  const valves = [...(block?.valves ?? [])].sort((left, right) => left.sort - right.sort)
  const rowsTotal = block?.rows_total

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={t("nav.harvest")}
      title={t(entry === null ? "harvest.drawerTitle" : "harvest.drawerEditTitle")}
      footer={
        <div className="flex justify-end gap-2">
          <button type="button" className={outlineBtn} onClick={() => onOpenChange(false)}>
            {t("harvest.cancel")}
          </button>
          <button type="submit" form={FORM_ID} className={primaryBtn} disabled={saving}>
            {t("harvest.save")}
          </button>
        </div>
      }
    >
      <form
        id={FORM_ID}
        className="flex flex-col gap-4"
        onSubmit={(submitEvent) => void onSubmit(submitEvent)}
      >
        <label className="block">
          <FieldLabel label={t("harvest.block")} tag="required" />
          <select
            className={`${fieldClass} disabled:bg-[#F7F8F7]`}
            value={blockId}
            disabled={entry !== null}
            aria-invalid={errors.block_id !== undefined}
            onChange={(change) => {
              setBlockId(change.target.value)
              setValveId("")
              setBasisCount("")
            }}
          >
            {blocks.length === 0 ? (
              <option value="">{t("harvest.noBlocks")}</option>
            ) : (
              blocks.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))
            )}
          </select>
          {block !== undefined ? (
            <p className="mt-1 text-[12px] text-mut">
              {t("harvest.blockMeta", {
                variety,
                area: areaText(block.net_area_ha, lang),
              })}
            </p>
          ) : null}
          <FieldError message={errors.block_id} />
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <FieldLabel label={t("harvest.date")} tag="required" />
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
            <FieldLabel label={t("harvest.passNo")} tag="required" />
            <input
              className={fieldClass}
              inputMode="numeric"
              dir="ltr"
              lang="en"
              value={passNo}
              aria-invalid={errors.pass_no !== undefined}
              onChange={(change) => setPassNo(change.target.value)}
            />
            <FieldError message={errors.pass_no} />
          </label>
        </div>

        <div>
          <FieldLabel label={t("harvest.quantity")} tag="required" />
          <div className="flex flex-col gap-2">
            <input
              className={fieldClass}
              inputMode="decimal"
              dir="ltr"
              lang="en"
              value={quantity}
              aria-invalid={errors.quantity !== undefined}
              onChange={(change) => setQuantity(change.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              {units.map((item) => (
                <ChoiceChip key={item} selected={unit === item} onClick={() => setUnit(item)}>
                  {t(`harvest.unit.${item}`)}
                </ChoiceChip>
              ))}
            </div>
          </div>
          <FieldError message={errors.quantity} />
        </div>

        {needsUnitWeight(unit) ? (
          <label className="block">
            <FieldLabel label={t("harvest.unitWeight")} tag="required" />
            <input
              className={fieldClass}
              inputMode="decimal"
              dir="ltr"
              lang="en"
              value={unitWeight}
              aria-invalid={errors.unit_weight_kg !== undefined}
              onChange={(change) => setUnitWeight(change.target.value)}
            />
            <Help>{t("harvest.unitWeightHelp")}</Help>
            <FieldError message={errors.unit_weight_kg} />
          </label>
        ) : null}

        <div>
          <FieldLabel label={t("harvest.basisLabel")} tag="required" />
          <div className="flex flex-wrap gap-2">
            {bases.map((item) => (
              <ChoiceChip
                key={item}
                selected={basis === item}
                onClick={() => {
                  setBasis(item)
                  if (item !== "valve") setValveId("")
                  if (!basisNeedsCount(item)) setBasisCount("")
                }}
              >
                {t(`harvest.basis.${item}`)}
              </ChoiceChip>
            ))}
          </div>
          <FieldError message={errors.basis} />
        </div>

        {basis === "valve" ? (
          <label className="block">
            <FieldLabel label={t("harvest.valve")} tag="required" />
            <select
              className={fieldClass}
              value={valveId}
              aria-invalid={errors.valve_id !== undefined}
              onChange={(change) => setValveId(change.target.value)}
            >
              <option value="">{t("harvest.chooseValve")}</option>
              {valves.map((valve) => (
                <option key={valve.id} value={valve.id}>
                  {valve.name}
                </option>
              ))}
            </select>
            <FieldError message={errors.valve_id} />
          </label>
        ) : null}

        {basis === "rows" ? (
          <label className="block">
            <FieldLabel label={t("harvest.rowsPicked")} tag="required" />
            <input
              className={fieldClass}
              inputMode="decimal"
              dir="ltr"
              lang="en"
              value={basisCount}
              aria-invalid={errors.basis_count !== undefined}
              onChange={(change) => setBasisCount(change.target.value)}
            />
            {rowsTotal !== null && rowsTotal !== undefined ? (
              <Help>{t("harvest.rowsOf", { total: String(rowsTotal) })}</Help>
            ) : null}
            <FieldError message={errors.basis_count} />
          </label>
        ) : null}

        {basis === "trees" ? (
          <label className="block">
            <FieldLabel label={t("harvest.treesPicked")} tag="required" />
            <input
              className={fieldClass}
              inputMode="decimal"
              dir="ltr"
              lang="en"
              value={basisCount}
              aria-invalid={errors.basis_count !== undefined}
              onChange={(change) => setBasisCount(change.target.value)}
            />
            <FieldError message={errors.basis_count} />
          </label>
        ) : null}

        <section className="rounded-xl bg-[#F7F8F7] p-3">
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-[15px] font-bold">{t("harvest.previewTitle")}</h2>
            <SourceTag kind="calculated" />
          </div>
          <p className="mt-2 text-[13px]" dir="ltr">
            {preview === null
              ? t("common.missing")
              : t("harvest.previewLine", {
                  kg: massText(preview.kg, lang),
                  area: areaText(preview.area_ha, lang),
                  density: densityText(preview.kg_ha, lang),
                })}
          </p>
        </section>

        {qualityFields.length > 0 ? (
          <section className="flex flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-[15px] font-bold">{t("harvest.qualityTitle")}</h2>
              <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
                {t("weather.optional")}
              </span>
            </div>
            {qualityFields.includes("brix") ? (
              <label className="block">
                <FieldLabel label={t("harvest.quality.brix")} />
                <input
                  className={fieldClass}
                  inputMode="decimal"
                  dir="ltr"
                  lang="en"
                  value={qualityValues.brix ?? ""}
                  aria-invalid={errors.brix !== undefined}
                  onChange={(change) =>
                    setQualityValues((current) => ({ ...current, brix: change.target.value }))
                  }
                />
                <FieldError message={errors.brix} />
              </label>
            ) : null}
            {qualityFields.includes("size_grade") ? (
              <div>
                <FieldLabel label={t("harvest.quality.sizeGrade")} />
                <div className="flex flex-col gap-2">
                  {grades.map((row, index) => (
                    <div key={row.key} className="grid grid-cols-[1fr_90px_auto] gap-2">
                      <input
                        className={fieldClass}
                        placeholder={t("harvest.quality.gradeName")}
                        value={row.grade}
                        aria-labelledby={`${gradeId}-grade`}
                        onChange={(change) =>
                          setGrades((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, grade: change.target.value } : item,
                            ),
                          )
                        }
                      />
                      <input
                        className={fieldClass}
                        inputMode="decimal"
                        dir="ltr"
                        lang="en"
                        placeholder="%"
                        value={row.pct}
                        onChange={(change) =>
                          setGrades((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, pct: change.target.value } : item,
                            ),
                          )
                        }
                      />
                      <button
                        type="button"
                        className={outlineBtn}
                        onClick={() =>
                          setGrades((current) =>
                            current.length <= 1
                              ? [emptyGrade()]
                              : current.filter((_, itemIndex) => itemIndex !== index),
                          )
                        }
                      >
                        {t("harvest.removeGrade")}
                      </button>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  className={`mt-2 ${outlineBtn}`}
                  onClick={() => setGrades((current) => [...current, emptyGrade()])}
                >
                  {t("harvest.addGrade")}
                </button>
                <FieldError message={errors.size_grade} />
              </div>
            ) : null}
            {qualityFields.includes("waste_pct") ? (
              <label className="block">
                <FieldLabel label={t("harvest.quality.waste")} />
                <input
                  className={fieldClass}
                  inputMode="decimal"
                  dir="ltr"
                  lang="en"
                  value={qualityValues.waste_pct ?? ""}
                  aria-invalid={errors.waste_pct !== undefined}
                  onChange={(change) =>
                    setQualityValues((current) => ({
                      ...current,
                      waste_pct: change.target.value,
                    }))
                  }
                />
                <FieldError message={errors.waste_pct} />
              </label>
            ) : null}
            {qualityFields.includes("moisture_pct") ? (
              <label className="block">
                <FieldLabel label={t("harvest.quality.moisture")} />
                <input
                  className={fieldClass}
                  inputMode="decimal"
                  dir="ltr"
                  lang="en"
                  value={qualityValues.moisture_pct ?? ""}
                  aria-invalid={errors.moisture_pct !== undefined}
                  onChange={(change) =>
                    setQualityValues((current) => ({
                      ...current,
                      moisture_pct: change.target.value,
                    }))
                  }
                />
                <FieldError message={errors.moisture_pct} />
              </label>
            ) : null}
            {qualityFields.includes("protein_pct") ? (
              <label className="block">
                <FieldLabel label={t("harvest.quality.protein")} />
                <input
                  className={fieldClass}
                  inputMode="decimal"
                  dir="ltr"
                  lang="en"
                  value={qualityValues.protein_pct ?? ""}
                  aria-invalid={errors.protein_pct !== undefined}
                  onChange={(change) =>
                    setQualityValues((current) => ({
                      ...current,
                      protein_pct: change.target.value,
                    }))
                  }
                />
                <FieldError message={errors.protein_pct} />
              </label>
            ) : null}
            {qualityFields.includes("test_weight_kg_hl") ? (
              <label className="block">
                <FieldLabel label={t("harvest.quality.testWeight")} />
                <input
                  className={fieldClass}
                  inputMode="decimal"
                  dir="ltr"
                  lang="en"
                  value={qualityValues.test_weight_kg_hl ?? ""}
                  aria-invalid={errors.test_weight_kg_hl !== undefined}
                  onChange={(change) =>
                    setQualityValues((current) => ({
                      ...current,
                      test_weight_kg_hl: change.target.value,
                    }))
                  }
                />
                <FieldError message={errors.test_weight_kg_hl} />
              </label>
            ) : null}
          </section>
        ) : null}

        {preharvestWarning !== null ? (
          <div className="rounded-xl bg-[#FEF3C7] px-4 py-3 text-[13px] text-amb">
            <p className="font-semibold">{t("harvest.preharvestTitle")}</p>
            <p>
              {t("harvest.preharvestWarning", {
                product: preharvestWarning.product,
                sprayDate: formatMediumDate(preharvestWarning.spray_date, lang),
                daysSince: preharvestWarning.days_since,
                daysNeeded: preharvestWarning.days_needed,
              })}
            </p>
          </div>
        ) : (
          <p className="text-[12px] text-mut">{t("harvest.preharvestNote")}</p>
        )}
        {formError !== null ? <FieldError message={formError} /> : null}
      </form>
    </Drawer>
  )
}
