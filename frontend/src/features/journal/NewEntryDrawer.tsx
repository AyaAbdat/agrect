import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { apiGet, apiSend } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { varietyName } from "../blocks/display"
import {
  activeLang,
  localizedName,
  type BlockDetail,
  type BlockValve,
  type CatalogVariety,
} from "../blocks/types"
import type { MachineList, WorkerList } from "../team/types"
import { asNumber, farmToday, formatHour, isDecimal, wireDecimal } from "../weather/format"
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
  isoWeekText,
  m3FromWaterLiters,
  totalOnAreaText,
  warningKey,
  warningText,
  waterLitersFromM3,
} from "./display"
import { journalErrorState } from "./errors"
import { ProductDrawer } from "./ProductDrawer"
import type {
  MachineRow,
  Operation,
  OperationLabour,
  OperationMachine,
  OperationProductPreview,
  OperationType,
  OperationWarning,
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

function emptyMachineRow(): MachineRow {
  return {
    key: crypto.randomUUID(),
    machine_id: "",
    hours: "",
    fuel_l: "",
  }
}

function machineRowsFromOperation(operation: Operation): MachineRow[] {
  if (operation.machines.length === 0) return [emptyMachineRow()]
  return operation.machines.map((line) => ({
    key: line.id,
    machine_id: line.id,
    hours: line.hours,
    fuel_l: line.fuel_l ?? "",
  }))
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
  const [labourMode, setLabourMode] = useState<"workers" | "headcount">("workers")
  const [selectedWorkerIds, setSelectedWorkerIds] = useState<string[]>([])
  const [headcount, setHeadcount] = useState("")
  const [hoursEach, setHoursEach] = useState("")
  const [savedLabour, setSavedLabour] = useState<OperationLabour | null>(null)
  const [labourDirty, setLabourDirty] = useState(false)
  const [notes, setNotes] = useState("")
  const [productRows, setProductRows] = useState<ProductRow[]>([emptyRow()])
  const [machineRows, setMachineRows] = useState<MachineRow[]>([emptyMachineRow()])
  const [savedMachines, setSavedMachines] = useState<OperationMachine[]>([])
  const [savedOp, setSavedOp] = useState<Operation | null>(null)
  const [previews, setPreviews] = useState<Record<string, OperationProductPreview | null>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [warnings, setWarnings] = useState<OperationWarning[]>([])
  const [productDrawerOpen, setProductDrawerOpen] = useState(false)
  const [areaHa, setAreaHa] = useState(block.net_area_ha)

  const productsQuery = useQuery({
    queryKey: ["products", farmId],
    queryFn: () => apiGet<ProductList>(`/v1/farms/${farmId}/products`),
    enabled: open && farmId !== "",
  })
  const workersQuery = useQuery({
    queryKey: ["workers", farmId],
    queryFn: () => apiGet<WorkerList>(`/v1/farms/${farmId}/workers`),
    enabled: open && farmId !== "",
  })
  const machinesQuery = useQuery({
    queryKey: ["machines", farmId],
    queryFn: () => apiGet<MachineList>(`/v1/farms/${farmId}/machines`),
    enabled: open && farmId !== "",
  })
  const sortedWorkers = useMemo(() => {
    const list = workersQuery.data?.workers ?? []
    return [...list].sort((left, right) => {
      if (left.active !== right.active) return left.active ? -1 : 1
      return left.name.localeCompare(right.name)
    })
  }, [workersQuery.data])
  const sortedMachines = useMemo(() => {
    const list = machinesQuery.data?.machines ?? []
    return [...list].sort((left, right) => {
      if (left.status !== right.status) return left.status === "ok" ? -1 : 1
      return left.name.localeCompare(right.name)
    })
  }, [machinesQuery.data])
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
      setLabourMode("workers")
      setSelectedWorkerIds([])
      setHeadcount("")
      setHoursEach("")
      setSavedLabour(null)
      setLabourDirty(false)
      setNotes("")
      setProductRows([emptyRow()])
      setMachineRows([emptyMachineRow()])
      setSavedMachines([])
      setSavedOp(null)
      setAreaHa(block.net_area_ha)
    } else {
      setType(operation.type)
      setDate(operation.date)
      setSelectedValves(operation.valve_ids)
      setTarget(operation.target ?? "")
      if (operation.labour !== null) {
        if (operation.labour.workers.length > 0) {
          setLabourMode("workers")
          setSelectedWorkerIds(operation.labour.workers.map((worker) => worker.id))
          setHeadcount("")
        } else {
          setLabourMode("headcount")
          setSelectedWorkerIds([])
          setHeadcount(String(operation.labour.headcount))
        }
        setHoursEach(operation.labour.hours_each)
        setSavedLabour(operation.labour)
      } else {
        setLabourMode("workers")
        setSelectedWorkerIds([])
        setHeadcount(operation.workers_count === null ? "" : String(operation.workers_count))
        setHoursEach("")
        setSavedLabour(null)
      }
      setLabourDirty(false)
      setNotes(operation.notes ?? "")
      setProductRows(rowsFromOperation(operation))
      setMachineRows(machineRowsFromOperation(operation))
      setSavedMachines(operation.machines)
      setSavedOp(operation)
      setAreaHa(operation.area_ha)
    }
    setErrors({})
    setFormError(null)
    setPreviews({})
    setWarnings([])
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

  function toggleWorker(id: string) {
    setLabourDirty(true)
    setSelectedWorkerIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  function updateRow(key: string, patch: Partial<ProductRow>) {
    setProductRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  }

  function updateMachineRow(key: string, patch: Partial<MachineRow>) {
    setMachineRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  }

  async function onSubmit(submitEvent: FormEvent) {
    submitEvent.preventDefault()
    const next: Record<string, string> = {}
    if (date.trim() === "") next.date = "journal.errors.date"
    if (selectedValves.length === 0) next.valve_ids = "journal.errors.valve"

    const hasWorkers = labourMode === "workers" && selectedWorkerIds.length > 0
    const hasHeadcount = labourMode === "headcount" && headcount.trim() !== ""
    const hasHours = hoursEach.trim() !== ""
    let labourPayload: {
      worker_ids: string[] | null
      headcount: number | null
      hours_each: string
    } | null = null

    if (hasWorkers || hasHeadcount || hasHours) {
      let countValid = true
      if (labourMode === "workers") {
        if (selectedWorkerIds.length === 0) {
          next.headcount = "journal.errors.labourWorkersRequired"
          countValid = false
        }
      } else {
        if (headcount.trim() === "") {
          next.headcount = "journal.errors.labourWorkersRequired"
          countValid = false
        } else if (!/^\d+$/.test(headcount.trim())) {
          next.headcount = "journal.errors.labourHeadcount"
          countValid = false
        }
      }
      const hoursWire = wireDecimal(hoursEach)
      if (!hasHours || hoursWire === null || !isDecimal(hoursEach) || Number(hoursWire) < 0) {
        next.hours_each = "journal.errors.labourHours"
      } else if (countValid) {
        labourPayload =
          labourMode === "workers"
            ? {
                worker_ids: selectedWorkerIds,
                headcount: null,
                hours_each: hoursWire,
              }
            : {
                worker_ids: [],
                headcount: Number(headcount.trim()),
                hours_each: hoursWire,
              }
      }
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
    const seenMachineIds = new Set<string>()
    const machineLines = machineRows.flatMap((row, index) => {
      if (row.machine_id === "" && row.hours.trim() === "" && row.fuel_l.trim() === "") {
        return []
      }
      if (row.machine_id === "") {
        next[`machines.${index}`] = "journal.errors.machineMissing"
        return []
      }
      if (seenMachineIds.has(row.machine_id)) {
        next[`machines.${index}`] = "journal.errors.machineDuplicate"
        return []
      }
      seenMachineIds.add(row.machine_id)
      const hoursWire = wireDecimal(row.hours)
      if (hoursWire === null || !isDecimal(row.hours) || Number(hoursWire) <= 0) {
        next[`machines.${index}.hours`] = "journal.errors.machineHours"
        return []
      }
      const fuelWire = wireDecimal(row.fuel_l)
      if (row.fuel_l.trim() !== "") {
        if (fuelWire === null || !isDecimal(row.fuel_l) || Number(fuelWire) < 0) {
          next[`machines.${index}.fuel_l`] = "journal.errors.machineFuel"
          return []
        }
      }
      return [
        {
          machine_id: row.machine_id,
          hours: hoursWire,
          fuel_l: row.fuel_l.trim() === "" ? null : fuelWire,
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
      workers_count: null,
      notes: notes.trim() === "" ? null : notes.trim(),
      products: lines,
      labour: labourPayload,
      machines: machineLines,
    }
    const targetOp = savedOp ?? operation
    let saved: Operation
    try {
      if (targetOp === null) {
        saved = await apiSend<Operation>("POST", `/v1/farms/${farmId}/operations`, payload)
      } else {
        saved = await apiSend<Operation>("PATCH", `/v1/operations/${targetOp.id}`, payload, {
          "If-Match": String(targetOp.version),
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
    await queryClient.invalidateQueries({ queryKey: ["labour-norms", farmId] })
    await queryClient.invalidateQueries({ queryKey: ["machines", farmId] })
    await queryClient.invalidateQueries({ queryKey: ["machine"] })
    await queryClient.invalidateQueries({ queryKey: ["maintenance-due", farmId] })
    setSaving(false)
    onSaved()
    setSavedOp(saved)
    setSavedLabour(saved.labour)
    setSavedMachines(saved.machines)
    setLabourDirty(false)
    // Keep the drawer open to show operation warnings or calculated machine work rates.
    if (saved.warnings.length > 0 || saved.machines.length > 0) {
      setWarnings(saved.warnings)
    } else {
      setWarnings([])
      onOpenChange(false)
    }
  }

  const stage = stageQuery.data?.stage
  const phiDays = bestPhi(selectedProducts)
  const reentryH = bestReentry(selectedProducts)
  const reentryUntil =
    reentryH === null
      ? null
      : new Date(new Date(`${date}T12:00:00Z`).getTime() + reentryH * 3600000).toISOString()

  const previewCount =
    labourMode === "workers"
      ? selectedWorkerIds.length
      : /^\d+$/.test(headcount.trim())
        ? Number(headcount.trim())
        : null
  const previewHoursWire = wireDecimal(hoursEach)
  const previewHoursNum =
    previewHoursWire !== null && isDecimal(hoursEach) && Number(previewHoursWire) >= 0
      ? asNumber(previewHoursWire)
      : null
  const showSavedTotal = !labourDirty && savedLabour !== null
  const showDraftPreview =
    !showSavedTotal &&
    previewCount !== null &&
    previewCount > 0 &&
    previewHoursNum !== null

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
          {warnings.length > 0 ? (
            <div className="rounded-xl border border-[#FDE68A] bg-[#FFFBEB] p-3 text-[12px] text-amb">
              {warnings.map((warning, index) => (
                <p key={warningKey(warning, index)}>{warningText(warning, t)}</p>
              ))}
            </div>
          ) : null}
          {savedMachines.length > 0 ? (
            <div className="flex flex-col gap-1.5 rounded-xl border border-line bg-[#F7F8F7] p-3 text-[12px]">
              <div className="flex items-center justify-between gap-2">
                <p className="font-semibold">{t("journal.machineWorkRateTitle")}</p>
                <SourceTag kind="calculated" />
              </div>
              {savedMachines.map((line) => (
                <p key={line.id} className="flex items-center justify-between gap-2">
                  <span>{line.name}</span>
                  <span className="font-semibold" dir="ltr">
                    {line.work_rate_ha_h !== null
                      ? t("team.machines.workRateValue", {
                          rate: formatNumber(asNumber(line.work_rate_ha_h), 2, lang),
                        })
                      : t("common.missing")}
                  </span>
                </p>
              ))}
            </div>
          ) : null}
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

          <div className="flex flex-col gap-3 rounded-xl border border-line p-3">
            <FieldLabel label={t("journal.machinesSection")} tag="optional" />
            {sortedMachines.length === 0 ? (
              <p className="text-[12px] text-mut">{t("journal.machinesEmpty")}</p>
            ) : (
              <>
                {machineRows.map((row, index) => {
                  const picked = sortedMachines.find((item) => item.id === row.machine_id)
                  const inRepair = picked?.status === "repair"
                  return (
                    <div key={row.key} className="rounded-xl border border-line p-3">
                      <label className="block">
                        <FieldLabel label={t("journal.machine")} />
                        <select
                          className={`${fieldClass} ${inRepair ? "bg-[#F3F5F3] text-mut" : ""}`}
                          value={row.machine_id}
                          aria-invalid={errors[`machines.${index}`] !== undefined}
                          onChange={(change) =>
                            updateMachineRow(row.key, { machine_id: change.target.value })
                          }
                        >
                          <option value="">{t("journal.chooseMachine")}</option>
                          {sortedMachines.map((machine) => (
                            <option
                              key={machine.id}
                              value={machine.id}
                              className={machine.status === "repair" ? "text-mut" : undefined}
                            >
                              {machine.status === "repair"
                                ? `${machine.name} (${t("team.machines.inRepairLower")})`
                                : machine.name}
                            </option>
                          ))}
                        </select>
                        <FieldError message={errors[`machines.${index}`]} />
                      </label>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <label className="block">
                          <FieldLabel label={t("journal.machineHours")} />
                          <input
                            className={fieldClass}
                            inputMode="decimal"
                            dir="ltr"
                            lang="en"
                            value={row.hours}
                            aria-invalid={errors[`machines.${index}.hours`] !== undefined}
                            onChange={(change) =>
                              updateMachineRow(row.key, { hours: change.target.value })
                            }
                          />
                          <FieldError message={errors[`machines.${index}.hours`]} />
                        </label>
                        <label className="block">
                          <FieldLabel label={t("journal.machineFuel")} tag="optional" />
                          <input
                            className={fieldClass}
                            inputMode="decimal"
                            dir="ltr"
                            lang="en"
                            value={row.fuel_l}
                            aria-invalid={errors[`machines.${index}.fuel_l`] !== undefined}
                            onChange={(change) =>
                              updateMachineRow(row.key, { fuel_l: change.target.value })
                            }
                          />
                          <FieldError message={errors[`machines.${index}.fuel_l`]} />
                        </label>
                      </div>
                      {machineRows.length > 1 ? (
                        <button
                          type="button"
                          className={`mt-2 ${outlineBtn} h-8 px-3 text-[12px]`}
                          onClick={() =>
                            setMachineRows((current) =>
                              current.filter((item) => item.key !== row.key),
                            )
                          }
                        >
                          {t("journal.removeMachine")}
                        </button>
                      ) : null}
                    </div>
                  )
                })}
                <button
                  type="button"
                  className={`${outlineBtn} self-start`}
                  onClick={() => setMachineRows((current) => [...current, emptyMachineRow()])}
                >
                  {t("journal.addMachine")}
                </button>
              </>
            )}
            <FieldError message={errors.machines} />
          </div>

          <div className="flex flex-col gap-3 rounded-xl border border-line p-3">
            <FieldLabel label={t("journal.labourSection")} tag="optional" />
            <div className="flex flex-wrap gap-2">
              <ChoiceChip
                selected={labourMode === "workers"}
                onClick={() => {
                  setLabourMode("workers")
                  setHeadcount("")
                  setLabourDirty(true)
                }}
              >
                {t("journal.labourModeWorkers")}
              </ChoiceChip>
              <ChoiceChip
                selected={labourMode === "headcount"}
                onClick={() => {
                  setLabourMode("headcount")
                  setSelectedWorkerIds([])
                  setLabourDirty(true)
                }}
              >
                {t("journal.labourModeHeadcount")}
              </ChoiceChip>
            </div>

            {labourMode === "workers" ? (
              <div>
                {sortedWorkers.length === 0 ? (
                  <p className="text-[12px] text-mut">{t("journal.labourNoWorkers")}</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {sortedWorkers.map((worker) => {
                      const picked = selectedWorkerIds.includes(worker.id)
                      const label = worker.active
                        ? worker.name
                        : `${worker.name} (${t("team.workers.statusInactive")})`
                      return (
                        <button
                          key={worker.id}
                          type="button"
                          aria-pressed={picked}
                          onClick={() => toggleWorker(worker.id)}
                          className={`inline-flex h-8 items-center rounded-full px-3 text-[12px] font-semibold ${
                            picked
                              ? worker.active
                                ? "bg-pri text-white"
                                : "border border-[#9CA3AF] bg-[#E5E7EB] text-mut"
                              : worker.active
                                ? "border border-[#C7D2C9] bg-white text-text"
                                : "border border-line bg-[#F3F5F3] text-mut"
                          }`}
                        >
                          {label}
                        </button>
                      )
                    })}
                  </div>
                )}
                <FieldError message={errors.worker_ids ?? errors.headcount} />
              </div>
            ) : (
              <label className="block">
                <FieldLabel label={t("journal.labourHeadcount")} />
                <input
                  className={fieldClass}
                  inputMode="numeric"
                  dir="ltr"
                  lang="en"
                  value={headcount}
                  aria-invalid={errors.headcount !== undefined}
                  onChange={(change) => {
                    setHeadcount(change.target.value)
                    setLabourDirty(true)
                  }}
                />
                <FieldError message={errors.headcount} />
              </label>
            )}

            <label className="block">
              <FieldLabel label={t("journal.labourHoursEach")} />
              <input
                className={fieldClass}
                inputMode="decimal"
                dir="ltr"
                lang="en"
                value={hoursEach}
                aria-invalid={errors.hours_each !== undefined}
                onChange={(change) => {
                  setHoursEach(change.target.value)
                  setLabourDirty(true)
                }}
              />
              <FieldError message={errors.hours_each} />
            </label>

            {showSavedTotal && savedLabour !== null ? (
              <p className="flex flex-wrap items-center gap-2 text-[12px]">
                <span className="font-semibold" dir="ltr">
                  {t("journal.labourTotal", {
                    total: formatNumber(asNumber(savedLabour.total_hours), 1, lang),
                  })}
                </span>
                <SourceTag kind="calculated" />
              </p>
            ) : showDraftPreview && previewCount !== null && previewHoursNum !== null ? (
              <p className="text-[12px] text-mut" dir="ltr">
                {t("journal.labourPreview", {
                  count: formatNumber(previewCount, 0, lang),
                  hours: formatNumber(previewHoursNum, 1, lang),
                })}
              </p>
            ) : null}
          </div>

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
