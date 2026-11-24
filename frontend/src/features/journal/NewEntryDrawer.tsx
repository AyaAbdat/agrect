import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { apiGet, apiSend } from "../../lib/api"
import { varietyName } from "../blocks/display"
import {
  activeLang,
  localizedName,
  type BlockDetail,
  type BlockValve,
  type CatalogVariety,
} from "../blocks/types"
import { farmToday, formatHour, isDecimal, wireDecimal } from "../weather/format"
import {
  ChoiceChip,
  FieldError,
  FieldLabel,
  SourceTag,
  fieldClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { isoWeekText, m3FromWaterLiters, totalOnAreaText, waterLitersFromM3 } from "./display"
import { journalErrorState } from "./errors"
import { ProductDrawer } from "./ProductDrawer"
import type {
  Operation,
  OperationProductPreview,
  OperationType,
  Product,
  ProductList,
  ProductRow,
  ProductUnit,
  RateBasis,
  StageAt,
} from "./types"

const FORM_ID = "journal-new-entry"

const ENTRY_TYPES: (OperationType | "irrigation" | "harvest")[] = [
  "fertigation",
  "crop_protection_spray",
  "foliar_application",
  "irrigation",
  "herbicide",
  "pruning",
  "shoot_cluster_thinning",
  "harvest",
]

const RATE_BASES: RateBasis[] = ["per_ha", "per_100l", "per_block"]
const UNITS: ProductUnit[] = ["kg", "g", "l", "ml", "unit"]

function emptyRow(unit: ProductUnit = "l"): ProductRow {
  return {
    key: crypto.randomUUID(),
    product_id: "",
    rate: "",
    rate_unit: unit,
    rate_basis: "per_ha",
    water_m3_ha: "",
  }
}

function rowsFromOperation(operation: Operation): ProductRow[] {
  if (operation.products.length === 0) return [emptyRow()]
  return operation.products.map((line) => ({
    key: line.id,
    product_id: line.product_id,
    rate: line.rate,
    rate_unit: line.rate_unit,
    rate_basis: line.rate_basis,
    water_m3_ha: m3FromWaterLiters(line.water_l_ha),
  }))
}

function bestPhi(products: Product[]): number | null {
  let best: number | null = null
  for (const product of products) {
    const phi = product.preharvest_interval_days
    if (phi === null) continue
    if (best === null || phi > best) best = phi
  }
  return best
}

function bestReentry(products: Product[]): number | null {
  let best: number | null = null
  for (const product of products) {
    const hours = product.reentry_h
    if (hours === null) continue
    if (best === null || hours > best) best = hours
  }
  return best
}

export function NewEntryDrawer({
  open,
  onOpenChange,
  farmId,
  block,
  blockId,
  timeZone,
  operation,
  initialType,
  onOpenIrrigation,
  onOpenHarvest,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  farmId: string
  block: BlockDetail
  blockId: string
  timeZone: string
  operation: Operation | null
  initialType: OperationType | null
  onOpenIrrigation: () => void
  onOpenHarvest: () => void
  onSaved: () => void
}) {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const queryClient = useQueryClient()
  const today = farmToday(timeZone)
  const valves = useMemo(
    () => [...block.valves].sort((left, right) => left.sort - right.sort),
    [block.valves],
  )
  const [type, setType] = useState<OperationType | "irrigation" | "harvest">(
    "crop_protection_spray",
  )
  const [selectedValves, setSelectedValves] = useState<string[]>([])
  const [date, setDate] = useState(today)
  const [target, setTarget] = useState("")
  const [workers, setWorkers] = useState("")
  const [notes, setNotes] = useState("")
  const [productRows, setProductRows] = useState<ProductRow[]>([emptyRow()])
  const [previews, setPreviews] = useState<Record<string, OperationProductPreview | null>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [productDrawerOpen, setProductDrawerOpen] = useState(false)
  const [areaHa, setAreaHa] = useState(block.net_area_ha)

  const productsQuery = useQuery({
    queryKey: ["products", farmId],
    queryFn: () => apiGet<ProductList>(`/v1/farms/${farmId}/products`),
    enabled: open && farmId !== "",
  })
  const stageQuery = useQuery({
    queryKey: ["stage-at", blockId, date],
    queryFn: () => apiGet<StageAt>(`/v1/blocks/${blockId}/stage-at?date=${date}`),
    enabled: open && date !== "",
  })
  const cropId = block.crop?.id ?? null
  const varietiesQuery = useQuery({
    queryKey: ["catalog", "varieties", cropId],
    queryFn: () => apiGet<CatalogVariety[]>(`/v1/catalog/crops/${cropId}/varieties`),
    enabled: open && cropId !== null,
  })
  const variety =
    varietyName(block.plantings[0], varietiesQuery.data ?? []) ?? t("common.missing")
  const products = productsQuery.data?.products ?? []
  const productById = new Map(products.map((row) => [row.id, row]))
  const selectedProducts = productRows
    .map((row) => productById.get(row.product_id))
    .flatMap((row) => (row === undefined ? [] : [row]))

  useEffect(() => {
    if (!open) return
    const defaultType = initialType ?? "crop_protection_spray"
    if (operation === null) {
      setType(defaultType)
      setDate(today)
      setSelectedValves(valves.map((valve) => valve.id))
      setTarget("")
      setWorkers("")
      setNotes("")
      setProductRows([emptyRow()])
      setAreaHa(block.net_area_ha)
    } else {
      setType(operation.type)
      setDate(operation.date)
      setSelectedValves(operation.valve_ids)
      setTarget(operation.target ?? "")
      setWorkers(operation.workers_count === null ? "" : String(operation.workers_count))
      setNotes(operation.notes ?? "")
      setProductRows(rowsFromOperation(operation))
      setAreaHa(operation.area_ha)
    }
    setErrors({})
    setFormError(null)
    setPreviews({})
  }, [open, operation, today, initialType, block.net_area_ha, valves])

  function pickType(next: OperationType | "irrigation" | "harvest") {
    if (next === "irrigation") {
      onOpenChange(false)
      onOpenIrrigation()
      return
    }
    if (next === "harvest") {
      onOpenChange(false)
      onOpenHarvest()
      return
    }
    setType(next)
  }

  const valveKey = [...selectedValves].sort().join(",")

  useEffect(() => {
    if (!open) return
    let cancelled = false
    const timers: number[] = []
    for (const row of productRows) {
      const rateWire = wireDecimal(row.rate)
      const water = waterLitersFromM3(row.water_m3_ha)
      const canPreview =
        rateWire !== null &&
        isDecimal(row.rate) &&
        Number(rateWire) > 0 &&
        (row.rate_basis !== "per_100l" || water !== null)
      if (!canPreview) {
        setPreviews((current) => ({ ...current, [row.key]: null }))
        continue
      }
      const handle = window.setTimeout(() => {
        void apiSend<OperationProductPreview>("POST", "/v1/calc/operation-product", {
          rate: rateWire,
          rate_basis: row.rate_basis,
          area_ha: areaHa,
          water_l_ha: row.rate_basis === "per_100l" ? water : null,
          rate_unit: row.rate_unit,
        })
          .then((body) => {
            if (!cancelled) {
              setPreviews((current) => ({ ...current, [row.key]: body }))
            }
          })
          .catch(() => {
            if (!cancelled) {
              setPreviews((current) => ({ ...current, [row.key]: null }))
            }
          })
      }, 300)
      timers.push(handle)
    }
    return () => {
      cancelled = true
      for (const handle of timers) window.clearTimeout(handle)
    }
  }, [open, productRows, areaHa, valveKey])

  function toggleValve(id: string) {
    setSelectedValves((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  function updateRow(key: string, patch: Partial<ProductRow>) {
    setProductRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  }

  async function onSubmit(submitEvent: FormEvent) {
    submitEvent.preventDefault()
    const next: Record<string, string> = {}
    if (date.trim() === "") next.date = "journal.errors.date"
    if (selectedValves.length === 0) next.valve_ids = "journal.errors.valve"
    const workerValue = workers.trim() === "" ? null : Number(workers)
    if (workers.trim() !== "" && (!/^\d+$/.test(workers.trim()) || (workerValue ?? 0) < 0)) {
      next.workers_count = "journal.errors.workers"
    }
    const lines = productRows.flatMap((row, index) => {
      if (row.product_id === "" && row.rate.trim() === "") return []
      if (row.product_id === "") {
        next[`products.${index}`] = "journal.errors.productMissing"
        return []
      }
      const rateWire = wireDecimal(row.rate)
      if (rateWire === null || !isDecimal(row.rate) || Number(rateWire) <= 0) {
        next[`products.${index}`] = "journal.errors.rate"
        return []
      }
      const water =
        row.rate_basis === "per_100l"
          ? waterLitersFromM3(row.water_m3_ha)
          : row.water_m3_ha.trim() === ""
            ? null
            : waterLitersFromM3(row.water_m3_ha)
      if (row.rate_basis === "per_100l" && water === null) {
        next[`products.${index}`] = "journal.errors.water"
        return []
      }
      return [
        {
          product_id: row.product_id,
          rate: rateWire,
          rate_unit: row.rate_unit,
          rate_basis: row.rate_basis,
          water_l_ha: water,
        },
      ]
    })
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0) return
    setSaving(true)
    const payload = {
      block_id: blockId,
      valve_ids: selectedValves,
      type: type as OperationType,
      date,
      target: target.trim() === "" ? null : target.trim(),
      workers_count: workerValue,
      notes: notes.trim() === "" ? null : notes.trim(),
      products: lines,
    }
    try {
      if (operation === null) {
        await apiSend("POST", `/v1/farms/${farmId}/operations`, payload)
      } else {
        await apiSend("PATCH", `/v1/operations/${operation.id}`, payload, {
          "If-Match": String(operation.version),
        })
      }
    } catch (error) {
      setSaving(false)
      const parsed = journalErrorState(error)
      setErrors(parsed.fields)
      setFormError(parsed.form)
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["journal", blockId] })
    await queryClient.invalidateQueries({ queryKey: ["operations", farmId, blockId] })
    setSaving(false)
    onSaved()
    onOpenChange(false)
  }

  const stage = stageQuery.data?.stage
  const phiDays = bestPhi(selectedProducts)
  const reentryH = bestReentry(selectedProducts)
  const reentryUntil =
    reentryH === null
      ? null
      : new Date(new Date(`${date}T12:00:00Z`).getTime() + reentryH * 3600000).toISOString()

  return (
    <>
      <Drawer
        open={open}
        onOpenChange={onOpenChange}
        crumb={t("nav.journal")}
        title={t(operation === null ? "journal.drawerNew" : "journal.drawerEdit")}
        footer={
          <div className="flex justify-end gap-2">
            <button type="button" className={outlineBtn} onClick={() => onOpenChange(false)}>
              {t("journal.cancel")}
            </button>
            <button type="submit" form={FORM_ID} className={primaryBtn} disabled={saving}>
              {t("journal.saveEntry")}
            </button>
          </div>
        }
      >
        <form
          id={FORM_ID}
          className="flex flex-col gap-4"
          onSubmit={(submitEvent) => void onSubmit(submitEvent)}
        >
          <div>
            <FieldLabel label={t("journal.operationType")} tag="required" />
            <div className="flex flex-wrap gap-2">
              {ENTRY_TYPES.map((item) => (
                <ChoiceChip
                  key={item}
                  selected={type === item}
                  onClick={() => pickType(item)}
                  disabled={item === "irrigation" || item === "harvest" ? false : false}
                >
                  {t(
                    item === "irrigation"
                      ? "journal.types.irrigation"
                      : item === "harvest"
                        ? "journal.types.harvest"
                        : item === "crop_protection_spray"
                          ? "journal.types.treatment"
                          : item === "herbicide"
                            ? "journal.types.weed"
                            : item === "shoot_cluster_thinning"
                              ? "journal.types.thinning"
                              : `journal.types.${item}`,
                  )}
                </ChoiceChip>
              ))}
              <ChoiceChip selected={false} disabled badge={t("settings.phase2")}>
                {t("journal.types.scouting")}
              </ChoiceChip>
            </div>
          </div>

          <label className="block">
            <FieldLabel label={t("journal.varietySubblock")} />
            <input className={`${fieldClass} bg-[#F7F8F7]`} readOnly value={variety} />
          </label>

          <div>
            <FieldLabel label={t("journal.valves")} tag="required" />
            <div className="flex flex-wrap gap-2">
              {valves.map((valve: BlockValve) => (
                <ChoiceChip
                  key={valve.id}
                  selected={selectedValves.includes(valve.id)}
                  onClick={() => toggleValve(valve.id)}
                >
                  {valve.name}
                </ChoiceChip>
              ))}
            </div>
            <FieldError message={errors.valve_ids} />
          </div>

          <label className="block">
            <FieldLabel label={t("journal.dateWeek")} tag="required" />
            <input
              type="date"
              dir="ltr"
              lang="en"
              className={fieldClass}
              value={date}
              aria-invalid={errors.date !== undefined}
              onChange={(change) => setDate(change.target.value)}
            />
            <p className="mt-1 text-[12px] text-mut" dir="ltr">
              {t("journal.isoWeek", { week: isoWeekText(date, lang) })}
            </p>
            <FieldError message={errors.date} />
          </label>

          <div className="flex items-center justify-between gap-2 rounded-xl bg-[#F7F8F7] px-3 py-2">
            <div>
              <p className="text-[12px] text-mut">{t("journal.growthStage")}</p>
              <p className="text-[13px] font-semibold">
                {stage === null || stage === undefined
                  ? t("common.missing")
                  : localizedName(stage.name, lang)}
              </p>
            </div>
            <SourceTag kind="calculated" />
          </div>

          <label className="block">
            <FieldLabel label={t("journal.target")} />
            <input
              className={fieldClass}
              placeholder={t("journal.targetPlaceholder")}
              value={target}
              onChange={(change) => setTarget(change.target.value)}
            />
          </label>

          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between gap-2">
              <FieldLabel label={t("journal.products")} />
              <button
                type="button"
                className={`${outlineBtn} h-8 px-3 text-[12px]`}
                onClick={() => setProductDrawerOpen(true)}
              >
                {t("journal.newProduct")}
              </button>
            </div>
            {productRows.map((row, index) => {
              const product = productById.get(row.product_id)
              const preview = previews[row.key]
              return (
                <div key={row.key} className="rounded-xl border border-line p-3">
                  <label className="block">
                    <FieldLabel label={t("journal.product")} />
                    <select
                      className={fieldClass}
                      value={row.product_id}
                      aria-invalid={errors[`products.${index}`] !== undefined}
                      onChange={(change) => {
                        const picked = productById.get(change.target.value)
                        updateRow(row.key, {
                          product_id: change.target.value,
                          rate_unit: picked?.unit ?? row.rate_unit,
                        })
                      }}
                    >
                      <option value="">{t("journal.chooseProduct")}</option>
                      {products.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                    {product !== undefined ? (
                      <p className="mt-1 text-[12px] text-mut">
                        {t("journal.stockUnit", { unit: t(`journal.units.${product.unit}`) })}
                      </p>
                    ) : null}
                    <FieldError message={errors[`products.${index}`]} />
                  </label>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <label className="block">
                      <FieldLabel label={t("journal.dose")} />
                      <input
                        className={fieldClass}
                        inputMode="decimal"
                        dir="ltr"
                        lang="en"
                        value={row.rate}
                        onChange={(change) => updateRow(row.key, { rate: change.target.value })}
                      />
                    </label>
                    <label className="block">
                      <FieldLabel label={t("journal.doseUnit")} />
                      <select
                        className={fieldClass}
                        value={row.rate_unit}
                        onChange={(change) =>
                          updateRow(row.key, { rate_unit: change.target.value as ProductUnit })
                        }
                      >
                        {UNITS.map((item) => (
                          <option key={item} value={item}>
                            {t(`journal.units.${item}`)}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {RATE_BASES.map((item) => (
                      <ChoiceChip
                        key={item}
                        selected={row.rate_basis === item}
                        onClick={() => updateRow(row.key, { rate_basis: item })}
                      >
                        {t(`journal.rateBasis.${item}`)}
                      </ChoiceChip>
                    ))}
                  </div>
                  <label className="mt-3 block">
                    <FieldLabel label={t("journal.waterM3Ha")} />
                    <input
                      className={fieldClass}
                      inputMode="decimal"
                      dir="ltr"
                      lang="en"
                      value={row.water_m3_ha}
                      onChange={(change) => updateRow(row.key, { water_m3_ha: change.target.value })}
                    />
                  </label>
                  {preview !== null && preview !== undefined ? (
                    <p className="mt-2 flex flex-wrap items-center gap-2 text-[12px]">
                      <span dir="ltr">
                        {totalOnAreaText(preview.total_qty, preview.total_unit, areaHa, lang, t)}
                      </span>
                      <SourceTag kind="calculated" />
                    </p>
                  ) : null}
                  {productRows.length > 1 ? (
                    <button
                      type="button"
                      className={`mt-2 ${outlineBtn} h-8 px-3 text-[12px]`}
                      onClick={() =>
                        setProductRows((current) => current.filter((item) => item.key !== row.key))
                      }
                    >
                      {t("journal.removeProduct")}
                    </button>
                  ) : null}
                </div>
              )
            })}
            <button
              type="button"
              className={`${outlineBtn} self-start`}
              onClick={() => setProductRows((current) => [...current, emptyRow()])}
            >
              {t("journal.addProduct")}
            </button>
          </div>

          <label className="block">
            <FieldLabel label={t("journal.sprayer")} />
            <input
              className={`${fieldClass} bg-[#F7F8F7]`}
              disabled
              value={t("journal.sprayerPhase2")}
            />
          </label>

          <label className="block">
            <FieldLabel label={t("journal.workers")} />
            <input
              className={fieldClass}
              inputMode="numeric"
              dir="ltr"
              lang="en"
              value={workers}
              aria-invalid={errors.workers_count !== undefined}
              onChange={(change) => setWorkers(change.target.value)}
            />
            <FieldError message={errors.workers_count} />
          </label>

          <label className="block">
            <FieldLabel label={t("journal.notes")} />
            <textarea
              className={`${fieldClass} min-h-20 py-2`}
              value={notes}
              onChange={(change) => setNotes(change.target.value)}
            />
          </label>

          <CardSafety phiDays={phiDays} reentryH={reentryH} reentryUntil={reentryUntil} timeZone={timeZone} />

          <div className="flex flex-wrap gap-2">
            <button type="button" className={outlineBtn} disabled>
              {t("journal.addPhoto")}
            </button>
            <button type="button" className={outlineBtn} disabled>
              {t("journal.voiceNote")}
            </button>
          </div>

          {formError !== null ? <FieldError message={formError} /> : null}
        </form>
      </Drawer>
      <ProductDrawer
        open={productDrawerOpen}
        onOpenChange={setProductDrawerOpen}
        farmId={farmId}
        product={null}
        onSaved={() => void productsQuery.refetch()}
      />
    </>
  )
}

function CardSafety({
  phiDays,
  reentryH,
  reentryUntil,
  timeZone,
}: {
  phiDays: number | null
  reentryH: number | null
  reentryUntil: string | null
  timeZone: string
}) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-line p-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-[12px] text-mut">{t("journal.phiTitle")}</p>
          <p className="text-[13px] font-semibold" dir="ltr">
            {phiDays === null
              ? t("journal.phiEmpty")
              : t("journal.phiDaysLine", { days: phiDays })}
          </p>
        </div>
        <SourceTag kind="calculated" />
      </div>
      {reentryH !== null ? (
        <p className="text-[12px] text-mut">
          {t("journal.reentryLine", {
            hours: reentryH,
            until:
              reentryUntil === null
                ? t("common.missing")
                : formatHour(reentryUntil, timeZone),
          })}
        </p>
      ) : null}
    </div>
  )
}
