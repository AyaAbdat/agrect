import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { activeLang, localizedName } from "../blocks/types"
import { operationTypeKey } from "../journal/display"
import { asNumber } from "../weather/format"
import { LoadError, PageSkeleton, SourceTag, cardClass } from "../weather/ui"
import type { LabourNormList } from "./types"

function seasonYears(): number[] {
  const current = new Date().getFullYear()
  return [current, current - 1, current - 2, current - 3]
}

export function LabourNormsTab() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const farmId = currentFarmId
  const [season, setSeason] = useState<number>(new Date().getFullYear())

  const normsQuery = useQuery({
    queryKey: ["labour-norms", farmId, season],
    queryFn: () => apiGet<LabourNormList>(`/v1/farms/${farmId}/labour-norms?season=${season}`),
    enabled: farmId !== null,
  })

  if (farmId === null) return null

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-end">
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

      {normsQuery.isLoading ? (
        <PageSkeleton />
      ) : normsQuery.isError || normsQuery.data === undefined ? (
        <LoadError onRetry={() => void normsQuery.refetch()} />
      ) : (
        <section className={cardClass}>
          {normsQuery.data.rows.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <p className="text-[13px] text-mut">{t("team.norms.empty")}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] text-start text-[13px]">
                <thead className="text-[11px] uppercase tracking-wide text-mut">
                  <tr className="border-b border-line">
                    <th className="py-2 text-start font-semibold">
                      {t("team.norms.operationType")}
                    </th>
                    <th className="py-2 text-start font-semibold">{t("team.norms.crop")}</th>
                    <th className="py-2 text-end font-semibold">
                      {t("team.norms.operations")}
                    </th>
                    <th className="py-2 text-end font-semibold">{t("team.norms.hours")}</th>
                    <th className="py-2 text-end font-semibold">{t("team.norms.areaHa")}</th>
                    <th className="py-2 text-end font-semibold">
                      <span className="inline-flex items-center gap-1.5">
                        {t("team.norms.hPerHa")}
                        <SourceTag kind="calculated" />
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {normsQuery.data.rows.map((row) => (
                    <tr
                      key={`${row.operation_type}-${row.crop?.id ?? "none"}`}
                      className="border-b border-line last:border-b-0"
                    >
                      <td className="py-3 font-semibold">
                        {t(operationTypeKey(row.operation_type))}
                      </td>
                      <td className="py-3">
                        {row.crop === null
                          ? t("common.missing")
                          : localizedName(row.crop.name, lang)}
                      </td>
                      <td className="py-3 text-end" dir="ltr">
                        {formatNumber(row.operations_count, 0, lang)}
                      </td>
                      <td className="py-3 text-end" dir="ltr">
                        {formatNumber(asNumber(row.total_hours), 1, lang)}
                      </td>
                      <td className="py-3 text-end" dir="ltr">
                        {formatNumber(asNumber(row.total_area_ha), 2, lang)}
                      </td>
                      <td className="py-3 text-end font-semibold" dir="ltr">
                        {formatNumber(asNumber(row.h_per_ha), 1, lang)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
