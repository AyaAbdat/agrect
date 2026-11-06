import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const localesDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "src",
  "i18n",
  "locales",
)
const langs = ["fr", "ar", "en"]

function flatten(value, prefix, out) {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    for (const [key, child] of Object.entries(value)) {
      const next = prefix ? `${prefix}.${key}` : key
      flatten(child, next, out)
    }
    return
  }
  out[prefix] = value
}

function load(lang) {
  const raw = JSON.parse(readFileSync(join(localesDir, `${lang}.json`), "utf8"))
  const flat = {}
  flatten(raw, "", flat)
  return flat
}

const maps = Object.fromEntries(langs.map((lang) => [lang, load(lang)]))
const keySets = Object.fromEntries(
  langs.map((lang) => [lang, new Set(Object.keys(maps[lang]))]),
)
const base = [...keySets.fr].sort()
let failed = false

for (const lang of langs) {
  if (lang === "fr") continue
  const missing = base.filter((key) => !keySets[lang].has(key))
  const extra = [...keySets[lang]].filter((key) => !keySets.fr.has(key)).sort()
  if (missing.length > 0 || extra.length > 0) {
    failed = true
    console.error(`${lang} missing: ${missing.join(", ") || "(none)"}`)
    console.error(`${lang} extra: ${extra.join(", ") || "(none)"}`)
  }
}

for (const lang of langs) {
  for (const [key, value] of Object.entries(maps[lang])) {
    if (typeof value !== "string" || value.trim() === "") {
      failed = true
      console.error(`${lang}: empty value at ${key}`)
    }
  }
}

if (failed) process.exit(1)
console.log(`i18n keys OK (${base.length} keys)`)
