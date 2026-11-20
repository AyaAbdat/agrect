import { useEffect, useState } from "react"

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>
}

function isInstallPrompt(event: Event): event is BeforeInstallPromptEvent {
  return (
    "prompt" in event &&
    typeof (event as BeforeInstallPromptEvent).prompt === "function"
  )
}

let promptEvent: BeforeInstallPromptEvent | null = null
const listeners = new Set<() => void>()

function publish(next: BeforeInstallPromptEvent | null) {
  promptEvent = next
  for (const listener of listeners) listener()
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    if (!isInstallPrompt(event)) return
    event.preventDefault()
    publish(event)
  })
  window.addEventListener("appinstalled", () => {
    publish(null)
  })
}

export function useInstallPrompt() {
  const [, redraw] = useState(0)

  useEffect(() => {
    const listener = () => redraw((count) => count + 1)
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  }, [])

  function install() {
    if (promptEvent === null) return
    const pending = promptEvent
    void pending.prompt().finally(() => {
      publish(null)
    })
  }

  return { canInstall: promptEvent !== null, install }
}
