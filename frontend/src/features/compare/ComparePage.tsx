import { useQuery } from "@tanstack/react-query"
import { AlertTriangle } from "lucide-react"
import { Fragment, useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useNavigate } from "react-router"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { activeLang } from "../blocks/types"
import { sourceBadgeClass, sourceKey } from "../journal/display"
import { ChoiceChip, LoadError, PageHeader, cardClass } from "../weather/ui"
import type { CompareMetric, CompareResponse, CompareRow, CompareSource } from "./types"

type MetricChipDef = {
  key: CompareMetric
  labelKey: string
  disabled?: boolean
}

const METRIC_CHIPS: MetricChipDef[] = [
  { key: "water_left", labelKey: "compare.metrics.waterLeft" },
  { key: "water_applied", labelKey: "compare.metrics.waterApplied" },
  { key: "crop_water_use", labelKey: "compare.metrics.cropWaterUse" },
  { key: "degree_days", labelKey: "compare.metrics.degreeDays" },
  { key: "pest_count", labelKey: "compare.metrics.pestCount", disabled: true },
  { key: "stage", labelKey: "compare.metrics.stage" },
]

function CompareSourceTag({ kind }: { kind: CompareSource | null }) {
  const { t } = useTranslation()
  if (kind === null) return null
  return (
    <span
      className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${sourceBadgeClass(kind)}`}
    >
      {t(sourceKey(kind))}
    </span>
  )
}

function localizedStageName(
  valueName: Record<string, string> | null,
  fallback: string,
  lang: string,
): string {
  if (valueName === null) return fallback
  return valueName[lang] ?? valueName.en ?? valueName.fr ?? valueName.ar ?? fallback
}

function formatUnit(unit: string | null, t: (key: string) => string): string {
  if (unit === "mm") return t("compare.units.mm")
  if (unit === "degc_day") return t("compare.units.degcDay")
  return unit ?? ""
}

function formatNumericValue(raw: string, unit: string | null, lang: string, t: (key: string) => string): string {
  const parsed = Number(raw)
  if (!Number.isFinite(parsed)) return raw
  const numText = formatNumber(parsed, 1, lang)
  const unitText = formatUnit(unit, t)
  return unitText === "" ? numText : `${numText} ${unitText}`
}

function flagMessageKey(code: string): string {
  if (code === "compare.drift_same_setting") return "compare.flags.driftSameSetting"
  return "compare.flags.generic"
}

export function ComparePage() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const navigate = useNavigate()
  const farmId = currentFarmId
  const [metric, setMetric] = useState<CompareMetric>("water_left")

  const compareQuery = useQuery({
    queryKey: ["compare", farmId, metric],
    queryFn: () => apiGet<CompareResponse>(`/v1/farms/${farmId}/compare?metric=${metric}`),
    enabled: farmId !== null && metric !== "pest_count",
  })

  const rows = useMemo(() => compareQuery.data?.rows ?? [], [compareQuery.data?.rows])
  const flags = useMemo(() => compareQuery.data?.flags ?? [], [compareQuery.data?.flags])

  const blockNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const row of rows) {
      map.set(row.block.id, row.block.name)
    }
    return map
  }, [rows])

  if (farmId === null) return null

  const hasMeanColumn = metric !== "degree_days" && metric !== "stage"

  function renderValueCell(row: CompareRow) {
    if (row.value === null) {
      return <span className="text-mut">{t("compare.notEnoughData")}</span>
    }
    const text =
      metric === "stage"
        ? localizedStageName(row.value_name, row.value, lang)
        : formatNumericValue(row.value, row.unit, lang, t)
    return (
      <span className="inline-flex flex-wrap items-center gap-1.5">
        <span className="font-medium text-text">{text}</span>
        <CompareSourceTag kind={row.source} />
      </span>
    )
  }

  function renderMeanCell(row: CompareRow) {
    if (!hasMeanColumn) {
      return <span className="text-mut">—</span>
    }
    if (row.mean_7d === null) {
      return <span className="text-mut">{t("compare.notEnoughData")}</span>
    }
    return <span className="text-text">{formatNumericValue(row.mean_7d, row.unit, lang, t)}</span>
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("nav.farm")}
        title={t("compare.title")}
        sub={t("compare.sub")}
      />

      <div className="flex flex-wrap items-center gap-2">
        {METRIC_CHIPS.map((chip) => (
          <ChoiceChip
            key={chip.key}
            selected={metric === chip.key}
            disabled={chip.disabled}
            badge={chip.disabled ? t("compare.phase2") : undefined}
            onClick={chip.disabled ? undefined : () => setMetric(chip.key)}
          >
            {t(chip.labelKey)}
          </ChoiceChip>
        ))}
      </div>

      {compareQuery.isError ? (
        <LoadError onRetry={() => void compareQuery.refetch()} />
      ) : (
        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
          {/* Left card: Yesterday */}
          <section className={`${cardClass} p-5`}>
            <h2 className="text-[15px] font-bold text-text">{t("compare.yesterday")}</h2>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full border-collapse text-[13px]">
                <thead>
                  <tr className="border-b border-line text-start text-[11px] font-semibold uppercase tracking-wider text-mut">
                    <th className="py-2 pe-4 text-start font-semibold">
                      {t("compare.colBlock")}
                    </th>
                    <th className="py-2 pe-4 text-start font-semibold">
                      {t("compare.colValue")}
                    </th>
                    <th className="py-2 pe-4 text-start font-semibold">
                      {t("compare.colPlan")}
                    </th>
                    <th className="py-2 text-start font-semibold">
                      {t("compare.colMean7d")}
                    </th>
                  </tr>
                </thead>
                {compareQuery.isPending ? (
                  <tbody className="divide-y divide-line">
                    {[0, 1, 2].map((idx) => (
                      <tr key={idx}>
                        <td className="py-3 pe-4">
                          <div className="h-4 w-28 animate-pulse rounded bg-[#E5E7EB]" />
                        </td>
                        <td className="py-3 pe-4">
                          <div className="h-4 w-24 animate-pulse rounded bg-[#E5E7EB]" />
                        </td>
                        <td className="py-3 pe-4">
                          <div className="h-4 w-10 animate-pulse rounded bg-[#E5E7EB]" />
                        </td>
                        <td className="py-3">
                          <div className="h-4 w-16 animate-pulse rounded bg-[#E5E7EB]" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                ) : rows.length >= 2 ? (
                  <tbody className="divide-y divide-line">
                    {rows.map((row) => (
                      <tr
                        key={row.block.id}
                        onClick={() => void navigate(`/blocks/${row.block.id}/overview`)}
                        className="group cursor-pointer transition-colors hover:bg-[#F9FBF9]"
                      >
                        <td className="py-3 pe-4 font-semibold text-text">
                          <Link
                            to={`/blocks/${row.block.id}/overview`}
                            onClick={(event) => event.stopPropagation()}
                            className="group-hover:underline"
                          >
                            {row.block.name}
                          </Link>
                        </td>
                        <td className="py-3 pe-4">{renderValueCell(row)}</td>
                        <td className="py-3 pe-4 text-mut">—</td>
                        <td className="py-3">{renderMeanCell(row)}</td>
                      </tr>
                    ))}
                  </tbody>
                ) : null}
              </table>
            </div>

            {!compareQuery.isPending && rows.length < 2 ? (
              <div className="flex flex-col items-center justify-center gap-1 py-8 text-center">
                <p className="text-[14px] font-bold text-text">{t("compare.emptyTitle")}</p>
                <p className="text-[13px] text-mut">{t("compare.emptyText")}</p>
              </div>
            ) : null}
          </section>

          {/* Right card: Same setting, different result */}
          <section className={`${cardClass} p-5`}>
            <h2 className="text-[15px] font-bold text-text">{t("compare.driftTitle")}</h2>
            <p className="mt-1.5 text-[13px] leading-relaxed text-mut">
              {t("compare.driftSub")}
            </p>

            {compareQuery.isPending ? (
              <div className="mt-4 h-4 w-32 animate-pulse rounded bg-[#E5E7EB]" />
            ) : flags.length === 0 ? (
              <p className="mt-4 text-[13px] text-mut">{t("compare.nothingFlagged")}</p>
            ) : (
              <ul className="mt-4 flex flex-col gap-2.5">
                {flags.map((flag, index) => (
                  <li
                    key={`${flag.message_code}-${flag.block_ids.join(",")}-${index}`}
                    className="rounded-xl border border-[#F59E0B]/25 bg-[#FEF3C7]/60 p-3 text-[13px]"
                  >
                    <div className="flex items-start gap-2">
                      <AlertTriangle
                        className="mt-0.5 size-4 shrink-0 text-amb"
                        aria-hidden="true"
                      />
                      <div className="min-w-0">
                        <p className="font-medium text-text">
                          {flag.block_ids.map((blockId, idx) => {
                            const name = blockNameById.get(blockId) ?? blockId
                            return (
                              <Fragment key={blockId}>
                                {idx > 0 ? ", " : null}
                                <Link
                                  to={`/blocks/${blockId}/overview`}
                                  className="font-semibold text-pri underline-offset-2 hover:underline"
                                >
                                  {name}
                                </Link>
                              </Fragment>
                            )
                          })}
                        </p>
                        <p className="mt-0.5 text-[12px] leading-snug text-mut">
                          {t(flagMessageKey(flag.message_code))}
                        </p>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
