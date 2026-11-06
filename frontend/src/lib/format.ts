export function formatNumber(
  value: number | null | undefined,
  decimals: number,
  lang: string,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—"
  }
  return new Intl.NumberFormat(`${lang}-u-nu-latn`, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}
