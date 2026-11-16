import { Info } from "lucide-react"
import { useState, type ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { apiSend } from "../../lib/api"
import { crumbClass } from "../../lib/navStyles"

export const cardClass = "rounded-2xl border border-line bg-white p-4"
export const fieldClass =
  "h-10 w-full rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px] outline-none focus:ring-2 focus:ring-mint"
export const outlineBtn = "h-9 rounded-full border border-line bg-white px-4 text-[13px] font-semibold"
export const primaryBtn = "h-9 rounded-full bg-pri px-4 text-[13px] font-semibold text-white"

export function SourceTag({ kind }: { kind: "estimated" | "calculated" }) {
  const { t } = useTranslation()
  const estimated = kind === "estimated"
  return (
    <span
      className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
        estimated ? "bg-[#E5E7EB] text-mut" : "bg-mint text-pri"
      }`}
    >
      {t(estimated ? "weather.estimated" : "weather.calculated")}
    </span>
  )
}

export function PageHeader({
  crumb,
  title,
  sub,
  actions,
}: {
  crumb: string
  title: string
  sub?: string
  actions?: ReactNode
}) {
  return (
    <header className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <p className={crumbClass}>{crumb}</p>
        <h1 className="text-[24px] font-bold leading-tight">{title}</h1>
        {sub !== undefined ? <p className="mt-1 text-mut">{sub}</p> : null}
      </div>
      {actions !== undefined ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </header>
  )
}

export function StatusBanner({ stale, time }: { stale: boolean; time: string }) {
  const { t } = useTranslation()
  if (stale) {
    return (
      <div className="rounded-xl bg-[#FEF3C7] px-4 py-3 text-[13px] text-amb">
        {t("weather.bannerStale", { time })}
      </div>
    )
  }
  return (
    <div className="rounded-xl bg-mint px-4 py-3 text-[13px] text-pri">
      {t("weather.bannerEstimated", { time })}
    </div>
  )
}

export function FieldLabel({
  label,
  tag,
}: {
  label: string
  tag?: "required" | "optional"
}) {
  const { t } = useTranslation()
  return (
    <span className="mb-1.5 flex items-start justify-between gap-2">
      <span className="text-[13px] font-semibold">{label}</span>
      {tag === "required" ? (
        <span className="shrink-0 rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[10px] font-semibold text-amb">
          {t("weather.required")}
        </span>
      ) : null}
      {tag === "optional" ? (
        <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
          {t("weather.optional")}
        </span>
      ) : null}
    </span>
  )
}

export function FieldError({ message }: { message: string | undefined }) {
  const { t } = useTranslation()
  if (message === undefined || message === "") return null
  return <p className="mt-1 text-[12px] text-red">{t(message)}</p>
}

export function ChoiceChip({
  selected,
  disabled,
  onClick,
  children,
  badge,
}: {
  selected: boolean
  disabled?: boolean
  onClick?: () => void
  children: string
  badge?: string
}) {
  const className = `inline-flex h-8 items-center gap-2 rounded-full px-3 text-[12px] font-semibold ${
    selected
      ? "bg-pri text-white"
      : disabled
        ? "border border-line bg-[#F3F5F3] text-mut"
        : "border border-[#C7D2C9] bg-white text-text"
  }`
  if (disabled || onClick === undefined) {
    return (
      <span className={className}>
        {children}
        {badge !== undefined ? (
          <span className="rounded-full bg-[#E5E7EB] px-1.5 py-0.5 text-[10px] text-mut">{badge}</span>
        ) : null}
      </span>
    )
  }
  return (
    <button type="button" aria-pressed={selected} onClick={onClick} className={className}>
      {children}
    </button>
  )
}

export function FormulaTip({ text }: { text: string }) {
  const { t } = useTranslation()
  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        className="flex size-6 items-center justify-center rounded-full border border-line text-mut"
        aria-label={t("weather.formulaLabel")}
      >
        <Info className="size-3.5" aria-hidden="true" />
      </button>
      <span
        role="tooltip"
        className="absolute start-0 top-full z-20 mt-1 hidden w-72 rounded-lg border border-line bg-white p-2 text-[12px] leading-snug shadow group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
  )
}

export function EmptyChart() {
  const { t } = useTranslation()
  return (
    <div className="flex h-[220px] items-center justify-center text-[13px] text-mut">
      {t("weather.noData")}
    </div>
  )
}

export function PageSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="h-8 w-48 animate-pulse rounded-xl bg-[#E5E7EB]" />
      <div className="h-14 animate-pulse rounded-xl bg-[#E5E7EB]" />
      <div className="h-40 animate-pulse rounded-2xl bg-[#E5E7EB]" />
      <div className="h-64 animate-pulse rounded-2xl bg-[#E5E7EB]" />
    </div>
  )
}

export function LoadError({ onRetry, pending = false }: { onRetry: () => void; pending?: boolean }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-line bg-white py-16 text-center">
      <p>{t("common.loadError")}</p>
      <Button type="button" className={primaryBtn} disabled={pending} onClick={onRetry}>
        {t("common.retry")}
      </Button>
    </div>
  )
}

export function WeatherError({ farmId }: { farmId: string }) {
  const queryClient = useQueryClient()
  const [pending, setPending] = useState(false)
  async function retry() {
    setPending(true)
    try {
      await apiSend("POST", `/v1/farms/${farmId}/weather/refresh`)
    } catch {
      // A failed refresh still refetches so stored values can appear.
    }
    await queryClient.invalidateQueries({ queryKey: ["weather", farmId] })
    setPending(false)
  }
  return <LoadError pending={pending} onRetry={() => void retry()} />
}

export function ChartLegend({
  items,
}: {
  items: { label: string; color: string; dashed?: boolean }[]
}) {
  return (
    <div className="mb-2 flex flex-wrap gap-3 text-[11px] text-mut">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-0.5 w-4"
            style={{
              background: item.dashed ? "transparent" : item.color,
              borderTop: item.dashed ? `2px dashed ${item.color}` : undefined,
            }}
          />
          {item.label}
        </span>
      ))}
    </div>
  )
}
