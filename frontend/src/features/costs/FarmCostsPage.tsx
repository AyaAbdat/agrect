import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { activeLang } from "../blocks/types"
import { money } from "../inventories/money"
import type { FarmCosts } from "../inventories/types"
import { LoadError, PageSkeleton, cardClass } from "../weather/ui"
import { MissingPricesPanel, UnitMismatchesPanel } from "./panels"

function seasonYears(): number[] {
  const current = new Date().getFullYear()
  return [current, current - 1, current - 2, current - 3]
}

export function FarmCostsPage() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const farmId = currentFarmId
  const [season, setSeason] = useState<number>(new Date().getFullYear())

  const costsQuery = useQuery({
    queryKey: ["farm-costs", farmId, season],
    queryFn: () => apiGet<FarmCosts>(`/v1/farms/${farmId}/costs?season=${season}`),
    enabled: farmId !== null,
  })

  if (farmId === null) return null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wide text-mut">
            {t("costs.title")}
          </p>
          <h1 className="text-[24px] font-bold leading-tight">{t("costs.farmTitle")}</h1>
          <p className="text-[13px] text-mut">{t("costs.sub")}</p>
        </div>
        <label className="flex items-center gap-2 text-[13px]">
          <span className="font-semibold text-mut">{t("costs.season")}</span>
          <select
            className="h-9 rounded-full border border-line bg-white px-3 text-[13px]"
            dir="ltr"
            value={season}
            onChange={(change) => setSeason(Number(change.target.value))}
          >
            {seasonYears().map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </label>
      </div>

      {costsQuery.isLoading ? <PageSkeleton /> : null}
      {costsQuery.isError || costsQuery.data === undefined ? (
        !costsQuery.isLoading ? <LoadError onRetry={() => void costsQuery.refetch()} /> : null
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className={cardClass}>
              <p className="text-[12px] text-mut">{t("costs.farmTotal")}</p>
              <p className="mt-2 text-[22px] font-bold" dir="ltr">
                {money(costsQuery.data.total_dzd, lang)} {t("common.dzd")}
              </p>
            </div>
            <div className={cardClass}>
              <p className="text-[12px] text-mut">{t("costs.perHa")}</p>
              <p className="mt-2 text-[22px] font-bold" dir="ltr">
                {money(costsQuery.data.per_ha_dzd, lang)} {t("common.dzd")}
              </p>
            </div>
          </div>

          <section className={cardClass}>
            {costsQuery.data.blocks.length === 0 ? (
              <p className="px-2 py-8 text-center text-[13px] text-mut">{t("costs.empty")}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-start text-[13px]">
                  <thead className="text-[11px] uppercase tracking-wide text-mut">
                    <tr className="border-b border-line">
                      <th className="py-2 text-start font-semibold">{t("costs.block")}</th>
                      <th className="py-2 text-end font-semibold">{t("costs.total")}</th>
                      <th className="py-2 text-end font-semibold">{t("costs.perHa")}</th>
                      <th className="py-2 text-end font-semibold">{t("costs.products")}</th>
                      <th className="py-2 text-end font-semibold">{t("costs.water")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {costsQuery.data.blocks.map((block) => (
                      <tr key={block.block_id} className="border-b border-line last:border-b-0">
                        <td className="py-3 font-semibold">
                          <Link to={`/blocks/${block.block_id}/costs`} className="text-pri">
                            {block.name}
                          </Link>
                        </td>
                        <td className="py-3 text-end" dir="ltr">
                          {money(block.total_dzd, lang)}
                        </td>
                        <td className="py-3 text-end" dir="ltr">
                          {money(block.per_ha_dzd, lang)}
                        </td>
                        <td className="py-3 text-end" dir="ltr">
                          {money(block.by_source.product ?? "0", lang)}
                        </td>
                        <td className="py-3 text-end" dir="ltr">
                          {money(block.by_source.water ?? "0", lang)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <MissingPricesPanel names={costsQuery.data.missing_prices} />
          <UnitMismatchesPanel rows={costsQuery.data.unit_mismatches} />
        </>
      )}
    </div>
  )
}
