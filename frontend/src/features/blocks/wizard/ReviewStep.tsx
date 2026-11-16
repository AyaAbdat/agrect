import { useQuery, useQueryClient } from "@tanstack/react-query"
import type { FormEvent, ReactNode } from "react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useNavigate } from "react-router"
import { SatelliteMap } from "../../../components/map/SatelliteMap"
import { useAuth } from "../../../app/auth"
import { ApiError, apiGet } from "../../../lib/api"
import { formatNumber } from "../../../lib/format"
import { showDecimal, trainingName, varietyName } from "../display"
import {
  activeLang,
  cropLabel,
  type BlockValve,
  type CatalogTrainingSystem,
  type CatalogVariety,
} from "../types"
import { useBlockVersion, type StepSaveProps } from "./blockWrite"
import { REVIEW_FORM_ID } from "./steps"
import { FactRow, InlineError } from "./wizardUi"

const FIELD_ORDER = [
  "outline",
  "net_area_ha",
  "name",
  "crop_id",
  "planting",
  "irrigation_layout",
  "rows_total",
]

function unitValue(value: string, unit: string, missing: string): string {
  if (value === missing) return value
  return `${value} ${unit}`
}

function missingItem(field: string, code: string): { step: number; key: string } {
  if (field === "outline") return { step: 1, key: "blocks.missing.outline" }
  if (field === "net_area_ha") return { step: 1, key: "blocks.missing.netArea" }
  if (field === "name") return { step: 1, key: "blocks.missing.name" }
  if (field === "crop_id") return { step: 2, key: "blocks.missing.crop" }
  if (field === "planting") return { step: 2, key: "blocks.missing.planting" }
  if (field === "irrigation_layout") {
    return {
      step: 4,
      key:
        code === "irrigation.typed_flow_required"
          ? "blocks.missing.flow"
          : "blocks.missing.irrigation",
    }
  }
  if (field === "rows_total") return { step: 5, key: "blocks.missing.rows" }
  return { step: 1, key: "blocks.missing.other" }
}

function SummaryCard({
  title,
  editTo,
  editLabel,
  children,
}: {
  title: string
  editTo: string
  editLabel: string
  children: ReactNode
}) {
  return (
    <section className="rounded-2xl border border-line bg-white p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-[15px] font-bold">{title}</h2>
        <Link to={editTo} className="text-[13px] font-semibold text-pri">
          {editLabel}
        </Link>
      </div>
      {children}
    </section>
  )
}

