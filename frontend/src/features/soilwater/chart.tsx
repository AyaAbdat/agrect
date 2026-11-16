import { useTranslation } from "react-i18next"
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { formatNumber } from "../../lib/format"
import { UNIT_MM } from "../../lib/units"
import { asNumber, formatAxisDate } from "../weather/format"
import { ChartLegend } from "../weather/ui"
import type { BalanceRow } from "./types"

const PRI = "#1B4332"
const RAIN = "#7EB6D9"
const IRRIGATION = "#40916C"
const AMBER = "#b45309"
const tick = { fontSize: 11, fill: "#6B7280" }

export type WaterPoint = {
  label: string
  past: number | null
  forecast: number | null
  rain: number | null
  irrigation: number | null
}

export function waterPoints(rows: BalanceRow[], lang: string): WaterPoint[] {
  let lastPast = -1
  rows.forEach((row, index) => {
    if (!row.is_forecast) lastPast = index
  })
  const hasForecast = rows.some((row) => row.is_forecast)
  return rows.map((row, index) => {
    const left = asNumber(row.water_left_mm)
    const onForecast = hasForecast && (lastPast < 0 || index >= lastPast)
    return {
      label: formatAxisDate(row.date, lang),
      past: index <= lastPast ? left : null,
      forecast: onForecast ? left : null,
      rain: asNumber(row.rain_mm),
      irrigation: asNumber(row.irrigation_soil_mm),
    }
  })
}

export function hasChartData(points: WaterPoint[]): boolean {
  return points.some(
    (point) =>
      point.past !== null ||
      point.forecast !== null ||
      point.rain !== null ||
      point.irrigation !== null,
  )
}

function depthDomain(points: WaterPoint[]): number {
  let peak = 0
  for (const point of points) {
    peak = Math.max(peak, point.rain ?? 0, point.irrigation ?? 0)
  }
  return Math.max(5, Math.ceil(peak <= 0 ? 5 : peak * 1.25))
}

function axisTick(value: number | string, lang: string): string {
  const parsed = typeof value === "number" ? value : Number(value)
  return formatNumber(Number.isFinite(parsed) ? parsed : null, 0, lang)
}

export function WaterChart({
  points,
  lang,
  threshold,
  thresholdLabel,
}: {
  points: WaterPoint[]
  lang: string
  threshold: number | null
  thresholdLabel: string
}) {
  const { t } = useTranslation()
  return (
    <div>
      <ChartLegend
        items={[
          { label: t("soil.legendWater"), color: PRI },
          { label: t("soil.legendForecast"), color: PRI, dashed: true },
          { label: t("soil.legendThreshold"), color: AMBER, dashed: true },
          { label: t("soil.legendRain"), color: RAIN },
          { label: t("soil.legendIrrigation"), color: IRRIGATION },
        ]}
      />
      <div dir="ltr" className="h-[220px] w-full">
        <ResponsiveContainer
          width="100%"
          height="100%"
          minWidth={0}
          initialDimension={{ width: 640, height: 220 }}
        >
          <ComposedChart data={points} margin={{ top: 16, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#E5E7EB" />
            <XAxis dataKey="label" tick={tick} tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis
              yAxisId="water"
              tick={tick}
              tickLine={false}
              axisLine={false}
              width={36}
              tickFormatter={(value: number) => axisTick(value, lang)}
            />
            <YAxis
              yAxisId="depth"
              orientation="right"
              domain={[0, depthDomain(points)]}
              tick={tick}
              tickLine={false}
              axisLine={false}
              width={32}
              tickFormatter={(value: number) => axisTick(value, lang)}
            />
            <Tooltip
              content={(props) => {
                const row = props.payload?.[0]?.payload as WaterPoint | undefined
                if (!props.active || row === undefined) return null
                const left = row.past ?? row.forecast
                return (
                  <div
                    dir={lang === "ar" ? "rtl" : "ltr"}
                    className="rounded-lg border border-line bg-white px-3 py-2 text-[12px] shadow-sm"
                  >
                    <p className="mb-1 font-semibold">{row.label}</p>
                    <TipRow label={t("soil.legendWater")} value={left} lang={lang} />
                    <TipRow label={t("soil.legendRain")} value={row.rain} lang={lang} />
                    <TipRow label={t("soil.legendIrrigation")} value={row.irrigation} lang={lang} />
                  </div>
                )
              }}
            />
            {threshold !== null ? (
              <ReferenceLine
                yAxisId="water"
                y={threshold}
                stroke={AMBER}
                strokeDasharray="4 3"
                ifOverflow="extendDomain"
                label={{
                  value: thresholdLabel,
                  fill: AMBER,
                  fontSize: 11,
                  position: "insideTopRight",
                }}
              />
            ) : null}
            <Bar
              yAxisId="depth"
              dataKey="rain"
              fill={RAIN}
              maxBarSize={10}
              isAnimationActive={false}
            />
            <Bar
              yAxisId="depth"
              dataKey="irrigation"
              fill={IRRIGATION}
              fillOpacity={0.85}
              maxBarSize={10}
              isAnimationActive={false}
            />
            <Line
              yAxisId="water"
              dataKey="past"
              stroke={PRI}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              yAxisId="water"
              dataKey="forecast"
              stroke={PRI}
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function TipRow({
  label,
  value,
  lang,
}: {
  label: string
  value: number | null
  lang: string
}) {
  return (
    <p className="flex justify-between gap-4">
      <span className="text-mut">{label}</span>
      <span className="font-semibold">
        {formatNumber(value, value !== null && Math.abs(value - Math.round(value)) < 0.05 ? 0 : 1, lang)}{" "}
        {UNIT_MM}
      </span>
    </p>
  )
}
