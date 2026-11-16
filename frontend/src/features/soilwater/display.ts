import { formatNumber } from "../../lib/format"
import { asNumber, formatMediumDate } from "../weather/format"

type Translate = (key: string, options?: Record<string, string>) => string

export function show(value: string | number | null | undefined, lang: string): string {
  const parsed = asNumber(value)
  return formatNumber(parsed, digitsFor(parsed), lang)
}

export function thetaPercent(value: string | null | undefined, lang: string): string {
  const theta = asNumber(value)
  if (theta === null) return formatNumber(null, 0, lang)
  return show(theta * 100, lang)
}

export function efficiencyPercent(value: string | null | undefined, lang: string): string {
  const ratio = asNumber(value)
  if (ratio === null) return formatNumber(null, 0, lang)
  return show(ratio * 100, lang)
}

export function runParts(
  minutes: string | number | null | undefined,
  lang: string,
): { hours: string; minutes: string } {
  const total = asNumber(minutes)
  if (total === null || total < 0) {
    return { hours: formatNumber(null, 0, lang), minutes: formatNumber(null, 0, lang) }
  }
  const rounded = Math.round(total)
  return {
    hours: formatNumber(Math.floor(rounded / 60), 0, lang),
    minutes: formatNumber(rounded % 60, 0, lang),
  }
}

export function formatEventDate(iso: string, timeZone: string, lang: string): string {
  return new Intl.DateTimeFormat(`${lang}-u-nu-latn`, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone,
  }).format(new Date(iso))
}

export function mm2(value: string | number | null | undefined, lang: string): string {
  return formatNumber(asNumber(value), 2, lang)
}

export function runClock(totalMin: number, lang: string): string {
  const hours = Math.floor(totalMin / 60)
  const minutes = totalMin % 60
  return `${formatNumber(hours, 0, lang)}:${formatNumber(minutes, 0, lang).padStart(2, "0")}`
}

export function farmWallIso(isoDate: string, time: string, timeZone: string): string {
  const [year, month, day] = isoDate.split("-").map(Number)
  const [hour, minute] = time.split(":").map(Number)
  const utcGuess = Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1, hour ?? 0, minute ?? 0, 0)
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(utcGuess))
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((part) => part.type === type)?.value ?? "0")
  const wall = Date.UTC(
    pick("year"),
    pick("month") - 1,
    pick("day"),
    pick("hour") % 24,
    pick("minute"),
    pick("second"),
  )
  return new Date(utcGuess - (wall - utcGuess)).toISOString()
}

export function farmDateAndTime(iso: string, timeZone: string): { date: string; time: string } {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).formatToParts(new Date(iso))
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? ""
  const hour = String(Number(pick("hour")) % 24).padStart(2, "0")
  const minute = pick("minute").padStart(2, "0")
  return { date: `${pick("year")}-${pick("month")}-${pick("day")}`, time: `${hour}:${minute}` }
}

export function balanceNote(note: string, lang: string, t: Translate): string | null {
  const assumed = /^assumed at field capacity on (\d{4}-\d{2}-\d{2})$/.exec(note)
  if (assumed?.[1] !== undefined) {
    return t("soil.assumedFull", { date: formatMediumDate(assumed[1], lang) })
  }
  const restarted = /^restarted at field capacity on (\d{4}-\d{2}-\d{2})$/.exec(note)
  if (restarted?.[1] !== undefined) {
    return t("soil.restartedFull", { date: formatMediumDate(restarted[1], lang) })
  }
  return null
}

function digitsFor(value: number | null): number {
  if (value === null) return 0
  return Math.abs(value - Math.round(value)) < 0.05 ? 0 : 1
}
