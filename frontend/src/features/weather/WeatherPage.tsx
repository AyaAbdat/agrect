import { useQuery } from "@tanstack/react-query"
import { useState, type ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import { Button } from "@/components/ui/button"
import { Drawer } from "../../components/Drawer"
import { activeLang, cropLabel, type BlockDetail } from "../blocks/types"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import {
  UNIT_HOURS,
  UNIT_MM,
  UNIT_RADIATION_W_M2,
  UNIT_TEMP_C,
  UNIT_VPD_KPA,
  UNIT_WIND_M_S,
} from "../../lib/units"
import { HourChart, HistoryChart } from "./charts"
import {
  asNumber,
  farmToday,
  formatAxisDate,
  formatHour,
  formatWeekdayDate,
  shiftIsoDate,
} from "./format"
import { ThresholdsDrawer } from "./ThresholdsDrawer"
import type {
  BlockGddSetting,
  DailyOut,
  DegreeDays,
  FarmWeather,
  ForecastDay,
  ForecastOut,
  GddSetting,
  HistoryPoint,
  HourPoint,
  NowOut,
} from "./types"
import {
  BlockOverrideTag,
  PageHeader,
  PageSkeleton,
  SourceTag,
  StatusBanner,
  WeatherError,
  cardClass,
  outlineBtn,
} from "./ui"

function show(value: string | number | null | undefined, digits: number, lang: string): string {
  return formatNumber(asNumber(value), digits, lang)
}

export function WeatherPage() {
  const { t, i18n } = useTranslation()
  const { blockId } = useParams()
  const { currentFarmId } = useAuth()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [thresholdsOpen, setThresholdsOpen] = useState(false)
  const farmId = currentFarmId
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmWeather>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const nowQuery = useQuery({
    queryKey: ["weather", farmId, "now"],
    queryFn: () => apiGet<NowOut>(`/v1/farms/${farmId}/weather/now`),
    enabled: farmId !== null,
    refetchInterval: 10 * 60 * 1000,
  })
  const forecastQuery = useQuery({
    queryKey: ["weather", farmId, "forecast"],
    queryFn: () => apiGet<ForecastOut>(`/v1/farms/${farmId}/weather/forecast`),
    enabled: farmId !== null,
    refetchInterval: 10 * 60 * 1000,
  })
  const today = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)
  const dailyQuery = useQuery({
    queryKey: ["weather", farmId, "daily", today],
    queryFn: () =>
      apiGet<DailyOut>(
        `/v1/farms/${farmId}/weather/daily?from=${shiftIsoDate(today ?? "", -30)}&to=${shiftIsoDate(today ?? "", -1)}`,
      ),
    enabled: farmId !== null && today !== null,
  })
  const cropId = blockQuery.data?.crop?.id ?? null
  const blockSettingQuery = useQuery({
    queryKey: ["block-gdd-setting", blockId],
    queryFn: () => apiGet<BlockGddSetting>(`/v1/blocks/${blockId}/gdd-setting`),
    enabled: blockId !== undefined,
  })
  const settingQuery = useQuery({
    queryKey: ["gdd-setting", farmId, cropId],
    queryFn: () => apiGet<GddSetting>(`/v1/farms/${farmId}/gdd-settings/${cropId}`),
    enabled: farmId !== null && cropId !== null,
  })
  const blockSetting = blockSettingQuery.data
  const override =
    blockSetting !== undefined && blockSetting.method !== null ? blockSetting : null
  const effectiveMethod = override !== null ? override.method : settingQuery.data?.method
  const effectiveStart = override !== null ? override.start_date : settingQuery.data?.start_date
  const hasSetting = effectiveMethod != null && effectiveStart != null
  const degreeQuery = useQuery({
    queryKey: ["weather", farmId, "degree-days", cropId, blockId],
    queryFn: () =>
      apiGet<DegreeDays>(
        `/v1/farms/${farmId}/weather/degree-days?crop_id=${cropId}&block_id=${blockId}`,
      ),
    enabled: farmId !== null && cropId !== null && blockId !== undefined && hasSetting,
  })

  if (farmId === null || blockId === undefined) return null
  const loading =
    farmQuery.isPending ||
    blockQuery.isPending ||
    nowQuery.isPending ||
    forecastQuery.isPending ||
    dailyQuery.isLoading
  if (loading) return <PageSkeleton />
  const failed =
    farmQuery.isError ||
    blockQuery.isError ||
    nowQuery.isError ||
    forecastQuery.isError ||
    dailyQuery.isError ||
    blockSettingQuery.isError ||
    farmQuery.data === undefined ||
    blockQuery.data === undefined ||
    nowQuery.data === undefined ||
    forecastQuery.data === undefined ||
    dailyQuery.data === undefined
  if (failed) return <WeatherError farmId={farmId} />

  const farm = farmQuery.data
  const now = nowQuery.data
  const forecast = forecastQuery.data
  const daily = dailyQuery.data
  const zone = farm.timezone
  const todayRow = forecast.daily.find((day) => day.date === today)
  const time = now.issued_at === null ? t("common.missing") : formatHour(now.issued_at, zone)
  const hours: HourPoint[] = forecast.hourly.map((hour) => ({
    label: formatHour(hour.ts, zone),
    temp: asNumber(hour.temp_c),
    rain: asNumber(hour.rain_mm),
    rh: asNumber(hour.rh_pct),
    wind: asNumber(hour.wind_ms),
  }))
  const history: HistoryPoint[] = daily.days.map((day) => ({
    label: formatAxisDate(day.date, lang),
    tmin: asNumber(day.tmin_c),
    tmax: asNumber(day.tmax_c),
    rain: asNumber(day.rain_mm),
  }))
  const crop = cropLabel(blockQuery.data.crop, lang) ?? t("common.missing")
  const degree = degreeQuery.data
  const stale = now.stale || forecast.stale

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("weather.crumb")}
        title={t("weather.title")}
        sub={t("weather.sub")}
        actions={
          <>
            <Button type="button" variant="outline" className={outlineBtn} onClick={() => setSourceOpen(true)}>
              {t("weather.sourceButton")}
            </Button>
            <Link to="/alerts" className={`inline-flex items-center ${outlineBtn}`}>
              {t("top.alerts")}
            </Link>
          </>
        }
      />
      <StatusBanner stale={stale} time={time} />
      <div className="grid grid-cols-[240px_minmax(0,1fr)] gap-3">
        <section className={`${cardClass} flex flex-col justify-between`}>
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-[15px] font-bold">{t("weather.now")}</h2>
            <SourceTag kind="estimated" />
          </div>
          <p className="text-[40px] font-bold leading-none">
            {show(now.temp_c, 1, lang)}
            <span className="ms-1 text-[16px] font-semibold text-mut">{UNIT_TEMP_C}</span>
          </p>
          <p className="text-[13px] text-mut">
            {t("weather.todayMinMax", {
              min: show(todayRow?.tmin_c, 1, lang),
              max: show(todayRow?.tmax_c, 1, lang),
            })}
          </p>
        </section>
        <div className="grid grid-cols-4 gap-3">
          <Tile label={t("weather.humidity")} value={show(now.rh_pct, 0, lang)} unit="%" source="estimated" />
          <Tile label={t("weather.vpd")} value={show(now.vpd_kpa, 2, lang)} unit={UNIT_VPD_KPA} source="calculated" />
          <Tile
            label={t("weather.wind")}
            value={show(now.wind_ms, 1, lang)}
            unit={UNIT_WIND_M_S}
            source="estimated"
            extra={
              <p className="text-[11px] text-mut">
                {t("weather.gusts", { value: show(now.gust_ms, 1, lang) })}
              </p>
            }
          />
          <Tile label={t("weather.rainToday")} value={show(now.rain_mm, 1, lang)} unit={UNIT_MM} source="estimated" />
          <Tile label={t("weather.solar")} value={show(now.rad_wm2, 0, lang)} unit={UNIT_RADIATION_W_M2} source="estimated" />
          <Tile label={t("weather.et0Today")} value={show(now.et0_mm, 2, lang)} unit={UNIT_MM} source="estimated" />
          <Tile label={t("weather.dewPoint")} value={show(now.dewpoint_c, 1, lang)} unit={UNIT_TEMP_C} source="calculated" />
          <FrostTile
            hours={todayRow === undefined ? undefined : todayRow.frost_h}
            lang={lang}
            onSet={() => setThresholdsOpen(true)}
          />
        </div>
      </div>
      <div className="grid grid-cols-[minmax(0,1.45fr)_minmax(280px,0.9fr)] gap-3">
        <section className={cardClass}>
          <div className="mb-3 flex items-start justify-between gap-2">
            <div>
              <h2 className="text-[15px] font-bold">{t("weather.next48")}</h2>
              <p className="text-[12px] text-mut">{t("weather.hourlyForecast")}</p>
            </div>
            <SourceTag kind="estimated" />
          </div>
          <HourChart points={hours} lang={lang} />
        </section>
        <section className={cardClass}>
          <div className="mb-2 flex items-start justify-between gap-2">
            <h2 className="text-[15px] font-bold">{t("weather.next7")}</h2>
            <SourceTag kind="estimated" />
          </div>
          {forecast.daily.length === 0 ? (
            <p className="py-8 text-center text-[13px] text-mut">{t("weather.noData")}</p>
          ) : (
            <div>
              {forecast.daily.map((day) => (
                <DayRow key={day.date} day={day} lang={lang} />
              ))}
            </div>
          )}
        </section>
      </div>
      <section className={cardClass}>
        <div className="mb-2 flex items-start justify-between gap-2">
          <h2 className="text-[15px] font-bold">{t("weather.last30")}</h2>
          <SourceTag kind="estimated" />
        </div>
        <HistoryChart points={history} lang={lang} />
        <p className="mt-2 text-[12px] text-mut">{t("weather.dailyCaption")}</p>
      </section>
      <div className="grid grid-cols-2 gap-3">
        <section className={cardClass}>
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-[15px] font-bold">{t("weather.degreeCard")}</h2>
            <Link to={`/blocks/${blockId}/weather/degree-days`} className="text-[13px] font-semibold text-pri">
              {t("weather.open")}
            </Link>
          </div>
          <p className="mt-3 flex flex-wrap items-center gap-2 font-semibold">
            <span>{crop}</span>
            {degree?.setting?.override === true ? <BlockOverrideTag /> : null}
          </p>
          <p className="mt-2 flex items-center gap-2 text-[22px] font-bold">
            {show(degree?.gdd_total, 1, lang)}
            <span className="text-[13px] font-medium text-mut">{t("weather.unitCday")}</span>
            <SourceTag kind="calculated" />
          </p>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-[13px]">
            <span className="text-mut">{t("weather.chillSeasonLine")}</span>
            <span className="font-semibold">
              {formatNumber(degree?.chill.hours_total ?? null, 0, lang)} {UNIT_HOURS}
            </span>
            <SourceTag kind="calculated" />
          </p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-[13px]">
            <span className="text-mut">{t("weather.chillPortions")}</span>
            <span className="font-semibold">
              {formatNumber(asNumber(degree?.chill.portions_total ?? null), 1, lang)}{" "}
              {t("weather.portions")}
            </span>
            {degree?.chill.portions_total != null ? <SourceTag kind="calculated" /> : null}
          </p>
        </section>
        <section className={cardClass}>
          <h2 className="text-[15px] font-bold">{t("weather.alertsCard")}</h2>
          <p className="mt-3 text-mut">{t("weather.alertsPhase2")}</p>
        </section>
      </div>
      <Drawer
        open={sourceOpen}
        onOpenChange={setSourceOpen}
        crumb={t("weather.crumb")}
        title={t("weather.sourceTitle")}
      >
        <p className="text-[13px] leading-relaxed">
          {t("weather.sourceBody", {
            lat: show(farm.lat, 5, lang),
            lon: show(farm.lon, 5, lang),
          })}
        </p>
        <p className="mt-3 text-[13px] text-mut">{t("weather.updated", { time })}</p>
      </Drawer>
      <ThresholdsDrawer farmId={farmId} open={thresholdsOpen} onOpenChange={setThresholdsOpen} />
    </div>
  )
}

