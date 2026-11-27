import { useSyncExternalStore } from "react"

const EVENT_NAME = "agrect:checklist-visibility"

function storageKey(farmId: string): string {
  return `agrect.checklist.show.${farmId}`
}

function readValue(farmId: string): boolean {
  try {
    return window.localStorage.getItem(storageKey(farmId)) === "1"
  } catch {
    return false
  }
}

function notify() {
  window.dispatchEvent(new Event(EVENT_NAME))
}

export function showChecklist(farmId: string): void {
  try {
    window.localStorage.setItem(storageKey(farmId), "1")
  } catch {
    // Ignore storage failures in restricted contexts.
  }
  notify()
}

export function hideChecklist(farmId: string): void {
  try {
    window.localStorage.removeItem(storageKey(farmId))
  } catch {
    // Ignore storage failures in restricted contexts.
  }
  notify()
}

function subscribe(callback: () => void): () => void {
  window.addEventListener(EVENT_NAME, callback)
  window.addEventListener("storage", callback)
  return () => {
    window.removeEventListener(EVENT_NAME, callback)
    window.removeEventListener("storage", callback)
  }
}

export function useChecklistForceShow(farmId: string): boolean {
  return useSyncExternalStore(
    subscribe,
    () => readValue(farmId),
    () => false,
  )
}
