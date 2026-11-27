import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate, useParams, useSearchParams } from "react-router"
import { useAuth } from "../../app/auth"
import { LogoMark } from "../../components/LogoMark"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { varietyName } from "../blocks/display"
import {
  activeLang,
  cropLabel,
  localizedName,
  type BlockDetail,
  type BlockValve,
  type CatalogVariety,
} from "../blocks/types"
import type { HarvestEntry, HarvestList } from "../harvest/types"
import { money } from "../inventories/money"
import { runClock } from "../soilwater/display"
import type { IrrigationEvent, IrrigationEvents } from "../soilwater/types"
import type { CatalogStage, CropStages } from "../stages/types"
import { asNumber, formatMediumDate, shiftIsoDate } from "../weather/format"
import { LoadError, outlineBtn, primaryBtn } from "../weather/ui"
import {
  isoWeekText,
  itemTypeKey,
  m3FromWaterLiters,
  sourceKey,
  totalOnAreaText,
  unitLabel,
  warningKey,
  warningText,
} from "./display"
import type {
  JournalItem,
  JournalList,
  Operation,
  OperationList,
  OperationProductLine,
} from "./types"

type FarmMeta = {
  id?: string
  name?: string
  timezone: string
}

function journalPath(
  blockId: string,
  from: string | null,
  to: string | null,
  types: string | null,
): string {
  const params = new URLSearchParams()
  if (from !== null) params.set("from", from)
  if (to !== null) params.set("to", to)
  if (types !== null) params.set("types", types)
  const query = params.toString()
  return query === ""
    ? `/v1/blocks/${blockId}/journal`
    : `/v1/blocks/${blockId}/journal?${query}`
}

function operationsPath(
  farmId: string,
  blockId: string,
  from: string | null,
  to: string | null,
): string {
  const params = new URLSearchParams()
  params.set("block_id", blockId)
  if (from !== null) params.set("from", from)
  if (to !== null) params.set("to", to)
  return `/v1/farms/${farmId}/operations?${params.toString()}`
}

function parseTypes(raw: string | null): Set<string> | null {
  if (raw === null || raw.trim() === "") return null
  const tokens = raw
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part !== "")
  return tokens.length === 0 ? null : new Set(tokens)
}

function includesKind(wanted: Set<string> | null, kind: string): boolean {
  if (wanted === null) return true
  if (kind === "stage") return wanted.has("stage") || wanted.has("stages")
  return wanted.has(kind)
}

function groupByMonth(items: JournalItem[]): { monthKey: string; items: JournalItem[] }[] {
  const groups = new Map<string, JournalItem[]>()
  for (const item of items) {
    const key = item.date.slice(0, 7)
    const list = groups.get(key) ?? []
    list.push(item)
    groups.set(key, list)
  }
  return [...groups.entries()].map(([monthKey, rows]) => ({ monthKey, items: rows }))
}

function formatMonthHeading(monthKey: string, lang: string): string {
  const [year, month] = monthKey.split("-").map(Number)
  const date = new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, 15, 12))
  return new Intl.DateTimeFormat(`${lang}-u-nu-latn`, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date)
}

function formatGeneratedAt(date: Date, timeZone: string, lang: string): string {
  return new Intl.DateTimeFormat(`${lang}-u-nu-latn`, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone,
  }).format(date)
}

function formatRate(value: string, lang: string): string {
  const parsed = asNumber(value)
  if (parsed === null) return "—"
  const decimals = Number.isInteger(parsed) ? 0 : 2
  return formatNumber(parsed, decimals, lang)
}

function valveNames(valveIds: string[], valves: BlockValve[]): string[] {
  if (valveIds.length === 0) return []
  const byId = new Map(valves.map((v) => [v.id, v.name]))
  return valveIds.map((id) => byId.get(id)).filter((name): name is string => name !== undefined)
}

