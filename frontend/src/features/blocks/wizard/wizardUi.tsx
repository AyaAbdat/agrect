import type { ReactNode } from "react"
import type { UseFormRegisterReturn } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { formatNumber } from "../../../lib/format"

export const fieldClass =
  "h-10 w-full rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px] outline-none focus:ring-2 focus:ring-mint"

export const panelClass = "min-w-0 flex-1 rounded-2xl border border-line bg-white p-4"

export function showServerNumber(
  value: string | number | null | undefined,
  places: number,
  lang: string,
): string {
  if (value === null || value === undefined || value === "") return formatNumber(null, places, lang)
  const parsed = typeof value === "number" ? value : Number(value)
  return formatNumber(parsed, places, lang)
}

export function FieldError({ message }: { message: string | undefined }) {
  const { t } = useTranslation()
  if (message === undefined || message === "") return null
  return (
    <p className="mt-1 text-[12px] text-red">
      {t(message, { year: new Date().getFullYear() })}
    </p>
  )
}

export function SourceTag() {
  const { t } = useTranslation()
  return (
    <span className="shrink-0 rounded-full bg-mint px-2 py-0.5 text-[10px] font-semibold text-pri">
      {t("blocks.calculated")}
    </span>
  )
}

export function RequiredTag() {
  const { t } = useTranslation()
  return (
    <span className="shrink-0 rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[10px] font-semibold text-amb">
      {t("blocks.required")}
    </span>
  )
}

export function OptionalTag() {
  const { t } = useTranslation()
  return (
    <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
      {t("blocks.optional")}
    </span>
  )
}

export function EnteredTag() {
  const { t } = useTranslation()
  return (
    <span className="shrink-0 rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
      {t("blocks.entered")}
    </span>
  )
}

export function FieldLabel({
  label,
  tag,
}: {
  label: string
  tag?: "calculated" | "required" | "optional" | "entered"
}) {
  return (
    <span className="mb-1.5 flex items-start justify-between gap-2">
      <span className="text-[13px] font-semibold">{label}</span>
      {tag === "calculated" ? <SourceTag /> : null}
      {tag === "required" ? <RequiredTag /> : null}
      {tag === "optional" ? <OptionalTag /> : null}
      {tag === "entered" ? <EnteredTag /> : null}
    </span>
  )
}

export function FactRow({
  label,
  value,
  tag,
}: {
  label: string
  value: string
  tag?: "calculated" | "optional" | "entered"
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-line py-2 last:border-b-0">
      <span className="text-[13px] text-mut">{label}</span>
      <span className="flex items-center gap-2 text-end text-[13px] font-semibold">
        {tag === "calculated" ? <SourceTag /> : null}
        {tag === "optional" ? <OptionalTag /> : null}
        {tag === "entered" ? <EnteredTag /> : null}
        <span>{value}</span>
      </span>
    </div>
  )
}

export function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#9CA3AF]">{children}</p>
  )
}

export function TextField({
  label,
  unit,
  error,
  placeholder,
  inputMode,
  registration,
  tag,
}: {
  label: string
  unit?: string
  error?: string
  placeholder?: string
  inputMode?: "decimal" | "numeric" | "text"
  registration: UseFormRegisterReturn
  tag?: "required" | "optional"
}) {
  return (
    <label className="block min-w-0">
      <FieldLabel label={label} tag={tag} />
      <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
        <input
          className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
          inputMode={inputMode}
          placeholder={placeholder}
          autoComplete="off"
          aria-invalid={error !== undefined}
          {...registration}
        />
        {unit !== undefined ? <span className="text-mut">{unit}</span> : null}
      </span>
      <FieldError message={error} />
    </label>
  )
}

export function CalculatedField({
  label,
  value,
  unit,
  help,
  error,
}: {
  label: string
  value: string
  unit?: string
  help?: string
  error?: string
}) {
  return (
    <div className="min-w-0">
      <FieldLabel label={label} tag="calculated" />
      <div className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-[#F4F7F4] px-3 text-[13px]">
        <span className="flex-1">{value}</span>
        {unit !== undefined ? <span className="text-mut">{unit}</span> : null}
      </div>
      {help !== undefined ? <p className="mt-1 text-[12px] text-mut">{help}</p> : null}
      <FieldError message={error} />
    </div>
  )
}

export function Chip({
  selected,
  onClick,
  children,
}: {
  selected: boolean
  onClick: () => void
  children: string
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={`inline-flex h-8 items-center rounded-full px-3 text-[12px] font-semibold ${
        selected ? "bg-pri text-white" : "border border-[#C7D2C9] bg-white text-text"
      }`}
    >
      {children}
    </button>
  )
}

export function InlineError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-wrap items-center gap-3 py-2">
      <p className="text-[13px]">{t("common.loadError")}</p>
      <Button type="button" variant="outline" className="h-8 rounded-full px-3" onClick={onRetry}>
        {t("common.retry")}
      </Button>
    </div>
  )
}

export type ExplainerLine = {
  id: string
  formula: string
  label: string
  value: string
}

export function ExplainerCard({
  title,
  lines,
  footnote,
}: {
  title: string
  lines: ExplainerLine[]
  footnote?: string
}) {
  const { t } = useTranslation()
  return (
    <aside className="w-[320px] shrink-0 rounded-2xl border border-line bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-[15px] font-bold">{title}</h2>
        <SourceTag />
      </div>
      <p className="mt-1 text-[12px] text-mut">{t("blocks.explainerSub")}</p>
      <ol className="mt-4 flex flex-col gap-3">
        {lines.map((line, index) => (
          <li key={line.id} className="flex items-start gap-2">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-mint text-[11px] font-bold text-pri">
              {index + 1}
            </span>
            <span className="flex min-w-0 flex-1 items-start justify-between gap-2">
              <span className="min-w-0">
                <span className="block text-[13px] font-bold">{line.formula}</span>
                <span className="mt-0.5 block text-[11px] text-mut">{line.label}</span>
              </span>
              <span className="shrink-0 text-[13px] font-semibold">{line.value}</span>
            </span>
          </li>
        ))}
      </ol>
      {footnote !== undefined ? <p className="mt-4 text-[11px] text-mut">{footnote}</p> : null}
    </aside>
  )
}

export function InfoBox({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-[#C7D2C9] bg-[#F4F7F4] px-4 py-3 text-[13px]">
      {children}
    </div>
  )
}
