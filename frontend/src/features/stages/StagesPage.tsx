import { useState, type ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Link, useNavigate, useParams } from "react-router"
import { activeLang, cropLabel, localizedName, type CatalogVariety } from "../blocks/types"
import { formatNumber } from "../../lib/format"
import { asNumber, formatAxisDate, formatMediumDate } from "../weather/format"
import type { GddSettingListItem } from "../weather/types"
import {
  LoadError,
  PageHeader,
  PageSkeleton,
  SourceTag,
  cardClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { ConfirmStageDrawer } from "./ConfirmStageDrawer"
import {
  codeLabelKey,
  fractionDigits,
  isSownCrop,
  methodKey,
  placeholderRow,
  scaleLabelKey,
} from "./display"
import { SowingDrawer } from "./SowingDrawer"
import { SourcePill, StatusTag } from "./tags"
import type { StageRow, StageSetting } from "./types"
import { useBlockSeason } from "./useBlockSeason"

function settingFor(
  cropId: string | null,
  live: StageSetting | null | undefined,
  rows: GddSettingListItem[] | undefined,
): StageSetting | null {
  if (live !== undefined && live !== null) return live
  if (cropId === null || rows === undefined) return null
  const found = rows.find((row) => row.crop_id === cropId)
  if (found === undefined) return null
  return { base_c: found.base_c, upper_c: found.upper_c, method: found.method }
}

function varietyName(
  varietyId: string | null,
  varietyText: string | null,
  varieties: CatalogVariety[] | undefined,
  missing: string,
): string {
  if (varietyText !== null && varietyText.trim() !== "") return varietyText
  if (varietyId === null || varieties === undefined) return missing
  return varieties.find((row) => row.id === varietyId)?.name ?? missing
}

function Amber({
  title,
  text,
  action,
}: {
  title: string
  text: string
  action?: ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl bg-[#FEF3C7] px-4 py-3 text-[13px]">
      <div className="min-w-0">
        <p className="font-semibold text-amb">{title}</p>
        <p className="text-amb">{text}</p>
      </div>
      {action}
    </div>
  )
}

export function StagesPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { blockId } = useParams()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const season = useBlockSeason(blockId)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [sowingOpen, setSowingOpen] = useState(false)
  const [prefillId, setPrefillId] = useState("")

  if (blockId === undefined || season.farmId === null) return null
  const cropPending = season.cropId !== null && (season.catalogQuery.isPending || season.varietiesQuery.isPending || season.prefsQuery.isPending)
  const stagesPending = season.year !== null && season.stagesQuery.isPending
  if (
    season.farmQuery.isPending ||
    season.blockQuery.isPending ||
    season.settingsQuery.isPending ||
    cropPending ||
    stagesPending
  ) {
    return <PageSkeleton />
  }
  const failed =
    season.farmQuery.isError ||
    season.blockQuery.isError ||
    season.settingsQuery.isError ||
    (season.cropId !== null &&
      (season.catalogQuery.isError || season.varietiesQuery.isError || season.prefsQuery.isError)) ||
    (season.year !== null && season.stagesQuery.isError)
  if (
    failed ||
    season.blockQuery.data === undefined ||
    season.year === null ||
    season.today === null ||
    season.settingsQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void season.farmQuery.refetch()
          void season.blockQuery.refetch()
          void season.catalogQuery.refetch()
          void season.varietiesQuery.refetch()
          void season.settingsQuery.refetch()
          void season.prefsQuery.refetch()
          void season.stagesQuery.refetch()
        }}
      />
    )
  }

  const block = season.blockQuery.data
  const timeline = season.stagesQuery.data ?? null
  const catalog = season.catalogQuery.data
  const crop = block.crop
  const missing = t("common.missing")
  const planting = block.plantings[0]
  const variety = varietyName(
    planting?.variety_id ?? null,
    planting?.variety_text ?? null,
    season.varietiesQuery.data,
    missing,
  )
  const cropName = cropLabel(crop, lang) ?? missing
  const setting = settingFor(season.cropId, timeline?.setting, season.settingsQuery.data)
  const hidden = new Set(
    (season.prefsQuery.data?.items ?? []).filter((item) => item.hidden).map((item) => item.stage_def_id),
  )
  const live = new Map((timeline?.stages ?? []).map((row) => [row.stage.id, row]))
  const reason = setting === null ? "phenology.no_gdd_setting" : "phenology.season_start_required"
  const rows: StageRow[] =
    catalog === undefined
      ? []
      : catalog.stages
          .filter((stage) => !hidden.has(stage.id))
          .map((stage) => live.get(stage.id) ?? placeholderRow(stage, reason))
  const counted = timeline?.today.dd_counted ?? null
  const countedNumber = asNumber(counted)
  const since =
    countedNumber === null || timeline?.season.start_date === null || timeline === null
      ? t("stages.sinceNone")
      : t("stages.since", {
          value: formatNumber(countedNumber, fractionDigits(countedNumber), lang),
          date: formatMediumDate(timeline.season.start_date, lang),
        })
  const baseNumber = asNumber(setting?.base_c)
  const upperNumber = asNumber(setting?.upper_c)
  const baseLine =
    setting === null
      ? t("stages.notSet")
      : t("stages.baseLine", {
          base: formatNumber(baseNumber, fractionDigits(baseNumber), lang),
          upper:
            setting.upper_c === null
              ? missing
              : formatNumber(upperNumber, fractionDigits(upperNumber), lang),
          method: t(methodKey(setting.method)),
        })
  const currentId = timeline?.today.current_stage?.id ?? null
  const choices = (catalog?.stages ?? []).map((stage) => ({ id: stage.id, name: stage.name }))

  function openConfirm(stageId = "") {
    setPrefillId(stageId)
    setConfirmOpen(true)
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("stages.crumbBlock", { block: block.name })}
        title={t("nav.stages")}
        sub={t("stages.sub", { crop: cropName, variety, year: String(season.year) })}
        actions={
          <>
            <Link to="/stages" className={`inline-flex items-center ${outlineBtn}`}>
              {t("stages.allBlocks")}
            </Link>
            <Link
              to={season.cropId === null ? "/stages/settings" : `/stages/settings?crop=${season.cropId}`}
              className={`inline-flex items-center ${outlineBtn}`}
            >
              {t("stages.modelSettings")}
            </Link>
            <button type="button" className={primaryBtn} onClick={() => openConfirm()}>
              {t("stages.confirm")}
            </button>
          </>
        }
      />
      {timeline === null ? (
        <Amber
          title={t("stages.seasonNotStarted")}
          text={t("stages.seasonNotStartedText")}
          action={
            <span className="flex shrink-0 items-center gap-2">
              {crop !== null && isSownCrop(crop.code) ? (
                <button type="button" className={outlineBtn} onClick={() => setSowingOpen(true)}>
                  {t("stages.setSowing")}
                </button>
              ) : null}
              <button type="button" className={outlineBtn} onClick={() => openConfirm()}>
                {t("stages.confirm")}
              </button>
            </span>
          }
        />
      ) : null}
      {setting === null ? (
        <Amber
          title={t("stages.missingSettings")}
          text={t("stages.missingSettingsText")}
          action={
            <Link
              to={`/blocks/${blockId}/weather/degree-day-settings`}
              className="shrink-0 font-semibold text-pri"
            >
              {t("stages.openSettings")}
            </Link>
          }
        />
      ) : null}
      {crop === null ? <p className="text-[13px] text-mut">{t("stages.noCrop")}</p> : null}
      <div className="grid grid-cols-[minmax(0,1.4fr)_minmax(260px,0.8fr)] items-start gap-4">
        <section className={cardClass}>
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-[16px] font-bold">{t("stages.ddSoFar")}</h2>
            <SourceTag kind="calculated" />
          </div>
          <p className="mt-3 text-[20px] font-bold leading-tight">{since}</p>
          <p className="mt-1 text-[13px] text-mut">{baseLine}</p>
        </section>
        <section className={cardClass}>
          <h2 className="text-[16px] font-bold">{t("stages.legend")}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusTag label="observed" />
            <StatusTag label="predicted" />
            <StatusTag label="not_enough_data" />
            <StatusTag label="beyond_data" />
          </div>
          <p className="mt-3 text-[13px] text-mut">{t("stages.legendText")}</p>
        </section>
      </div>
      <section className={cardClass}>
        <h2 className="text-[16px] font-bold">{t("nav.stages")}</h2>
        <p className="mt-1 text-[13px] text-mut">
          {catalog === undefined
            ? missing
            : t("stages.tableIntro", {
                crop: cropName,
                scale: t(scaleLabelKey(catalog.scale)),
              })}
        </p>
        {rows.length === 0 ? (
          <p className="py-10 text-center text-mut">{missing}</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[720px] text-start text-[13px]">
              <thead>
                <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-wide text-mut">
                  <th className="px-2 py-2 font-semibold">{t("stages.colStage")}</th>
                  <th className="px-2 py-2 font-semibold">{t("stages.colCode")}</th>
                  <th className="px-2 py-2 font-semibold">{t("stages.colNeeded")}</th>
                  <th className="px-2 py-2 font-semibold">{t("stages.colDate")}</th>
                  <th className="px-2 py-2 text-end font-semibold">{t("stages.colStatus")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const needed = asNumber(row.dd_needed)
                  const current = row.stage.id === currentId
                  return (
                    <tr
                      key={row.stage.id}
                      className={`cursor-pointer border-b border-line last:border-b-0 ${
                        current ? "bg-mint" : "hover:bg-[#F7F8F7]"
                      }`}
                      onClick={() => void navigate(`/blocks/${blockId}/stages/${row.stage.id}`)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          void navigate(`/blocks/${blockId}/stages/${row.stage.id}`)
                        }
                      }}
                      tabIndex={0}
                    >
                      <td className="px-2 py-3 font-semibold">{localizedName(row.stage.name, lang)}</td>
                      <td className="px-2 py-3 text-mut">
                        {catalog === undefined
                          ? row.stage.code
                          : t(codeLabelKey(catalog.scale), { code: row.stage.code })}
                      </td>
                      <td className="px-2 py-3">
                        {needed === null ? (
                          missing
                        ) : (
                          <span className="inline-flex items-center gap-1.5">
                            <span>
                              {formatNumber(needed, fractionDigits(needed), lang)} {t("stages.unitCday")}
                            </span>
                            {row.dd_source !== null ? (
                              <SourcePill source={row.dd_source} citation={row.citation} />
                            ) : null}
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-3">
                        {row.date === null ? (
                          <span className="text-mut">{missing}</span>
                        ) : (
                          <span>
                            <span className="block">{formatMediumDate(row.date, lang)}</span>
                            {row.label === "predicted" && row.earliest !== null && row.latest !== null ? (
                              <span className="block text-[11px] text-mut">
                                {t("stages.range", {
                                  from: formatAxisDate(row.earliest, lang),
                                  to: formatAxisDate(row.latest, lang),
                                })}
                              </span>
                            ) : null}
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-3 text-end">
                        <StatusTag label={row.label} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <ConfirmStageDrawer
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        blockId={blockId}
        year={season.year}
        today={season.today}
        seasonId={timeline?.season.id ?? null}
        stages={choices}
        observations={timeline?.observations ?? []}
        stageId={prefillId}
        dateSeen=""
        share=""
        lang={lang}
      />
      <SowingDrawer
        open={sowingOpen}
        onOpenChange={setSowingOpen}
        blockId={blockId}
        year={season.year}
      />
    </div>
  )
}
