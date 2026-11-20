import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { UNIT_MM } from "../../lib/units"
import { activeLang, type BlockDetail } from "../blocks/types"
import { asNumber, formatMediumDate } from "../weather/format"
import {
  ChoiceChip,
  LoadError,
  PageHeader,
  PageSkeleton,
  SourceTag,
  cardClass,
  outlineBtn,
} from "../weather/ui"
import { WaterChart, hasChartData, waterPoints } from "./chart"
import { mm2 } from "./display"
import type { WaterPeriod } from "./period"
import type { WaterBalance } from "./types"

const periods: { id: WaterPeriod; labelKey: "soil.balanceWeek" | "soil.balanceMonth" | "soil.balanceSeason" }[] = [
  { id: "week", labelKey: "soil.balanceWeek" },
  { id: "month", labelKey: "soil.balanceMonth" },
  { id: "season", labelKey: "soil.balanceSeason" },
]

export function WaterBalancePage() {
  const { t, i18n } = useTranslation()
  const { blockId } = useParams()
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [period, setPeriod] = useState<WaterPeriod>("week")
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const balanceQuery = useQuery({
    queryKey: ["water-balance", blockId, period],
    queryFn: () => apiGet<WaterBalance>(`/v1/blocks/${blockId}/water-balance?period=${period}`),
    enabled: blockId !== undefined,
  })

  if (blockId === undefined || currentFarmId === null) return null
  if (blockQuery.isPending || balanceQuery.isPending) return <PageSkeleton />
  if (
    blockQuery.isError ||
    balanceQuery.isError ||
    blockQuery.data === undefined ||
    balanceQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void queryClient.invalidateQueries({ queryKey: ["block", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["water-balance", blockId] })
        }}
      />
    )
  }

  const rows = balanceQuery.data.rows
  const points = waterPoints(rows, lang)
  const chartReady = hasChartData(points)
  const threshold = [...rows]
    .reverse()
    .map((row) => asNumber(row.irrigate_below_mm))
    .find((value) => value !== null)
  const missing = t("common.missing")
  const formulas = [
    { title: "soil.howSoilTodayTitle", body: "soil.howSoilTodayBody" },
    { title: "soil.howDrainTitle", body: "soil.howDrainBody" },
    { title: "soil.howCropBalanceTitle", body: "soil.howCropBalanceBody" },
    { title: "soil.howSoonTitle", body: "soil.howSoonBody" },
  ] as const

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("soil.setupCrumb")}
        title={t("soil.balanceTitle")}
        sub={t("soil.balancePageSub", { block: blockQuery.data.name })}
        actions={
          <Link
            to={`/blocks/${blockId}/soil-water`}
            className={`inline-flex items-center ${outlineBtn}`}
          >
            {t("soil.back")}
          </Link>
        }
      />
      <div className="flex flex-wrap gap-2">
        {periods.map((item) => (
          <ChoiceChip key={item.id} selected={period === item.id} onClick={() => setPeriod(item.id)}>
            {t(item.labelKey)}
          </ChoiceChip>
        ))}
      </div>
      <section className={cardClass}>
        <h2 className="text-[15px] font-bold">{t("soil.soilWaterChart")}</h2>
        <p className="mt-1 text-[13px] text-mut">{t("soil.chartSub")}</p>
        <div className="mt-4">
          {chartReady ? (
            <WaterChart
              points={points}
              lang={lang}
              threshold={threshold ?? null}
              thresholdLabel={t("soil.legendThreshold")}
            />
          ) : (
            <div className="flex h-[220px] items-center justify-center text-[13px] text-mut">
              {t("soil.noData")}
            </div>
          )}
        </div>
      </section>
      <div className="grid grid-cols-[minmax(0,1.6fr)_minmax(260px,0.8fr)] items-start gap-3">
        <section className={cardClass}>
          <h2 className="text-[15px] font-bold">{t("soil.dayByDay")}</h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[640px] text-start text-[13px]">
              <thead className="text-[11px] uppercase tracking-wide text-mut">
                <tr className="border-b border-line">
                  <th className="py-2 text-start font-semibold">{t("soil.colDate")}</th>
                  <th className="py-2 text-start font-semibold">{t("soil.colEtc")}</th>
                  <th className="py-2 text-start font-semibold">{t("soil.colRain")}</th>
                  <th className="py-2 text-start font-semibold">{t("soil.colIrrigation")}</th>
                  <th className="py-2 text-start font-semibold">{t("soil.colSoilWater")}</th>
                  <th className="py-2 text-start font-semibold">{t("soil.colStatus")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td className="py-3">{missing}</td>
                    <td className="py-3">{missing} {UNIT_MM}</td>
                    <td className="py-3">{missing} {UNIT_MM}</td>
                    <td className="py-3">{missing} {UNIT_MM}</td>
                    <td className="py-3">{missing} {UNIT_MM}</td>
                    <td className="py-3">{missing}</td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr
                      key={row.date}
                      className={`border-b border-line last:border-b-0 ${row.is_forecast ? "text-mut" : ""}`}
                    >
                      <td className="py-3">{formatMediumDate(row.date, lang)}</td>
                      <td className="py-3">{mm2(row.etc_mm, lang)} {UNIT_MM}</td>
                      <td className="py-3">{mm2(row.rain_mm, lang)} {UNIT_MM}</td>
                      <td className="py-3">{mm2(row.irrigation_soil_mm, lang)} {UNIT_MM}</td>
                      <td className="py-3">{mm2(row.water_left_mm, lang)} {UNIT_MM}</td>
                      <td className="py-3">
                        <BalanceStatus forecast={row.is_forecast} status={row.status} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
        <section className={cardClass}>
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-[15px] font-bold">{t("soil.howCalculated")}</h2>
            <SourceTag kind="calculated" />
          </div>
          <div className="mt-3">
            {formulas.map((item, index) => (
              <div
                key={item.title}
                className={index < formulas.length - 1 ? "border-b border-line py-3 first:pt-0" : "pt-3"}
              >
                <p className="text-[14px] font-semibold">{t(item.title)}</p>
                <p className="mt-1 text-[12px] text-mut">{t(item.body)}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

function BalanceStatus({
  forecast,
  status,
}: {
  forecast: boolean
  status: "ok" | "irrigate_soon" | "no_data"
}) {
  const { t } = useTranslation()
  if (forecast) {
    return (
      <span className="inline-flex rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
        {t("soil.statusForecast")}
      </span>
    )
  }
  if (status === "ok") {
    return (
      <span className="inline-flex rounded-full bg-mint px-2 py-0.5 text-[10px] font-semibold text-pri">
        {t("soil.statusOk")}
      </span>
    )
  }
  if (status === "irrigate_soon") {
    return (
      <span className="inline-flex rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[10px] font-semibold text-amb">
        {t("soil.statusSoon")}
      </span>
    )
  }
  return (
    <span className="inline-flex rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
      {t("soil.statusNotSet")}
    </span>
  )
}
