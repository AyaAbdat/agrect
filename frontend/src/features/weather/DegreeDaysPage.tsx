import { useQuery } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import { Button } from "@/components/ui/button"
import { activeLang, type BlockDetail } from "../blocks/types"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { UNIT_HOURS } from "../../lib/units"
import { GddChart } from "./charts"
import { asNumber, farmToday, formatAxisDate, formatMediumDate } from "./format"
import { ThresholdsDrawer } from "./ThresholdsDrawer"
import type { DegreeDays, FarmWeather, ForecastOut, GddPoint, GddSetting } from "./types"
import {
  FormulaTip,
  PageHeader,
  PageSkeleton,
  SourceTag,
  WeatherError,
  cardClass,
  outlineBtn,
  primaryBtn,
} from "./ui"

export function DegreeDaysPage() {
  const { t, i18n } = useTranslation()
  const { blockId } = useParams()
  const { currentFarmId } = useAuth()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [open, setOpen] = useState(false)
  const farmId = currentFarmId
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmWeather>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  const forecastQuery = useQuery({
    queryKey: ["weather", farmId, "forecast"],
    queryFn: () => apiGet<ForecastOut>(`/v1/farms/${farmId}/weather/forecast`),
    enabled: farmId !== null,
  })
  const cropId = blockQuery.data?.crop?.id ?? null
  const settingQuery = useQuery({
    queryKey: ["gdd-setting", farmId, cropId],
    queryFn: () => apiGet<GddSetting>(`/v1/farms/${farmId}/gdd-settings/${cropId}`),
    enabled: farmId !== null && cropId !== null,
  })
  const ready = settingQuery.data?.method != null && settingQuery.data.start_date != null
  const degreeQuery = useQuery({
    queryKey: ["weather", farmId, "degree-days", cropId],
    queryFn: () => apiGet<DegreeDays>(`/v1/farms/${farmId}/weather/degree-days?crop_id=${cropId}`),
    enabled: farmId !== null && cropId !== null && ready,
  })

  if (farmId === null || blockId === undefined) return null
  const waitingForSetting = cropId !== null && settingQuery.isPending
  const waitingForDegree = ready && degreeQuery.isPending
  if (
    blockQuery.isPending ||
    farmQuery.isPending ||
    forecastQuery.isPending ||
    waitingForSetting ||
    waitingForDegree
  ) {
    return <PageSkeleton />
  }
  if (
    blockQuery.isError ||
    farmQuery.isError ||
    forecastQuery.isError ||
    settingQuery.isError ||
    degreeQuery.isError ||
    blockQuery.data === undefined ||
    forecastQuery.data === undefined ||
    farmQuery.data === undefined
  ) {
    return <WeatherError farmId={farmId} />
  }

  const today = farmToday(farmQuery.data.timezone)
  const todayRow = forecastQuery.data.daily.find((day) => day.date === today)
  const degree = degreeQuery.data
  const points: GddPoint[] = gddPoints(degree, lang)
  const method = degree?.setting?.method
  const formula = method === "single_sine" ? t("weather.formulaSine") : t("weather.formulaAverage")

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("weather.degreeCrumb")}
        title={t("weather.degreeTitle")}
        sub={t("weather.degreeSub")}
        actions={
          <Link
            to={`/blocks/${blockId}/weather/degree-day-settings`}
            className={`inline-flex items-center ${primaryBtn}`}
          >
            {t("weather.settingsButton")}
          </Link>
        }
      />
      <div className="grid grid-cols-[minmax(0,1fr)_320px] items-start gap-3">
        <section className={cardClass}>
          <h2 className="text-[15px] font-bold">{t("weather.degreeDays")}</h2>
          {ready && degree !== undefined ? (
            <DegreeBody degree={degree} points={points} formula={formula} lang={lang} />
          ) : (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <div className="flex size-12 items-center justify-center rounded-[14px] bg-mint text-pri">
                <Plus className="size-5" aria-hidden="true" />
              </div>
              <p className="text-[16px] font-bold">{t("weather.emptyTitle")}</p>
              <p className="max-w-[380px] text-mut">{t("weather.emptyText")}</p>
              <Link
                to={`/blocks/${blockId}/weather/degree-day-settings`}
                className={`inline-flex items-center ${primaryBtn}`}
              >
                {t("weather.setupButton")}
              </Link>
            </div>
          )}
        </section>
        <div className="flex flex-col gap-3">
          <section className={cardClass}>
            <div className="mb-3 flex items-start justify-between gap-2">
              <h2 className="text-[15px] font-bold">{t("weather.chillCard")}</h2>
              <SourceTag kind="calculated" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-[12px] text-mut">{t("weather.chillHours")}</p>
                <p className="mt-1 text-[20px] font-bold">
                  {formatNumber(degree?.chill.hours_total ?? null, 0, lang)}{" "}
                  <span className="text-[12px] font-medium text-mut">{UNIT_HOURS}</span>
                </p>
              </div>
              <div>
                <p className="text-[12px] text-mut">{t("weather.chillPortions")}</p>
                <p className="mt-1 text-[20px] font-bold">
                  {t("common.missing")}{" "}
                  <span className="text-[12px] font-medium text-mut">{t("weather.portions")}</span>
                </p>
                <span className="mt-1 inline-flex rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
                  {t("weather.phase2")}
                </span>
              </div>
            </div>
            <Button type="button" variant="outline" className={`${outlineBtn} mt-4`} onClick={() => setOpen(true)}>
              {t("weather.setSeason")}
            </Button>
          </section>
          <section className={cardClass}>
            <h2 className="mb-3 text-[15px] font-bold">{t("weather.frostHeat")}</h2>
            <div className="grid grid-cols-2 gap-3">
              <HourTile
                label={t("weather.frostHoursToday")}
                hours={todayRow === undefined ? null : todayRow.frost_h}
                lang={lang}
              />
              <HourTile
                label={t("weather.heatHoursToday")}
                hours={todayRow === undefined ? null : todayRow.heat_h}
                lang={lang}
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="button" variant="outline" className={outlineBtn} onClick={() => setOpen(true)}>
                {t("weather.setFrost")}
              </Button>
              <Button type="button" variant="outline" className={outlineBtn} onClick={() => setOpen(true)}>
                {t("weather.setHeat")}
              </Button>
            </div>
          </section>
        </div>
      </div>
      <ThresholdsDrawer farmId={farmId} open={open} onOpenChange={setOpen} />
    </div>
  )
}