function Tile({
  label,
  value,
  unit,
  source,
  extra,
}: {
  label: string
  value: string
  unit: string
  source: "estimated" | "calculated"
  extra?: ReactNode
}) {
  return (
    <div className={`${cardClass} flex min-h-[96px] flex-col gap-1 p-3`}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-[12px] text-mut">{label}</span>
        <SourceTag kind={source} />
      </div>
      <p className="text-[18px] font-bold leading-tight">
        {value} <span className="text-[12px] font-medium text-mut">{unit}</span>
      </p>
      {extra}
    </div>
  )
}

function FrostTile({
  hours,
  lang,
  onSet,
}: {
  hours: number | null | undefined
  lang: string
  onSet: () => void
}) {
  const { t } = useTranslation()
  const missing = hours === null || hours === undefined
  return (
    <div className={`${cardClass} flex min-h-[96px] flex-col gap-1 p-3`}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-[12px] text-mut">{t("weather.frostHoursToday")}</span>
        {missing ? null : <SourceTag kind="calculated" />}
      </div>
      <p className="text-[18px] font-bold leading-tight">
        {formatNumber(hours ?? null, 0, lang)}{" "}
        <span className="text-[12px] font-medium text-mut">{UNIT_HOURS}</span>
      </p>
      {hours === null ? (
        <button type="button" className="text-start text-[12px] font-semibold text-pri" onClick={onSet}>
          {t("weather.setFrost")}
        </button>
      ) : null}
    </div>
  )
}

function DayRow({ day, lang }: { day: ForecastDay; lang: string }) {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-between gap-2 border-b border-line py-2 text-[13px] last:border-b-0">
      <span className="shrink-0">{formatWeekdayDate(day.date, lang)}</span>
      <span className="flex min-w-0 flex-wrap items-center justify-end gap-1.5">
        <span>
          {t("weather.dayLine", {
            min: show(day.tmin_c, 1, lang),
            max: show(day.tmax_c, 1, lang),
            rain: show(day.rain_mm, 1, lang),
          })}
        </span>
        {day.frost_h !== null && day.frost_h > 0 ? (
          <span className="rounded-full bg-[#FEF3C7] px-1.5 py-0.5 text-[10px] font-semibold text-amb">
            {t("weather.frostTag", { hours: formatNumber(day.frost_h, 0, lang) })}
          </span>
        ) : null}
        {day.heat_h !== null && day.heat_h > 0 ? (
          <span className="rounded-full bg-[#FEE2E2] px-1.5 py-0.5 text-[10px] font-semibold text-red">
            {t("weather.heatTag", { hours: formatNumber(day.heat_h, 0, lang) })}
          </span>
        ) : null}
      </span>
    </div>
  )
}
