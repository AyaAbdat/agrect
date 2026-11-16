export function asNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null
  const parsed = typeof value === "number" ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function decimalInput(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return ""
  if (!value.includes(".")) return value
  return value.replace(/0+$/, "").replace(/\.$/, "")
}

export function wireDecimal(value: string): string | null {
  const trimmed = value.trim().replace(",", ".")
  if (trimmed === "") return null
  return trimmed
}

export function isDecimal(value: string): boolean {
  return /^-?\d+(\.\d+)?$/.test(value.trim().replace(",", "."))
}

export function farmToday(timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date())
}

export function farmLocalNow(timeZone: string): { isoDate: string; hour: number } {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
  }).formatToParts(new Date())
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? ""
  const rawHour = Number(pick("hour"))
  return {
    isoDate: `${pick("year")}-${pick("month")}-${pick("day")}`,
    hour: Number.isFinite(rawHour) ? rawHour % 24 : 0,
  }
}

export function shiftIsoDate(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number)
  const utc = new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1))
  utc.setUTCDate(utc.getUTCDate() + days)
  return utc.toISOString().slice(0, 10)
}

function utcNoon(isoDate: string): Date {
  const [year, month, day] = isoDate.split("-").map(Number)
  return new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1, 12))
}

export function formatHour(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone,
  }).formatToParts(new Date(iso))
  const hour = parts.find((part) => part.type === "hour")?.value ?? "00"
  const minute = parts.find((part) => part.type === "minute")?.value ?? "00"
  return `${hour}:${minute}`
}

export function formatWeekdayDate(isoDate: string, lang: string): string {
  const date = utcNoon(isoDate)
  const weekday = new Intl.DateTimeFormat(`${lang}-u-nu-latn`, {
    weekday: "short",
    timeZone: "UTC",
  }).format(date)
  const day = new Intl.DateTimeFormat(`${lang}-u-nu-latn`, {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(date)
  return `${weekday} ${day}`
}

export function formatMediumDate(isoDate: string, lang: string): string {
  return new Intl.DateTimeFormat(`${lang}-u-nu-latn`, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(utcNoon(isoDate))
}

export function formatLongDate(isoDate: string, lang: string): string {
  return new Intl.DateTimeFormat(`${lang}-u-nu-latn`, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(utcNoon(isoDate))
}

export function formatAxisDate(isoDate: string, lang: string): string {
  return new Intl.DateTimeFormat(`${lang}-u-nu-latn`, {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(utcNoon(isoDate))
}
