import { formatNumber } from "../../lib/format"

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null
  const parsed = Number(value)
  return Number.isNaN(parsed) ? null : parsed
}

/** A DZD total: grouped thousands, no decimals, Western digits. */
export function money(value: string | number | null | undefined, lang: string): string {
  return formatNumber(toNumber(value), 0, lang)
}

/** A unit price: grouped thousands, two decimals. */
export function unitPrice(value: string | number | null | undefined, lang: string): string {
  return formatNumber(toNumber(value), 2, lang)
}

/** A stock quantity: up to three decimals, trailing zeros trimmed. */
export function amount(value: string | number | null | undefined, lang: string): string {
  const parsed = toNumber(value)
  if (parsed === null) return "—"
  return new Intl.NumberFormat(`${lang}-u-nu-latn`, { maximumFractionDigits: 3 }).format(parsed)
}
