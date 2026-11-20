import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import { activeLang, cropLabel, localizedName } from "../blocks/types"
import { formatNumber } from "../../lib/format"
import { asNumber, formatAxisDate, formatMediumDate } from "../weather/format"
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
import { codeLabelKey, fractionDigits, placeholderRow, reasonKey } from "./display"
import { StatusTag } from "./tags"
import type { StageRow } from "./types"
import { useBlockSeason } from "./useBlockSeason"

function Step({ n, text }: { n: string; text: string }) {
  return (
    <li className="flex items-center gap-3 border-b border-line py-2.5 last:border-b-0">
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-mint text-[12px] font-bold text-pri">
        {n}
      </span>
      <span>{text}</span>
    </li>
  )
}

export function StageDetailPage() {
  const { t, i18n } = useTranslation()
  const { blockId, stageDefId } = useParams()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const season = useBlockSeason(blockId)
  const [open, setOpen] = useState(false)

  if (blockId === undefined || stageDefId === undefined || season.farmId === null) return null
  const cropPending =
    season.cropId !== null &&
    (season.catalogQuery.isPending || season.prefsQuery.isPending)
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
    (season.cropId !== null && (season.catalogQuery.isError || season.prefsQuery.isError)) ||
    (season.year !== null && season.stagesQuery.isError)
  if (
    failed ||
    season.blockQuery.data === undefined ||
    season.settingsQuery.data === undefined ||
    season.year === null ||
    season.today === null ||
    season.catalogQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void season.farmQuery.refetch()
          void season.blockQuery.refetch()
          void season.catalogQuery.refetch()
          void season.stagesQuery.refetch()
        }}
      />
    )
  }

  const catalog = season.catalogQuery.data
  const stage = catalog.stages.find((row) => row.id === stageDefId)
  if (stage === undefined) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p>{t("stages.missingStage")}</p>
        <Link to={`/blocks/${blockId}/stages`} className={`inline-flex items-center ${outlineBtn}`}>
          {t("stages.back")}
        </Link>
      </div>
    )
  }
  const timeline = season.stagesQuery.data ?? null
  const listed = season.settingsQuery.data?.find((item) => item.crop_id === season.cropId)
  const hasSetting = (timeline !== null && timeline.setting !== null) || listed !== undefined
  const live = timeline?.stages.find((row) => row.stage.id === stage.id)
  const row: StageRow =
    live ??
    placeholderRow(stage, hasSetting ? "phenology.season_start_required" : "phenology.no_gdd_setting")
  const needed = asNumber(row.dd_needed)
  const counted = asNumber(timeline?.today.dd_counted ?? null)
  const code = t(codeLabelKey(catalog.scale), { code: stage.code })
  const cropName = cropLabel(season.blockQuery.data.crop, lang) ?? t("common.missing")
  const valueFrom =
    row.dd_source === "entered"
      ? t("stages.enteredByYou")
      : row.dd_source === "literature"
        ? (row.citation ?? t("common.missing"))
        : t("common.missing")
  const observed = timeline?.observations.find((item) => item.stage_def_id === stage.id)
  const years = timeline?.history.years_count ?? null
  const showDate = row.date !== null && (row.label === "predicted" || row.label === "observed")

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("stages.season")}
        title={localizedName(stage.name, lang)}
        sub={t("stages.detailSub", { code, crop: cropName })}
        actions={
          <>
            <Link to={`/blocks/${blockId}/stages`} className={`inline-flex items-center ${outlineBtn}`}>
              {t("stages.back")}
            </Link>
            <button type="button" className={primaryBtn} onClick={() => setOpen(true)}>
              {t("stages.confirmThis")}
            </button>
          </>
        }
      />
      <div className="grid grid-cols-[minmax(0,1.4fr)_minmax(280px,0.85fr)] items-start gap-4">
        <section className={cardClass}>
          <h2 className="text-[16px] font-bold">{t("stages.looksLike")}</h2>
          <p className="mt-2 text-[13px] text-mut">{localizedName(stage.description, lang)}</p>
          <div className="mt-4 flex h-64 items-center justify-center rounded-xl bg-[#F3F5F3] text-[13px] text-mut">
            {t("stages.noPhoto")}
          </div>
        </section>
        <div className="flex flex-col gap-4">
          <section className={cardClass}>
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-[16px] font-bold">{t("stages.degreeDays")}</h2>
              <SourceTag kind="calculated" />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-[#F7F8F7] px-3 py-3">
                <p className="text-[12px] text-mut">{t("stages.needed")}</p>
                <p className="mt-1 text-[18px] font-bold">
                  {formatNumber(needed, fractionDigits(needed), lang)}{" "}
                  <span className="text-[12px] font-medium text-mut">{t("stages.unitCday")}</span>
                </p>
              </div>
              <div className="rounded-xl bg-[#F7F8F7] px-3 py-3">
                <p className="text-[12px] text-mut">{t("stages.counted")}</p>
                <p className="mt-1 text-[18px] font-bold">
                  {formatNumber(counted, fractionDigits(counted), lang)}{" "}
                  <span className="text-[12px] font-medium text-mut">{t("stages.unitCday")}</span>
                </p>
              </div>
            </div>
            <p className="mt-3 text-[13px]">
              <span className="text-mut">{t("stages.valueFrom")}: </span>
              {valueFrom}
            </p>
          </section>
          <section className={cardClass}>
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-[16px] font-bold">{t("stages.predictedDate")}</h2>
              <StatusTag label={row.label} />
            </div>
            {showDate && row.date !== null ? (
              <>
                <p className="mt-3 text-[20px] font-bold">{formatMediumDate(row.date, lang)}</p>
                {row.earliest !== null && row.latest !== null ? (
                  <p className="mt-1 text-[13px] text-mut">
                    {t("stages.rangeTo", {
                      from: formatAxisDate(row.earliest, lang),
                      to: formatAxisDate(row.latest, lang),
                    })}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="mt-3 text-[13px] text-mut">{t(reasonKey(row.label, row.reason))}</p>
            )}
          </section>
          <section className={cardClass}>
            <h2 className="text-[16px] font-bold">{t("stages.howTitle")}</h2>
            <ol className="mt-2">
              <Step n={formatNumber(1, 0, lang)} text={t("stages.how1")} />
              <Step n={formatNumber(2, 0, lang)} text={t("stages.how2")} />
              <Step
                n={formatNumber(3, 0, lang)}
                text={t("stages.how3", { count: formatNumber(years, 0, lang) })}
              />
            </ol>
          </section>
        </div>
      </div>
      <ConfirmStageDrawer
        open={open}
        onOpenChange={setOpen}
        blockId={blockId}
        year={season.year}
        today={season.today}
        seasonId={timeline?.season.id ?? null}
        stages={catalog.stages.map((item) => ({ id: item.id, name: item.name }))}
        observations={timeline?.observations ?? []}
        stageId={stage.id}
        dateSeen={observed?.observed_on ?? ""}
        share={observed?.share_pct ?? ""}
        lang={lang}
      />
    </div>
  )
}
