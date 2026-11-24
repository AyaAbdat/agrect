import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { UNIT_MM } from "../../lib/units"
import { activeLang, type BlockDetail } from "../blocks/types"
import { OptionalTag } from "../blocks/wizard/wizardUi"
import { asNumber, formatMediumDate } from "../weather/format"
import {
  FormulaTip,
  LoadError,
  PageHeader,
  PageSkeleton,
  SourceTag,
  cardClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { WaterChart, hasChartData, waterPoints } from "./chart"
import { balanceNote, efficiencyPercent, formatEventDate, mm2, runParts, show } from "./display"
import { LogIrrigationDrawer } from "./LogIrrigationDrawer"
import type {
  FarmClock,
  ForecastRain,
  IrrigationEvents,
  IrrigationSettings,
  IrrigationToday,
  SoilProfile,
} from "./types"
import { useWaterLeftNow } from "./waterLeft"

export function SoilWaterPage() {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const { blockId } = useParams()
  const { currentFarmId } = useAuth()
  const [logOpen, setLogOpen] = useState(false)
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const farmId = currentFarmId
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
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
  const settingsQuery = useQuery({
    queryKey: ["irrigation-settings", blockId],
    queryFn: () => apiGet<IrrigationSettings>(`/v1/blocks/${blockId}/irrigation-settings`),
    enabled: blockId !== undefined,
  })
  const todayQuery = useQuery({
    queryKey: ["irrigation-today", blockId],
    queryFn: () => apiGet<IrrigationToday>(`/v1/blocks/${blockId}/irrigation-today`),
    enabled: blockId !== undefined,
  })
  const eventsQuery = useQuery({
    queryKey: ["irrigation-events", blockId, 1],
    queryFn: () => apiGet<IrrigationEvents>(`/v1/blocks/${blockId}/irrigation-events?limit=1`),
    enabled: blockId !== undefined,
  })
  const waterLeft = useWaterLeftNow(blockId)
  const balanceQuery = waterLeft.balanceQuery
  const today = waterLeft.today
  const forecastQuery = useQuery({
    queryKey: ["weather", farmId, "forecast"],
    queryFn: () => apiGet<ForecastRain>(`/v1/farms/${farmId}/weather/forecast`),
    enabled: farmId !== null,
  })

  if (blockId === undefined || farmId === null) return null
  const loading =
    farmQuery.isPending ||
    blockQuery.isPending ||
    soilQuery.isPending ||
    settingsQuery.isPending ||
    todayQuery.isPending ||
    eventsQuery.isPending ||
    balanceQuery.isLoading ||
    forecastQuery.isLoading
  if (loading) return <PageSkeleton />
  const failed =
    farmQuery.isError ||
    blockQuery.isError ||
    soilQuery.isError ||
    settingsQuery.isError ||
    todayQuery.isError ||
    eventsQuery.isError ||
    balanceQuery.isError ||
    farmQuery.data === undefined ||
    blockQuery.data === undefined ||
    soilQuery.data === undefined ||
    settingsQuery.data === undefined ||
    todayQuery.data === undefined ||
    eventsQuery.data === undefined ||
    balanceQuery.data === undefined
  if (failed) {
    return (
      <LoadError
        onRetry={() => {
          void queryClient.invalidateQueries({ queryKey: ["soil", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["irrigation-settings", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["irrigation-today", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["irrigation-events", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["water-balance", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["farm", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["block", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["weather", farmId, "forecast"] })
        }}
      />
    )
  }

  const soil = soilQuery.data
  const settings = settingsQuery.data
  const advice = todayQuery.data
  const balance = balanceQuery.data
  const zone = farmQuery.data.timezone
  const base = `/blocks/${blockId}/soil-water`
  const missing = new Set(advice.missing)
  const dose = advice.recommended === "refill" ? advice.refill : advice.maintain
  const other = advice.recommended === "refill" ? advice.maintain : advice.refill
  const otherKey = advice.recommended === "refill" ? "soil.maintainOther" : "soil.refillOther"
  const run = runParts(dose.run_time_min, lang)
  const otherRun = runParts(other.run_time_min, lang)
  const points = waterPoints(balance.rows, lang)
  const chartReady = hasChartData(points)
  const notes = balance.notes
    .map((note) => balanceNote(note, lang, t))
    .filter((note): note is string => note !== null)
  const balanceToday = balance.rows.find((row) => row.date === advice.date)
  const waterNow = waterLeft.row
  const forecastToday = forecastQuery.data?.daily.find((day) => day.date === advice.date)
  const rain = balanceToday?.rain_mm ?? forecastToday?.rain_mm ?? null
  const latest = eventsQuery.data.events[0]
  const latestRun = latest === undefined ? null : runParts(latest.duration_min, lang)

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("soil.crumb", { block: blockQuery.data.name })}
        title={t("soil.title")}
        sub={t("soil.sub")}
        actions={
          <>
            <Link to={`${base}/settings`} className={`inline-flex items-center ${outlineBtn}`}>
              {t("soil.settingsButton")}
            </Link>
            <button type="button" className={primaryBtn} onClick={() => setLogOpen(true)}>
              {t("soil.logButton")}
            </button>
          </>
        }
      />
      {soil.label === "not_enough_data" ? (
        <Banner
          title={t("soil.bannerSoilTitle")}
          text={t("soil.bannerSoilText")}
          action={t("soil.setupSoil")}
          to={`${base}/soil`}
        />
      ) : null}
      {missing.has("irrigation.kc_missing") || missing.has("irrigation.efficiency_missing") ? (
        <Banner
          title={t("soil.bannerSettingsTitle")}
          text={t("soil.bannerSettingsText")}
          action={t("soil.setupIrrigation")}
          to={`${base}/settings`}
        />
      ) : null}
      <div className="grid grid-cols-[minmax(0,1.5fr)_minmax(280px,0.85fr)] items-start gap-3">
        <section className={cardClass}>
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-[15px] font-bold">{t("soil.waterLeftTitle")}</h2>
            <SourceTag kind="calculated" />
          </div>
          <p className="mt-3 text-[28px] font-bold leading-tight">
            {t("soil.waterLeftLine", {
              left: mm2(waterNow?.water_left_mm, lang),
              taw: show(waterNow?.taw_mm ?? advice.taw_mm, lang),
            })}
          </p>
          {waterNow !== undefined ? (
            <p className="mt-1 text-[13px] text-mut">
              {t("soil.waterLeftAsOf", { date: formatMediumDate(waterNow.date, lang) })}
            </p>
          ) : null}
          <p className="mt-1 text-[13px] text-mut">
            {t("soil.irrigateBelow", { value: show(waterNow?.irrigate_below_mm, lang) })}
          </p>
          <div className="mt-4">
            {chartReady ? (
              <WaterChart
                points={points}
                lang={lang}
                threshold={asNumber(waterNow?.irrigate_below_mm)}
                thresholdLabel={t("soil.legendThreshold")}
              />
            ) : (
              <div className="flex h-[220px] items-center justify-center text-[13px] text-mut">
                {t("soil.noData")}
              </div>
            )}
          </div>
          {notes.length > 0 ? (
            <ul className="mt-3 flex flex-col gap-1 text-[12px] text-mut">
              {notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}
        </section>
        <div className="flex flex-col gap-3">
          <section className={cardClass}>
            <h2 className="text-[15px] font-bold">{t("soil.today")}</h2>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <Tile
                label={t("soil.etc")}
                value={show(advice.etc_today_mm, lang)}
                unit={UNIT_MM}
                source="calculated"
              />
              <Tile label={t("soil.rain")} value={show(rain, lang)} unit={UNIT_MM} source="estimated" />
            </div>
          </section>
          <section className={cardClass}>
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-[15px] font-bold">{t("soil.applyTitle")}</h2>
              <span className="flex items-center gap-2">
                <StatusTag status={advice.status} />
                <SourceTag kind="calculated" />
                <FormulaTip text={t("soil.formula")} />
              </span>
            </div>
            <p className="mt-3 text-[18px] font-bold leading-snug">
              {t("soil.applyLine", {
                net: show(dose.net_mm, lang),
                gross: show(dose.gross_mm, lang),
              })}
            </p>
            <p className="mt-1 text-[13px]">
              {t("soil.runTime", { hours: run.hours, minutes: run.minutes })}
            </p>
            <p className="mt-1 text-[13px]">
              {t("soil.efficiencyLine", { value: efficiencyPercent(settings.efficiency, lang) })}
            </p>
            <p className="mt-3 text-[12px] text-mut">
              {t(otherKey, {
                gross: show(other.gross_mm, lang),
                hours: otherRun.hours,
                minutes: otherRun.minutes,
              })}
            </p>
          </section>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-3">
        <section className={`${cardClass} flex flex-col justify-between gap-3`}>
          <div>
            <h2 className="text-[15px] font-bold">{t("soil.lastTitle")}</h2>
            <p className="mt-2 text-[13px] text-mut">
              {latest === undefined || latestRun === null
                ? t("soil.lastEmpty")
                : t("soil.lastLine", {
                    date: formatEventDate(latest.start_at, zone, lang),
                    hours: latestRun.hours,
                    minutes: latestRun.minutes,
                    depth: show(latest.depth_mm, lang),
                    volume: show(latest.volume_m3, lang),
                  })}
            </p>
          </div>
          <button type="button" className={outlineBtn} onClick={() => setLogOpen(true)}>
            {t("soil.logButton")}
          </button>
        </section>
        <LinkCard
          title={t("soil.logTitle")}
          text={t("soil.logText")}
          action={t("soil.openLog")}
          to={`${base}/log`}
        />
        <LinkCard
          title={t("soil.balanceTitle")}
          text={t("soil.balanceText")}
          action={t("soil.openBalance")}
          to={`${base}/balance`}
        />
        <section className={`${cardClass} flex flex-col justify-between gap-3`}>
          <div>
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-[15px] font-bold">{t("soil.checkTitle")}</h2>
              <OptionalTag />
            </div>
            <p className="mt-2 text-[13px] text-mut">{t("soil.checkText")}</p>
          </div>
          <Link to={`${base}/soil-check`} className={`inline-flex w-fit items-center ${outlineBtn}`}>
            {t("soil.checkSoil")}
          </Link>
        </section>
      </div>
      <LogIrrigationDrawer
        open={logOpen}
        onOpenChange={setLogOpen}
        blockId={blockId}
        blockName={blockQuery.data.name}
        valves={blockQuery.data.valves}
        timeZone={zone}
        today={today ?? advice.date}
        event={null}
      />
    </div>
  )
}

function Banner({
  title,
  text,
  action,
  to,
}: {
  title: string
  text: string
  action: string
  to: string
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl bg-[#FEF3C7] px-4 py-3">
      <div>
        <p className="text-[13px] font-semibold text-amb">{title}</p>
        <p className="text-[13px] text-amb">{text}</p>
      </div>
      <Link to={to} className={`inline-flex items-center ${outlineBtn}`}>
        {action}
      </Link>
    </div>
  )
}

function Tile({
  label,
  value,
  unit,
  source,
}: {
  label: string
  value: string
  unit: string
  source: "calculated" | "estimated"
}) {
  return (
    <div className="rounded-xl bg-[#F7F8F7] p-3">
      <p className="text-[12px] text-mut">{label}</p>
      <p className="mt-1 text-[20px] font-bold">
        {value} <span className="text-[12px] font-medium text-mut">{unit}</span>
      </p>
      <span className="mt-2 inline-flex">
        <SourceTag kind={source} />
      </span>
    </div>
  )
}

function StatusTag({ status }: { status: IrrigationToday["status"] }) {
  const { t } = useTranslation()
  if (status === "no_data") return null
  const soon = status === "irrigate_soon"
  return (
    <span
      className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
        soon ? "bg-[#FEF3C7] text-amb" : "bg-mint text-pri"
      }`}
    >
      {t(soon ? "soil.statusSoon" : "soil.statusOk")}
    </span>
  )
}

function LinkCard({
  title,
  text,
  action,
  to,
}: {
  title: string
  text: string
  action: string
  to: string
}) {
  return (
    <section className={`${cardClass} flex flex-col justify-between gap-3`}>
      <div>
        <h2 className="text-[15px] font-bold">{title}</h2>
        <p className="mt-2 text-[13px] text-mut">{text}</p>
      </div>
      <Link to={to} className={`inline-flex w-fit items-center ${outlineBtn}`}>
        {action}
      </Link>
    </section>
  )
}
