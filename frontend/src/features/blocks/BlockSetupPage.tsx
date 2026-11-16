import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { useNavigate, useParams } from "react-router"
import { Button } from "@/components/ui/button"
import { SatelliteMap } from "../../components/map/SatelliteMap"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { crumbClass } from "../../lib/navStyles"
import { formatHistoryDate, showDecimal, trainingName, varietyName } from "./display"
import { ErrorRow, LoadingRow } from "./Status"
import {
  activeLang,
  cropLabel,
  type BlockDetail,
  type BlockHistoryItem,
  type CatalogTrainingSystem,
  type CatalogVariety,
} from "./types"
import { FactRow, InlineError } from "./wizard/wizardUi"

export function BlockSetupPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { blockId } = useParams()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const historyQuery = useQuery({
    queryKey: ["block-history", blockId],
    queryFn: () => apiGet<BlockHistoryItem[]>(`/v1/blocks/${blockId}/history`),
    enabled: blockId !== undefined,
  })

  if (blockId === undefined) return null
  if (blockQuery.isPending) return <LoadingRow />
  if (blockQuery.isError || blockQuery.data === undefined) {
    return <ErrorRow onRetry={() => void blockQuery.refetch()} />
  }

  const block = blockQuery.data
  const missing = t("common.missing")
  const cropId = block.crop?.id ?? null
  return (
    <SetupBody
      block={block}
      cropId={cropId}
      lang={lang}
      missing={missing}
      history={historyQuery.data ?? []}
      historyPending={historyQuery.isPending}
      historyError={historyQuery.isError}
      onHistoryRetry={() => void historyQuery.refetch()}
      onEdit={(step) => void navigate(`/blocks/${block.id}/edit?step=${step}`)}
    />
  )
}

function withUnit(value: string, unit: string, missing: string): string {
  if (value === missing) return missing
  return `${value} ${unit}`
}

function SetupBody({
  block,
  cropId,
  lang,
  missing,
  history,
  historyPending,
  historyError,
  onHistoryRetry,
  onEdit,
}: {
  block: BlockDetail
  cropId: string | null
  lang: string
  missing: string
  history: BlockHistoryItem[]
  historyPending: boolean
  historyError: boolean
  onHistoryRetry: () => void
  onEdit: (step: number) => void
}) {
  const { t } = useTranslation()
  const planting = block.plantings[0]
  const layout = block.irrigation_layout
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
  const varietyPending = cropId !== null && planting?.variety_id !== null && varietiesQuery.isPending
  const named = varietyName(planting, varietiesQuery.data ?? [])
  const variety = varietyPending ? t("common.loading") : (named ?? missing)
  const area = showDecimal(block.net_area_ha, 2, lang, missing)
  const crop = cropLabel(block.crop, lang) ?? missing
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
  const draft = block.status === "draft"
  const entries = history.slice(0, 5)
  const meter = layout?.flow_meter === true

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className={crumbClass}>{t("blocks.setupCrumb", { name: block.name })}</p>
          <h1 className="text-[24px] font-bold leading-tight">{block.name}</h1>
          <p className="mt-1 text-mut">{t("blocks.setupSub", { crop, variety, area })}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {draft ? (
            <span className="rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[11px] font-semibold text-amb">
              {t("blocks.draft")}
            </span>
          ) : null}
          {draft ? (
            <Button
              type="button"
              className="h-9 rounded-full bg-pri px-4 text-white"
              onClick={() => onEdit(1)}
            >
              {t("blocks.finishSetup")}
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              className="h-9 rounded-full px-4"
              onClick={() => onEdit(6)}
            >
              {t("blocks.edit")}
            </Button>
          )}
        </div>
      </header>
      <div className="flex items-start gap-4">
        <section className="min-w-0 flex-1 rounded-2xl border border-line bg-white p-4">
          <h2 className="text-[15px] font-bold">{t("blocks.setupCard")}</h2>
          <p className="mt-1 text-[13px] text-mut">{t("blocks.setupLead")}</p>
          <div className="mt-3">
            <FactRow
              label={t("blocks.treesLabel")}
              value={
                block.trees_count === null ? missing : formatNumber(block.trees_count, 0, lang)
              }
              tag="calculated"
            />
            <FactRow label={t("blocks.spacing")} value={spacing} />
            <FactRow label={t("blocks.steps.training")} value={trainingLine} />
            <FactRow
              label={t("blocks.rowDirection")}
              value={withUnit(showDecimal(block.row_bearing_deg, 1, lang, missing), t("blocks.unitDeg"), missing)}
              tag="calculated"
            />
            <FactRow
              label={t("blocks.blockFlow")}
              value={withUnit(
                showDecimal(layout?.q_block_m3h ?? block.q_block_m3h, 2, lang, missing),
                t("blocks.unitFlow"),
                missing,
              )}
              tag="calculated"
            />
            <FactRow
              label={t("blocks.steps.valves")}
              value={
                block.valves.length === 0 ? missing : formatNumber(block.valves.length, 0, lang)
              }
            />
          </div>
          {trainingQuery.isError ? <InlineError onRetry={() => void trainingQuery.refetch()} /> : null}
          {varietiesQuery.isError ? (
            <InlineError onRetry={() => void varietiesQuery.refetch()} />
          ) : null}
          <p className="mb-2 mt-4 text-[13px] font-semibold">{t("blocks.blockOutline")}</p>
          <SatelliteMap
            height={240}
            blocks={[{ id: block.id, name: block.name, outline: block.outline }]}
          />
        </section>
        <div className="flex w-[360px] shrink-0 flex-col gap-4">
          <section className="rounded-2xl border border-line bg-white p-4">
            <h2 className="text-[15px] font-bold">{t("blocks.flowSource")}</h2>
            {meter ? (
              <p className="mt-2 text-[13px] text-mut">{t("blocks.flowSourceMeter")}</p>
            ) : (
              <>
                <p className="mt-2 text-[13px] text-mut">{t("blocks.flowSourceCalculated")}</p>
                <Button
                  type="button"
                  variant="outline"
                  className="mt-3 h-9 rounded-full px-4"
                  onClick={() => onEdit(4)}
                >
                  {t("blocks.addAFlowMeter")}
                </Button>
              </>
            )}
          </section>
          <section className="rounded-2xl border border-line bg-white p-4">
            <h2 className="text-[15px] font-bold">{t("blocks.historyTitle")}</h2>
            <p className="mt-1 text-[13px] text-mut">{t("blocks.historyLead")}</p>
            {historyPending ? <p className="mt-3 text-[13px]">{t("common.loading")}</p> : null}
            {historyError ? <InlineError onRetry={onHistoryRetry} /> : null}
            {!historyPending && !historyError && entries.length === 0 ? (
              <p className="mt-3 text-[13px] text-mut">{t("blocks.historyEmpty")}</p>
            ) : null}
            {!historyPending && !historyError && entries.length > 0 ? (
              <ul className="mt-3">
                {entries.map((item) => (
                  <li key={item.id} className="border-b border-line py-2 last:border-b-0">
                    <p className="text-[13px] font-semibold">
                      {formatHistoryDate(item.changed_at, lang, missing)}
                    </p>
                    <p className="text-[12px] text-mut">
                      {t("blocks.fieldsChanged", { count: item.changed_fields.length })}
                    </p>
                    {item.reason !== null && item.reason.trim() !== "" ? (
                      <p className="text-[12px] italic text-mut">
                        {item.reason === "completed" ? t("blocks.reasonCompleted") : item.reason}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  )
}
