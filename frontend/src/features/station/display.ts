import { formatNumber } from "../../lib/format"
import { asNumber } from "../weather/format"
import type { PumpWindow, ValveFlow } from "./types"

export function flowText(value: string | number | null | undefined, lang: string): string {
  return formatNumber(asNumber(value), 2, lang)
}

export function hoursText(value: string | number | null | undefined, lang: string): string {
  const parsed = asNumber(value)
  if (parsed === null) return formatNumber(null, 0, lang)
  const digits = Number.isInteger(parsed) ? 0 : 2
  return formatNumber(parsed, digits, lang)
}

export function clockHm(value: string): string {
  const match = /^(\d{2}):(\d{2})/.exec(value)
  if (match === null) return value
  return `${match[1]}:${match[2]}`
}

export function windowsLabel(windows: PumpWindow[], allDay: string): string {
  if (windows.length === 0) return allDay
  return windows.map((window) => `${clockHm(window.start_time)}–${clockHm(window.end_time)}`).join(", ")
}

export function shiftClock(minutes: string, lang: string): string {
  const total = asNumber(minutes)
  if (total === null || total < 0) return formatNumber(null, 0, lang)
  const rounded = Math.round(total)
  const hours = Math.floor(rounded / 60)
  const mins = rounded % 60
  const minuteText = formatNumber(mins, 0, lang).padStart(2, "0")
  return `${formatNumber(hours, 0, lang)}:${minuteText}`
}

export function sameIds(left: string[], right: string[]): boolean {
  if (left.length !== right.length) return false
  const a = [...left].sort()
  const b = [...right].sort()
  return a.every((id, index) => id === b[index])
}

export function isPositive(value: string | null | undefined): boolean {
  const parsed = asNumber(value)
  return parsed !== null && parsed > 0
}

export function groupedValveLabel(
  valves: ValveFlow[],
  blockName: (id: string) => string,
  valveName: (id: string) => string,
  valveSort: (id: string) => number,
): string {
  const order: string[] = []
  const groups = new Map<string, ValveFlow[]>()
  for (const valve of valves) {
    const group = groups.get(valve.block_id)
    if (group === undefined) {
      groups.set(valve.block_id, [valve])
      order.push(valve.block_id)
    } else {
      group.push(valve)
    }
  }
  return order
    .map((blockId) => {
      const names = [...(groups.get(blockId) ?? [])]
        .sort((left, right) => valveSort(left.valve_id) - valveSort(right.valve_id))
        .map((valve) => valveName(valve.valve_id))
      return `${blockName(blockId)} · ${names.join(", ")}`
    })
    .join(" · ")
}