function DegreeBody({
  degree,
  points,
  formula,
  lang,
}: {
  degree: DegreeDays
  points: GddPoint[]
  formula: string
  lang: string
}) {
  const { t } = useTranslation()
  const setting = degree.setting
  const method =
    setting?.method === "single_sine" ? t("weather.singleSine") : t("weather.simpleAverage")
  return (
    <div className="mt-3">
      <p className="text-[13px] text-mut">
        {t("weather.settingSummary", {
          base: formatNumber(asNumber(setting?.base_c), 1, lang),
          upper: formatNumber(asNumber(setting?.upper_c), 1, lang),
          method,
          since: formatMediumDate(degree.from, lang),
        })}
      </p>
      <p className="mt-3 flex items-center gap-2">
        <span className="text-[40px] font-bold leading-none">
          {formatNumber(asNumber(degree.gdd_total), 1, lang)}
        </span>
        <span className="text-[16px] font-semibold text-mut">{t("weather.unitCday")}</span>
        <SourceTag kind="calculated" />
        <FormulaTip text={formula} />
      </p>
      <div className="mt-4">
        <GddChart points={points} lang={lang} />
      </div>
      {degree.data_from !== null && degree.data_from > degree.from ? (
        <p className="mt-2 text-[12px] text-mut">
          {t("weather.dataFrom", { date: formatMediumDate(degree.data_from, lang) })}
        </p>
      ) : null}
    </div>
  )
}

function HourTile({
  label,
  hours,
  lang,
}: {
  label: string
  hours: number | null
  lang: string
}) {
  return (
    <div>
      <p className="text-[12px] text-mut">{label}</p>
      <p className="mt-1 flex items-center gap-2 text-[20px] font-bold">
        {formatNumber(hours, 0, lang)}{" "}
        <span className="text-[12px] font-medium text-mut">{UNIT_HOURS}</span>
        {hours !== null ? <SourceTag kind="calculated" /> : null}
      </p>
    </div>
  )
}

function gddPoints(degree: DegreeDays | undefined, lang: string): GddPoint[] {
  if (degree === undefined) return []
  let lastPast = -1
  degree.days.forEach((day, index) => {
    if (!day.is_forecast) lastPast = index
  })
  const hasForecast = degree.days.some((day) => day.is_forecast)
  return degree.days.map((day, index) => {
    const cumulative = asNumber(day.gdd_cum)
    const onForecast =
      hasForecast && (lastPast < 0 || index >= lastPast)
    return {
      label: formatAxisDate(day.date, lang),
      past: index <= lastPast ? cumulative : null,
      forecast: onForecast ? cumulative : null,
      daily: asNumber(day.gdd),
    }
  })
}
