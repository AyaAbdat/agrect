export type NumberKind = "empty" | "incomplete" | "ok" | "invalid" | "nonpositive"

export function decimalKind(value: string): NumberKind {
  const trimmed = value.trim()
  if (trimmed === "") return "empty"
  const normalized = trimmed.replace(",", ".")
  if (normalized === "." || normalized === "-" || normalized === "-." || normalized.endsWith(".")) {
    return "incomplete"
  }
  if (!/^-?\d+(\.\d+)?$/.test(normalized)) return "invalid"
  const parsed = Number(normalized)
  if (!Number.isFinite(parsed)) return "invalid"
  if (parsed <= 0) return "nonpositive"
  return "ok"
}

export function integerKind(value: string): NumberKind {
  const trimmed = value.trim()
  if (trimmed === "") return "empty"
  if (trimmed === "-") return "incomplete"
  if (!/^-?\d+$/.test(trimmed)) return "invalid"
  const parsed = Number(trimmed)
  if (!Number.isSafeInteger(parsed)) return "invalid"
  if (parsed <= 0) return "nonpositive"
  return "ok"
}

export function decimalWire(value: string): string | null {
  const kind = decimalKind(value)
  if (kind !== "ok" && kind !== "nonpositive") return null
  return value.trim().replace(",", ".")
}

export function integerWire(value: string): string | null {
  const kind = integerKind(value)
  if (kind !== "ok" && kind !== "nonpositive") return null
  return value.trim()
}

export function liveDecimalMessage(value: string): string | null {
  if (decimalKind(value) === "invalid") return "blocks.errors.number"
  return null
}

export function liveIntegerMessage(value: string): string | null {
  if (integerKind(value) === "invalid") return "blocks.errors.whole"
  return null
}

export function submitDecimalMessage(value: string): string | null {
  const kind = decimalKind(value)
  if (kind === "empty" || kind === "ok") return null
  if (kind === "nonpositive") return "blocks.errors.positive"
  return "blocks.errors.number"
}

export function submitIntegerMessage(value: string): string | null {
  const kind = integerKind(value)
  if (kind === "empty" || kind === "ok") return null
  if (kind === "nonpositive") return "blocks.errors.positive"
  return "blocks.errors.whole"
}

export function submitYearMessage(value: string, yearNow: number): string | null {
  const trimmed = value.trim()
  if (trimmed === "") return null
  if (!/^\d{4}$/.test(trimmed)) return "blocks.errors.yearRange"
  const year = Number(trimmed)
  if (!Number.isInteger(year) || year < 1950 || year > yearNow) return "blocks.errors.yearRange"
  return null
}

export function yearPayload(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === "" ? null : trimmed
}
