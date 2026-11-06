import i18n from "i18next"
import { initReactI18next } from "react-i18next"
import ar from "./locales/ar.json"
import en from "./locales/en.json"
import fr from "./locales/fr.json"

export const LANGS = ["fr", "ar", "en"] as const
export type Lang = (typeof LANGS)[number]

const STORAGE_KEY = "agrect.lang"

export function isLang(value: unknown): value is Lang {
  return typeof value === "string" && (LANGS as readonly string[]).includes(value)
}

function readLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (isLang(stored)) return stored
  } catch {
    // Storage can be blocked; fall back to French.
  }
  return "fr"
}

function applyDocumentLang(lang: string) {
  document.documentElement.lang = lang
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr"
}

void i18n.use(initReactI18next).init({
  resources: {
    fr: { translation: fr },
    ar: { translation: ar },
    en: { translation: en },
  },
  lng: readLang(),
  fallbackLng: "fr",
  supportedLngs: [...LANGS],
  interpolation: { escapeValue: false },
})

applyDocumentLang(i18n.language)

i18n.on("languageChanged", (lang) => {
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // Ignore storage failures; the document language still updates.
  }
  applyDocumentLang(lang)
})

export { i18n }