export function ReviewStep({ block, onBusy }: StepSaveProps) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { currentFarmId } = useAuth()
  const { write } = useBlockVersion(block)
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const missing = t("common.missing")
  const [gaps, setGaps] = useState<Record<string, string> | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const cropId = block.crop?.id ?? null
  const varietiesQuery = useQuery({
    queryKey: ["catalog", "varieties", cropId],
    queryFn: () => apiGet<CatalogVariety[]>(`/v1/catalog/crops/${cropId}/varieties`),
    enabled: cropId !== null,
  })
  const trainingQuery = useQuery({
    queryKey: ["catalog", "training", cropId],
    queryFn: () => apiGet<CatalogTrainingSystem[]>(`/v1/catalog/crops/${cropId}/training-systems`),
    enabled: cropId !== null,
  })
  const planting = block.plantings[0]
  const layout = block.irrigation_layout
  const edit = t("blocks.edit")
  const editTo = (step: number) => `/blocks/${block.id}/edit?step=${step}`

  const varietyPending =
    cropId !== null && planting?.variety_id !== null && varietiesQuery.isPending
  const variety = varietyName(planting, varietiesQuery.data ?? [])
  const root = planting?.rootstock?.trim() ?? ""
  let varietyLine = missing
  if (varietyPending) varietyLine = t("common.loading")
  else if (variety !== null && root !== "") varietyLine = `${variety} · ${root}`
  else if (variety !== null) varietyLine = variety
  else if (root !== "") varietyLine = root

  const trainingPending = block.training_system_id !== null && trainingQuery.isPending
  const trained = trainingName(
    block.training_system_id,
    block.training_other,
    trainingQuery.data ?? [],
    lang,
  )
  const trainingLine = trainingPending && trained === null ? t("common.loading") : (trained ?? missing)

  let spacing = missing
  if (planting?.row_spacing_m != null && planting.tree_spacing_m != null) {
    spacing = t("blocks.spacingPair", {
      row: formatNumber(Number(planting.row_spacing_m), 2, lang),
      tree: formatNumber(Number(planting.tree_spacing_m), 2, lang),
      unit: t("blocks.unitM"),
    })
  }

  let layoutLine = missing
  if (layout?.entry_mode === "typed_flow") layoutLine = t("blocks.flowTypedValue")
  else if (
    layout !== null &&
    layout.laterals_per_row !== null &&
    layout.emitter_spacing_m !== null &&
    layout.emitter_flow_lph !== null
  ) {
    layoutLine = t("blocks.layoutSummary", {
      laterals: formatNumber(layout.laterals_per_row, 0, lang),
      spacing: formatNumber(Number(layout.emitter_spacing_m), 2, lang),
      flow: formatNumber(Number(layout.emitter_flow_lph), 1, lang),
      m: t("blocks.unitM"),
      lph: t("blocks.unitLph"),
    })
  }

  function rowsFlow(valve: BlockValve): string {
    const rows = formatNumber(valve.row_to - valve.row_from + 1, 0, lang)
    const flow =
      valve.q_m3h === null ? missing : formatNumber(Number(valve.q_m3h), 2, lang)
    return t("blocks.rowsFlow", { rows, flow, unit: t("blocks.unitFlow") })
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setGaps(null)
    setFormError(null)
    onBusy(true)
    try {
      const saved = await write("POST", `/v1/blocks/${block.id}/complete`, undefined)
      if (currentFarmId !== null) {
        await queryClient.invalidateQueries({ queryKey: ["blocks", currentFarmId] })
      }
      void navigate(`/blocks/${saved.id}/setup`)
    } catch (error) {
      if (error instanceof ApiError && error.code === "block.incomplete") setGaps(error.fields)
      else if (error instanceof ApiError && (error.status === 409 || error.status === 428)) {
        setFormError("blocks.errors.version")
      } else setFormError("blocks.errors.save")
    } finally {
      onBusy(false)
    }
  }

  const gapItems =
    gaps === null
      ? []
      : Object.keys(gaps)
          .sort((left, right) => {
            const leftAt = FIELD_ORDER.indexOf(left)
            const rightAt = FIELD_ORDER.indexOf(right)
            return (leftAt < 0 ? FIELD_ORDER.length : leftAt) - (rightAt < 0 ? FIELD_ORDER.length : rightAt)
          })
          .map((field) => ({ field, code: gaps[field] ?? "", ...missingItem(field, gaps[field] ?? "") }))

  return (
    <form id={REVIEW_FORM_ID} className="min-w-0 flex-1" noValidate onSubmit={(event) => void onSubmit(event)}>
      {gapItems.length > 0 ? (
        <div className="mb-4 rounded-xl border border-red px-4 py-3" role="alert">
          <p className="text-[13px] font-semibold text-red">{t("blocks.incompleteTitle")}</p>
          <ul className="mt-2 flex flex-col gap-1">
            {gapItems.map((item) => (
              <li key={item.field}>
                <Link to={editTo(item.step)} className="text-[13px] font-semibold text-pri underline">
                  {t(item.key, { code: item.code })}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {formError !== null ? <p className="mb-4 text-[13px] text-red">{t(formError)}</p> : null}
      <div className="grid grid-cols-2 gap-4">
        <SummaryCard title={t("blocks.cards.outline")} editTo={editTo(1)} editLabel={edit}>
          <SatelliteMap
            height={170}
            blocks={[{ id: block.id, name: block.name, outline: block.outline }]}
          />
        </SummaryCard>
        <SummaryCard title={t("blocks.cards.location")} editTo={editTo(1)} editLabel={edit}>
          <FactRow label={t("blocks.name")} value={block.name} />
          <FactRow
            label={t("blocks.grossArea")}
            value={unitValue(showDecimal(block.gross_area_ha, 2, lang, missing), t("blocks.unitHa"), missing)}
            tag="calculated"
          />
          <FactRow
            label={t("blocks.netArea")}
            value={unitValue(showDecimal(block.net_area_ha, 2, lang, missing), t("blocks.unitHa"), missing)}
          />
          <FactRow
            label={t("blocks.rowDirection")}
            value={
              block.row_bearing_deg === null
                ? missing
                : `${showDecimal(block.row_bearing_deg, 1, lang, missing)} ${t("blocks.unitDeg")}`
            }
            tag="calculated"
          />
        </SummaryCard>
        <SummaryCard title={t("blocks.cards.training")} editTo={editTo(3)} editLabel={edit}>
          <FactRow label={t("blocks.system")} value={trainingLine} />
          {trainingQuery.isError ? (
            <InlineError onRetry={() => void trainingQuery.refetch()} />
          ) : null}
        </SummaryCard>
        <SummaryCard title={t("blocks.cards.planting")} editTo={editTo(2)} editLabel={edit}>
          <FactRow label={t("blocks.crop")} value={cropLabel(block.crop, lang) ?? missing} />
          <FactRow label={t("blocks.varietyAndRootstock")} value={varietyLine} />
          <FactRow
            label={t("blocks.plantingYear")}
            value={
              planting?.planting_year == null
                ? missing
                : formatNumber(planting.planting_year, 0, lang)
            }
          />
          <FactRow label={t("blocks.spacing")} value={spacing} />
          <FactRow
            label={t("blocks.treesPerHa")}
            value={
              planting?.trees_per_ha == null
                ? missing
                : formatNumber(planting.trees_per_ha, 0, lang)
            }
            tag="calculated"
          />
          <FactRow
            label={t("blocks.treesInBlock")}
            value={
              planting?.trees_count == null ? missing : formatNumber(planting.trees_count, 0, lang)
            }
            tag="calculated"
          />
          {varietiesQuery.isError ? (
            <InlineError onRetry={() => void varietiesQuery.refetch()} />
          ) : null}
        </SummaryCard>
        <SummaryCard title={t("blocks.cards.irrigation")} editTo={editTo(4)} editLabel={edit}>
          <FactRow
            label={t("blocks.system")}
            value={layout === null ? missing : t(`blocks.systems.${layout.system}`)}
          />
          <FactRow label={t("blocks.layout")} value={layoutLine} />
          <FactRow
            label={t("blocks.flowPerHa")}
            value={unitValue(showDecimal(layout?.q_ha_m3h, 2, lang, missing), t("blocks.unitFlow"), missing)}
            tag="calculated"
          />
          <FactRow
            label={t("blocks.applicationRate")}
            value={unitValue(showDecimal(layout?.rate_mm_h, 2, lang, missing), t("blocks.unitMmh"), missing)}
            tag="calculated"
          />
          <FactRow
            label={t("blocks.blockFlow")}
            value={unitValue(showDecimal(layout?.q_block_m3h, 2, lang, missing), t("blocks.unitFlow"), missing)}
            tag="calculated"
          />
          <FactRow
            label={t("blocks.flowMeter")}
            value={layout?.flow_meter === true ? t("blocks.meterAdded") : missing}
            tag="optional"
          />
        </SummaryCard>
        <SummaryCard title={t("blocks.cards.valves")} editTo={editTo(5)} editLabel={edit}>
          <FactRow
            label={t("blocks.valveCount")}
            value={
              block.valves.length === 0 ? missing : formatNumber(block.valves.length, 0, lang)
            }
          />
          {block.valves.length === 0 ? (
            <FactRow label={t("blocks.rowsAndFlow")} value={missing} />
          ) : (
            block.valves.map((valve) => (
              <FactRow key={valve.id} label={t("blocks.rowsAndFlow")} value={rowsFlow(valve)} />
            ))
          )}
        </SummaryCard>
      </div>
    </form>
  )
}