function OperationDetails({
  item,
  operation,
  valves,
  lang,
}: {
  item: JournalItem
  operation: Operation | undefined
  valves: BlockValve[]
  lang: string
}) {
  const { t } = useTranslation()
  if (operation === undefined) {
    return (
      <div className="flex flex-col gap-0.5">
        <p className="font-medium">{item.title}</p>
        {item.details !== null ? <p className="text-[11px]">{item.details}</p> : null}
      </div>
    )
  }

  const names = valveNames(operation.valve_ids, valves)

  function productSummary(line: OperationProductLine): string {
    const rate = `${formatRate(line.rate, lang)} ${unitLabel(line.rate_unit, t)} (${t(`journal.rateBasis.${line.rate_basis}`)})`
    const parts = [line.product_name, rate]
    if (line.water_l_ha !== null) {
      const m3Text = m3FromWaterLiters(line.water_l_ha)
      const m3Num = asNumber(m3Text)
      if (m3Num !== null) {
        parts.push(
          t("journal.print.waterM3Ha", {
            m3: formatNumber(m3Num, Number.isInteger(m3Num) ? 0 : 2, lang),
          }),
        )
      }
    }
    const total = totalOnAreaText(line.total_qty, line.total_unit, operation?.area_ha ?? "", lang, t)
    if (total !== "—") parts.push(total)
    return parts.join(" · ")
  }

  return (
    <div className="flex flex-col gap-0.5">
      {operation.products.map((line) => (
        <p key={line.id}>{productSummary(line)}</p>
      ))}
      {operation.target !== null && operation.target.trim() !== "" ? (
        <p>
          <span className="font-semibold">{t("journal.target")}:</span> {operation.target}
        </p>
      ) : null}
      {names.length > 0 ? (
        <p>
          <span className="font-semibold">{t("journal.valves")}:</span> {names.join(", ")}
        </p>
      ) : null}
      {operation.products.length === 0 &&
      (operation.target === null || operation.target.trim() === "") &&
      names.length === 0 ? (
        <p>{operation.notes !== null && operation.notes.trim() !== "" ? operation.notes : "—"}</p>
      ) : null}
      {item.warnings.map((warning, index) => (
        <p key={warningKey(warning, index)} className="font-semibold">
          {warningText(warning, t)}
        </p>
      ))}
    </div>
  )
}

function IrrigationDetails({
  item,
  event,
  valves,
  lang,
}: {
  item: JournalItem
  event: IrrigationEvent | undefined
  valves: BlockValve[]
  lang: string
}) {
  const { t } = useTranslation()
  if (event === undefined) {
    return (
      <div className="flex flex-col gap-0.5">
        <p>{item.title}</p>
        {item.details !== null ? <p>{item.details}</p> : null}
      </div>
    )
  }
  const names = valveNames(event.valve_ids, valves)
  return (
    <div className="flex flex-col gap-0.5">
      <p>
        {t("journal.print.irrigationLine", {
          duration: runClock(event.duration_min, lang),
          depth: formatNumber(asNumber(event.depth_mm), 1, lang),
          volume: formatNumber(asNumber(event.volume_m3), 1, lang),
        })}
      </p>
      {names.length > 0 ? (
        <p>
          <span className="font-semibold">{t("journal.valves")}:</span> {names.join(", ")}
        </p>
      ) : null}
    </div>
  )
}

function HarvestDetails({
  item,
  entry,
  lang,
}: {
  item: JournalItem
  entry: HarvestEntry | undefined
  lang: string
}) {
  const { t } = useTranslation()
  if (entry === undefined) {
    return (
      <div className="flex flex-col gap-0.5">
        <p>{item.title}</p>
        {item.details !== null ? <p>{item.details}</p> : null}
      </div>
    )
  }
  const warning = entry.preharvest_warning
  return (
    <div className="flex flex-col gap-0.5">
      <p>
        {t("journal.print.harvestLine", {
          pass: formatNumber(entry.pass_no, 0, lang),
          kg: formatNumber(asNumber(entry.kg), 0, lang),
          kgHa: formatNumber(asNumber(entry.kg_ha), 0, lang),
        })}
      </p>
      {warning !== null ? (
        <p className="font-bold">
          {t("harvest.preharvestWarning", {
            product: warning.product,
            sprayDate: formatMediumDate(warning.spray_date, lang),
            daysSince: formatNumber(warning.days_since, 0, lang),
            daysNeeded: formatNumber(warning.days_needed, 0, lang),
          })}
        </p>
      ) : null}
    </div>
  )
}

