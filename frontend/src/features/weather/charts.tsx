import { useTranslation } from "react-i18next"
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { formatNumber } from "../../lib/format"
import { UNIT_MM, UNIT_TEMP_C } from "../../lib/units"
import { ChartLegend, EmptyChart } from "./ui"
import type { GddPoint, HistoryPoint, HourPoint } from "./types"

const PRI = "#1B4332"
const GRN = "#40916C"
const SEC = "#2D6A4F"
const tick = { fontSize: 11, fill: "#6B7280" }

function axisTick(value: number | string, lang: string): string {
  const parsed = typeof value === "number" ? value : Number(value)
  return formatNumber(Number.isFinite(parsed) ? parsed : null, 0, lang)
}

function Tip({
  lang,
  title,
  rows,
}: {
  lang: string
  title: string
  rows: { label: string; value: string }[]
}) {
  return (
    <div
      dir={lang === "ar" ? "rtl" : "ltr"}
      className="rounded-lg border border-line bg-white px-3 py-2 text-[12px] shadow-sm"
    >
      <p className="mb-1 font-semibold">{title}</p>
      {rows.map((row) => (
        <p key={row.label} className="flex justify-between gap-4">
          <span className="text-mut">{row.label}</span>
          <span className="font-semibold">{row.value}</span>
        </p>
      ))}
    </div>
  )
}

export function HourChart({ points, lang }: { points: HourPoint[]; lang: string }) {
  const { t } = useTranslation()
  if (points.length === 0) return <EmptyChart />
  return (
    <div>
      <ChartLegend
        items={[
          { label: t("weather.temp"), color: PRI },
          { label: t("weather.rain"), color: SEC },
        ]}
      />
      <div dir="ltr" className="h-[240px] w-full">
        <ResponsiveContainer
          width="100%"
          height="100%"
          minWidth={0}
          initialDimension={{ width: 520, height: 240 }}
        >
          <ComposedChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#E5E7EB" />
            <XAxis dataKey="label" tick={tick} tickLine={false} axisLine={false} minTickGap={28} />
            <YAxis
              yAxisId="temp"
              tick={tick}
              tickLine={false}
              axisLine={false}
              width={36}
              tickFormatter={(value: number) => axisTick(value, lang)}
            />
            <YAxis
              yAxisId="rain"
              orientation="right"
              tick={tick}
              tickLine={false}
              axisLine={false}
              width={32}
              tickFormatter={(value: number) => axisTick(value, lang)}
            />
            <Tooltip
              content={(props) => {
                const row = props.payload?.[0]?.payload as HourPoint | undefined
                if (!props.active || row === undefined) return null
                return (
                  <Tip
                    lang={lang}
                    title={row.label}
                    rows={[
                      {
                        label: t("weather.temp"),
                        value: `${formatNumber(row.temp, 1, lang)} ${UNIT_TEMP_C}`,
                      },
                      {
                        label: t("weather.rhShort"),
                        value: `${formatNumber(row.rh, 0, lang)} %`,
                      },
                      {
                        label: t("weather.wind"),
                        value: `${formatNumber(row.wind, 1, lang)} m/s`,
                      },
                      {
                        label: t("weather.rain"),
                        value: `${formatNumber(row.rain, 1, lang)} ${UNIT_MM}`,
                      },
                    ]}
                  />
                )
              }}
            />
            <Bar
              yAxisId="rain"
              dataKey="rain"
              fill={SEC}
              fillOpacity={0.4}
              maxBarSize={10}
              isAnimationActive={false}
            />
            <Line
              yAxisId="temp"
              dataKey="temp"
              stroke={PRI}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function HistoryChart({ points, lang }: { points: HistoryPoint[]; lang: string }) {
  const { t } = useTranslation()
  if (points.length === 0) return <EmptyChart />
  return (
    <div>
      <ChartLegend
        items={[
          { label: t("weather.tmin"), color: GRN },
          { label: t("weather.tmax"), color: PRI },
          { label: t("weather.rain"), color: SEC },
        ]}
      />
      <div dir="ltr" className="h-[220px] w-full">
        <ResponsiveContainer
          width="100%"
          height="100%"
          minWidth={0}
          initialDimension={{ width: 640, height: 220 }}
        >
          <ComposedChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#E5E7EB" />
            <XAxis dataKey="label" tick={tick} tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis
              yAxisId="temp"
              tick={tick}
              tickLine={false}
              axisLine={false}
              width={36}
              tickFormatter={(value: number) => axisTick(value, lang)}
            />
            <YAxis
              yAxisId="rain"
              orientation="right"
              tick={tick}
              tickLine={false}
              axisLine={false}
              width={32}
              tickFormatter={(value: number) => axisTick(value, lang)}
            />
            <Tooltip
              content={(props) => {
                const row = props.payload?.[0]?.payload as HistoryPoint | undefined
                if (!props.active || row === undefined) return null
                return (
                  <Tip
                    lang={lang}
                    title={row.label}
                    rows={[
                      {
                        label: t("weather.tmin"),
                        value: `${formatNumber(row.tmin, 1, lang)} ${UNIT_TEMP_C}`,
                      },
                      {
                        label: t("weather.tmax"),
                        value: `${formatNumber(row.tmax, 1, lang)} ${UNIT_TEMP_C}`,
                      },
                      {
                        label: t("weather.rain"),
                        value: `${formatNumber(row.rain, 1, lang)} ${UNIT_MM}`,
                      },
                    ]}
                  />
                )
              }}
            />
            <Bar
              yAxisId="rain"
              dataKey="rain"
              fill={SEC}
              fillOpacity={0.4}
              maxBarSize={12}
              isAnimationActive={false}
            />
            <Line
              yAxisId="temp"
              dataKey="tmin"
              stroke={GRN}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              yAxisId="temp"
              dataKey="tmax"
              stroke={PRI}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function GddChart({ points, lang }: { points: GddPoint[]; lang: string }) {
  const { t } = useTranslation()
  if (points.length === 0) return <EmptyChart />
  const single = points.length === 1
  return (
    <div>
      <ChartLegend
        items={[
          { label: t("weather.legendPast"), color: PRI },
          { label: t("weather.legendForecast"), color: PRI, dashed: true },
        ]}
      />
      <div dir="ltr" className="h-[220px] w-full">
        <ResponsiveContainer
          width="100%"
          height="100%"
          minWidth={0}
          initialDimension={{ width: 640, height: 220 }}
        >
          <ComposedChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#E5E7EB" />
            <XAxis dataKey="label" tick={tick} tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis
              tick={tick}
              tickLine={false}
              axisLine={false}
              width={40}
              tickFormatter={(value: number) => axisTick(value, lang)}
            />
            <Tooltip
              content={(props) => {
                const row = props.payload?.[0]?.payload as GddPoint | undefined
                if (!props.active || row === undefined) return null
                return (
                  <Tip
                    lang={lang}
                    title={row.label}
                    rows={[
                      {
                        label: t("weather.dailyGdd"),
                        value: `${formatNumber(row.daily, 1, lang)} ${t("weather.unitCday")}`,
                      },
                    ]}
                  />
                )
              }}
            />
            <Line
              dataKey="past"
              stroke={PRI}
              strokeWidth={2}
              dot={single ? { r: 3 } : false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
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
