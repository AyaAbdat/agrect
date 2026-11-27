import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import { activeLang } from "../blocks/types"
import type { UnitMismatch } from "../inventories/types"
import { formatMediumDate } from "../weather/format"

const amberPanel = "rounded-2xl border border-[#FDE68A] bg-[#FFFBEB] p-4"

const RESOURCE_LABEL_KEYS: Record<string, string> = {
  "resource.labour_h": "costs.missingResource.labour_h",
  "resource.machine_h": "costs.missingResource.machine_h",
  "resource.fuel_l": "costs.missingResource.fuel_l",
  "resource.water_m3": "costs.missingResource.water_m3",
  "resource.energy_kwh": "costs.missingResource.energy_kwh",
  "Labour (h)": "costs.missingResource.labour_h",
  "Machine (h)": "costs.missingResource.machine_h",
  "Fuel (L)": "costs.missingResource.fuel_l",
  "Water (m³)": "costs.missingResource.water_m3",
  "Energy (kWh)": "costs.missingResource.energy_kwh",
}

export function MissingPricesPanel({ names }: { names: string[] }) {
  const { t } = useTranslation()
  if (names.length === 0) return null
  const labels = names.map((entry) => {
    const key = RESOURCE_LABEL_KEYS[entry]
    return key !== undefined ? t(key) : entry
  })
  return (
    <section className={amberPanel}>
      <h2 className="text-[13px] font-bold text-amb">{t("costs.missingTitle")}</h2>
      <p className="mt-1 text-[12px] text-mut">{labels.join(", ")}</p>
      <Link to="/settings/inventories" className="mt-2 inline-block text-[12px] font-semibold text-pri">
        {t("costs.missingLink")}
      </Link>
    </section>
  )
}

export function UnitMismatchesPanel({ rows }: { rows: UnitMismatch[] }) {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  if (rows.length === 0) return null
  return (
    <section className={amberPanel}>
      <h2 className="text-[13px] font-bold text-amb">{t("costs.unitsTitle")}</h2>
      <ul className="mt-1 flex flex-col gap-1">
        {rows.map((row) => (
          <li key={`${row.operation_id}-${row.product}`} className="text-[12px] text-mut">
            {t("costs.unitsRow", {
              product: row.product,
              op: row.operation_unit,
              prod: row.product_unit,
            })}{" "}
            <span dir="ltr">
              ({row.block_name}, {formatMediumDate(row.date, lang)})
            </span>
            <Link to={`/blocks/${row.block_id}/journal`} className="ms-2 font-semibold text-pri">
              {t("costs.openInJournal")}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