function StageDetails({
  item,
  stage,
  lang,
}: {
  item: JournalItem
  stage: CatalogStage | undefined
  lang: string
}) {
  const { t } = useTranslation()
  if (stage !== undefined) {
    return (
      <p>
        {t("journal.print.stageLine", {
          name: localizedName(stage.name, lang),
          code: stage.code,
        })}
      </p>
    )
  }
  return (
    <p>
      {t("journal.print.stageFallback", {
        title: item.details !== null ? `${item.title} (${item.details})` : item.title,
      })}
    </p>
  )
}

export function JournalPrintPage() {
  const { t, i18n } = useTranslation()
  const { blockId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { user, currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const generatedAt = useMemo(() => new Date(), [])

  const fromParam = searchParams.get("from")?.trim() || null
  const toParam = searchParams.get("to")?.trim() || null
  const typesParam = searchParams.get("types")?.trim() || null
  const wantedTypes = useMemo(() => parseTypes(typesParam), [typesParam])
  const wantOperations = includesKind(wantedTypes, "operation")
  const wantIrrigations = includesKind(wantedTypes, "irrigation")
  const wantHarvests = includesKind(wantedTypes, "harvest")
  const wantStages = includesKind(wantedTypes, "stage")

  const farmQuery = useQuery({
    queryKey: ["farm", currentFarmId],
    queryFn: () => apiGet<FarmMeta>(`/v1/farms/${currentFarmId}`),
    enabled: currentFarmId !== null,
  })
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const cropId = blockQuery.data?.crop?.id ?? null
  const varietiesQuery = useQuery({
    queryKey: ["catalog", "varieties", cropId],
    queryFn: () => apiGet<CatalogVariety[]>(`/v1/catalog/crops/${cropId}/varieties`),
    enabled: cropId !== null,
  })
  const journalQuery = useQuery({
    queryKey: ["journal", blockId, fromParam, toParam, typesParam],
    queryFn: () =>
      apiGet<JournalList>(journalPath(blockId ?? "", fromParam, toParam, typesParam)),
    enabled: blockId !== undefined,
  })
  const operationsQuery = useQuery({
    queryKey: ["operations", currentFarmId, blockId, fromParam, toParam],
    queryFn: () =>
      apiGet<OperationList>(
        operationsPath(currentFarmId ?? "", blockId ?? "", fromParam, toParam),
      ),
    enabled: currentFarmId !== null && blockId !== undefined && wantOperations,
  })
  const irrigationQuery = useQuery({
    queryKey: ["irrigation-events", blockId, "all"],
    queryFn: () => apiGet<IrrigationEvents>(`/v1/blocks/${blockId}/irrigation-events`),
    enabled: blockId !== undefined && wantIrrigations,
  })
  const harvestQuery = useQuery({
    queryKey: ["harvest", blockId],
    queryFn: () => apiGet<HarvestList>(`/v1/blocks/${blockId}/harvest`),
    enabled: blockId !== undefined && wantHarvests,
  })
  const stagesQuery = useQuery({
    queryKey: ["catalog", "stages", cropId],
    queryFn: () => apiGet<CropStages>(`/v1/catalog/crops/${cropId}/stages`),
    enabled: cropId !== null && wantStages,
  })

  const operationsById = useMemo(
    () => new Map((operationsQuery.data?.operations ?? []).map((row) => [row.id, row])),
    [operationsQuery.data],
  )
  const irrigationsById = useMemo(
    () => new Map((irrigationQuery.data?.events ?? []).map((row) => [row.id, row])),
    [irrigationQuery.data],
  )
  const harvestsById = useMemo(
    () => new Map((harvestQuery.data?.entries ?? []).map((row) => [row.id, row])),
    [harvestQuery.data],
  )
  const stagesById = useMemo(
    () => new Map((stagesQuery.data?.stages ?? []).map((row) => [row.id, row])),
    [stagesQuery.data],
  )

  const monthGroups = useMemo(
    () => groupByMonth(journalQuery.data?.items ?? []),
    [journalQuery.data],
  )

  if (blockId === undefined || currentFarmId === null) return null

  const loading =
    farmQuery.isPending ||
    blockQuery.isPending ||
    journalQuery.isPending ||
    (wantOperations && operationsQuery.isPending) ||
    (wantIrrigations && irrigationQuery.isPending) ||
    (wantHarvests && harvestQuery.isPending)

  const hasError =
    farmQuery.isError ||
    blockQuery.isError ||
    journalQuery.isError ||
    farmQuery.data === undefined ||
    blockQuery.data === undefined ||
    journalQuery.data === undefined

  const backToJournal = () => {
    void navigate(`/blocks/${blockId}/journal`)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-bg p-6">
        <div className="print-toolbar mx-auto mb-4 flex max-w-[210mm] items-center justify-between print:hidden">
          <button type="button" className={outlineBtn} onClick={backToJournal}>
            {t("journal.print.back")}
          </button>
        </div>
        <div className="mx-auto max-w-[210mm] rounded-xl border border-line bg-white p-8 text-center text-mut">
          {t("common.loading")}
        </div>
      </div>
    )
  }

  if (hasError) {
    return (
      <div className="min-h-screen bg-bg p-6">
        <div className="print-toolbar mx-auto mb-4 flex max-w-[210mm] items-center justify-between print:hidden">
          <button type="button" className={outlineBtn} onClick={backToJournal}>
            {t("journal.print.back")}
          </button>
        </div>
        <div className="mx-auto max-w-[210mm]">
          <LoadError
            onRetry={() => {
              void queryClient.invalidateQueries({ queryKey: ["farm", currentFarmId] })
              void queryClient.invalidateQueries({ queryKey: ["block", blockId] })
              void queryClient.invalidateQueries({ queryKey: ["journal", blockId] })
            }}
          />
        </div>
      </div>
    )
  }

  const block = blockQuery.data
  const farm = farmQuery.data
  const farmName =
    farm.name ?? user?.farms.find((item) => item.id === currentFarmId)?.name ?? t("common.missing")
  const missing = t("common.missing")
  const crop = cropLabel(block.crop, lang) ?? missing
  const variety = varietyName(block.plantings[0], varietiesQuery.data ?? []) ?? missing
  const areaNum = asNumber(block.net_area_ha)
  const areaText =
    areaNum === null
      ? missing
      : t("journal.print.areaHa", { area: formatNumber(areaNum, 2, lang) })

  const periodText =
    fromParam !== null && toParam !== null
      ? t("journal.print.periodRange", {
          from: formatMediumDate(fromParam, lang),
          to: formatMediumDate(toParam, lang),
        })
      : fromParam !== null
        ? t("journal.print.fromOnly", { from: formatMediumDate(fromParam, lang) })
        : toParam !== null
          ? t("journal.print.toOnly", { to: formatMediumDate(toParam, lang) })
          : t("journal.print.allDates")

  const generatedText = formatGeneratedAt(generatedAt, farm.timezone, lang)
  const items = journalQuery.data.items

  function renderPhi(item: JournalItem): string {
    if (item.kind !== "operation") return "—"
    const op = operationsById.get(item.link_id)
    const days = op?.safety?.preharvest_interval_days
    if (op === undefined || days === null || days === undefined) return "—"
    const clearDate = shiftIsoDate(op.date, days)
    return t("journal.print.phiCell", {
      days: formatNumber(days, 0, lang),
      date: formatMediumDate(clearDate, lang),
    })
  }

  return (
    <div className="journal-print-root min-h-screen bg-bg px-4 py-6 text-text print:bg-white print:p-0">
      <div className="print-toolbar mx-auto mb-4 flex max-w-[210mm] items-center justify-between gap-3 print:hidden">
        <button type="button" className={outlineBtn} onClick={backToJournal}>
          {t("journal.print.back")}
        </button>
        <button
          type="button"
          className={primaryBtn}
          onClick={() => window.print()}
        >
          {t("journal.print.printButton")}
        </button>
      </div>

      <article className="journal-print-sheet mx-auto max-w-[210mm] rounded-xl border border-line bg-white p-8 shadow-sm print:max-w-none print:rounded-none print:border-0 print:p-0 print:shadow-none">
        <header className="mb-5 border-b border-line pb-4 print:border-black">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <LogoMark size={30} />
              <div>
                <p className="text-[11px] font-bold tracking-wider uppercase text-mut print:text-black">
                  {t("app.name")}
                </p>
                <h1 className="text-[20px] font-bold leading-tight">
                  {t("journal.print.docTitle")}
                </h1>
              </div>
            </div>
            <div className="text-end text-[11px]">
              <p>
                <span className="font-semibold">{t("journal.print.periodLabel")}:</span>{" "}
                {periodText}
              </p>
              <p>
                <span className="font-semibold">{t("journal.print.generatedAt")}:</span>{" "}
                <span dir="ltr">{generatedText}</span>
              </p>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-baseline justify-between gap-2 text-[12px]">
            <div>
              <p className="font-semibold">
                {farmName} · {block.name}
              </p>
              <p className="text-mut print:text-black">
                {crop} · {variety} · {areaText}
              </p>
            </div>
          </div>
        </header>

        {items.length === 0 ? (
          <p className="py-10 text-center text-[13px] text-mut print:text-black">
            {t("journal.print.empty")}
          </p>
        ) : (
          <table className="journal-print-table w-full border-collapse text-start text-[11px]">
            <thead>
              <tr>
                <th className="w-[15%]">{t("journal.print.colDate")}</th>
                <th className="w-[14%]">{t("journal.print.colType")}</th>
                <th className="w-[37%]">{t("journal.print.colDetails")}</th>
                <th className="w-[14%]">{t("journal.print.colPhi")}</th>
                <th className="w-[11%] text-end">{t("journal.print.colCost")}</th>
                <th className="w-[9%]">{t("journal.print.colSource")}</th>
              </tr>
            </thead>
            {monthGroups.map((group) => (
              <tbody key={group.monthKey}>
                <tr className="journal-print-month">
                  <th colSpan={6} className="text-start font-bold">
                    {formatMonthHeading(group.monthKey, lang)}
                  </th>
                </tr>
                {group.items.map((item) => (
                  <tr key={`${item.kind}-${item.link_id}-${item.date}`}>
                    <td className="align-top">
                      <p className="font-semibold">{formatMediumDate(item.date, lang)}</p>
                      <p className="text-[10px] text-mut print:text-black" dir="ltr">
                        {t("journal.isoWeek", { week: isoWeekText(item.date, lang) })}
                      </p>
                    </td>
                    <td className="align-top font-medium">{t(itemTypeKey(item))}</td>
                    <td className="align-top">
                      {item.kind === "operation" ? (
                        <OperationDetails
                          item={item}
                          operation={operationsById.get(item.link_id)}
                          valves={block.valves}
                          lang={lang}
                        />
                      ) : item.kind === "irrigation" ? (
                        <IrrigationDetails
                          item={item}
                          event={irrigationsById.get(item.link_id)}
                          valves={block.valves}
                          lang={lang}
                        />
                      ) : item.kind === "harvest" ? (
                        <HarvestDetails
                          item={item}
                          entry={harvestsById.get(item.link_id)}
                          lang={lang}
                        />
                      ) : (
                        <StageDetails
                          item={item}
                          stage={stagesById.get(item.link_id)}
                          lang={lang}
                        />
                      )}
                    </td>
                    <td className="align-top">{renderPhi(item)}</td>
                    <td className="align-top text-end" dir="ltr">
                      {item.cost_dzd !== null
                        ? `${money(item.cost_dzd, lang)} ${t("common.dzd")}`
                        : "—"}
                    </td>
                    <td className="align-top">
                      {item.source !== null ? t(sourceKey(item.source)) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        )}

        <footer className="mt-6 border-t border-line pt-3 text-[10px] text-mut print:border-black print:text-black">
          <p>{t("journal.print.footerNote")}</p>
        </footer>
      </article>
    </div>
  )
}
