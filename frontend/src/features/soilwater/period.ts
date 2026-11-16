import { shiftIsoDate } from "../weather/format"

export type WaterPeriod = "week" | "month" | "season"

/** Monday–Sunday of the farm-local week that contains `todayIso`. */
export function weekRange(todayIso: string): { from: string; to: string } {
  const [year, month, day] = todayIso.split("-").map(Number)
  const weekday = new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1)).getUTCDay()
  const mondayOffset = weekday === 0 ? -6 : 1 - weekday
  return {
    from: shiftIsoDate(todayIso, mondayOffset),
    to: shiftIsoDate(todayIso, mondayOffset + 6),
  }
}

/** Calendar month that contains `todayIso`, in the farm-local date. */
export function monthRange(todayIso: string): { from: string; to: string } {
  const [yearText, monthText] = todayIso.split("-")
  const year = Number(yearText)
  const month = Number(monthText)
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate()
  return {
    from: `${yearText}-${monthText}-01`,
    to: `${yearText}-${monthText}-${String(last).padStart(2, "0")}`,
  }
}
