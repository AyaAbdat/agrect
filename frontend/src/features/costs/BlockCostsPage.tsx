import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import { apiGet } from "../../lib/api"
import { activeLang, type BlockDetail } from "../blocks/types"
import { operationTypeKey } from "../journal/display"
import { money } from "../inventories/money"
import type { BlockCosts } from "../inventories/types"
import { formatMediumDate } from "../weather/format"
import { LoadError, PageSkeleton, cardClass } from "../weather/ui"
import { MissingPricesPanel, UnitMismatchesPanel } from "./panels"

const SOURCES = ["product", "water", "labour", "machine", "fuel", "energy"] as const

function seasonYears(): number[] {
  const current = new Date().getFullYear()
  return [current, current - 1, current - 2, current - 3]
}

export function BlockCostsPage() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { blockId } = useParams()
  const [season, setSeason] = useState<number>(new Date().getFullYear())

  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const costsQuery = useQuery({
    queryKey: ["block-costs", blockId, season],
    queryFn: () => apiGet<BlockCosts>(`/v1/blocks/${blockId}/costs?season=${season}`),
    enabled: blockId !== undefined,
  })

  if (blockId === undefined) return null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wide text-mut">
            {t("costs.title")}
          </p>
          <h1 className="text-[24px] font-bold leading-tight">
            {blockQuery.data?.name ?? t("costs.blockTitle")}
          </h1>
          <Link to="/costs" className="text-[12px] font-semibold text-pri">
            {t("costs.allBlocks")}
          </Link>
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
              <p className="text-[12px] text-mut">{t("costs.total")}</p>
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
            <h2 className="text-[14px] font-bold">{t("costs.bySource")}</h2>
            <ul className="mt-2 flex flex-col gap-1 text-[13px]">
              {SOURCES.filter((source) => costsQuery.data.by_source[source] !== undefined).map(
                (source) => (
                  <li key={source} className="flex items-center justify-between">
                    <span>{t(`costs.sources.${source}`)}</span>
                    <span dir="ltr">
                      {money(costsQuery.data.by_source[source], lang)} {t("common.dzd")}
                    </span>
                  </li>
                ),
              )}
              {Object.keys(costsQuery.data.by_source).length === 0 ? (
                <li className="text-mut">{t("costs.empty")}</li>
              ) : null}
            </ul>
          </section>

          <section className={cardClass}>
            <h2 className="text-[14px] font-bold">{t("costs.byOperation")}</h2>
            {costsQuery.data.by_operation.length === 0 ? (
              <p className="px-2 py-6 text-center text-[13px] text-mut">{t("costs.empty")}</p>
            ) : (
              <div className="mt-2 overflow-x-auto">
                <table className="w-full min-w-[480px] text-start text-[13px]">
                  <thead className="text-[11px] uppercase tracking-wide text-mut">
                    <tr className="border-b border-line">
                      <th className="py-2 text-start font-semibold">{t("inventories.date")}</th>
                      <th className="py-2 text-start font-semibold">
                        {t("journal.operationType")}
                      </th>
                      <th className="py-2 text-end font-semibold">{t("costs.total")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {costsQuery.data.by_operation.map((row, index) => (
                      <tr
                        key={`${row.date}-${index}`}
                        className="border-b border-line last:border-b-0"
                      >
                        <td className="py-2" dir="ltr">
                          {formatMediumDate(row.date, lang)}
                        </td>
                        <td className="py-2">{t(operationTypeKey(row.type))}</td>
                        <td className="py-2 text-end" dir="ltr">
                          {money(row.dzd, lang)} {t("common.dzd")}
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
