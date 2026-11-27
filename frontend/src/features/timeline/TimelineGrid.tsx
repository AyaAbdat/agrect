import { AlertTriangle, ShoppingBasket } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"
import { formatNumber } from "../../lib/format"
import { cropLabel, localizedName } from "../blocks/types"
import { massText } from "../harvest/display"
import { operationTypeKey } from "../journal/display"
import { formatMediumDate } from "../weather/format"
import {
  dateToAxisPct,
  irrigationOpacity,
  monthLabels,
  type TimelineRowData,
} from "./model"
import { TimelineLegend } from "./TimelineLegend"

type ActiveTip = {
  rowId: string
  xPct: number
  title: string
  lines: string[]
}

function tipAlignClass(xPct: number): string {
  if (xPct < 14) return "left-0"
  if (xPct > 86) return "right-0"
  return "-translate-x-1/2"
}

function tipAnchorStyle(xPct: number): { left?: string; right?: string } {
  if (xPct < 14) return { left: `${Math.max(0, xPct)}%` }
  if (xPct > 86) return { right: `${Math.max(0, 100 - xPct)}%` }
  return { left: `${xPct}%` }
}

export function TimelineGrid({
  rows,
  years,
  todayIso,
  lang,
}: {
  rows: TimelineRowData[]
  years: number[]
  todayIso: string
  lang: string
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [activeTip, setActiveTip] = useState<ActiveTip | null>(null)
  const isRtl = lang === "ar"
  const months = monthLabels(lang)
  const totalMonths = years.length * 12
  const todayPct = dateToAxisPct(todayIso, years)
  const minTrackWidth = years.length > 1 ? "min-w-[1280px]" : "min-w-[760px]"

  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-white">
      <div className="overflow-x-auto" dir="ltr">
        <div className={`flex flex-col ${years.length > 1 ? "min-w-[1476px]" : "min-w-[956px]"}`}>
          {/* Header */}
          <div className="flex border-b border-line bg-white">
            <div
              className="sticky left-0 z-20 flex w-[196px] shrink-0 items-end border-r border-line bg-white px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-mut"
              dir={isRtl ? "rtl" : "ltr"}
            >
              {t("timeline.colBlock")}
            </div>
            <div className={`relative flex-1 ${minTrackWidth}`}>
              {/* Year header */}
              <div
                className="grid border-b border-line/70"
                style={{ gridTemplateColumns: `repeat(${years.length}, minmax(0, 1fr))` }}
              >
                {years.map((year, idx) => (
                  <div
                    key={year}
                    className={`px-2 py-1 text-center text-[11px] font-bold text-pri ${
                      idx > 0 ? "border-l border-line" : ""
                    }`}
                  >
                    {year}
                  </div>
                ))}
              </div>
              {/* Month header with week ticks */}
              <div
                className="grid"
                style={{ gridTemplateColumns: `repeat(${totalMonths}, minmax(0, 1fr))` }}
              >
                {years.flatMap((year, yearIdx) =>
                  months.map((label, monthIdx) => (
                    <div
                      key={`${year}-${monthIdx}`}
                      className={`relative py-1.5 text-center text-[11px] font-medium text-mut ${
                        monthIdx > 0 || yearIdx > 0 ? "border-l border-line/80" : ""
                      }`}
                    >
                      <span>{label}</span>
                      <span
                        aria-hidden="true"
                        className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-evenly"
                      >
                        <span className="h-1 w-px bg-line" />
                        <span className="h-1 w-px bg-line" />
                        <span className="h-1 w-px bg-line" />
                      </span>
                    </div>
                  )),
                )}
              </div>
              {/* Today tag on header */}
              {todayPct !== null ? (
                <div
                  className="pointer-events-none absolute top-0 bottom-0 z-20"
                  style={{ left: `${todayPct}%` }}
                >
                  <span
                    className="absolute top-0.5 -translate-x-1/2 rounded-full bg-red px-1.5 py-0.5 text-[9px] font-bold leading-none text-white shadow-xs"
                    dir={isRtl ? "rtl" : "ltr"}
                  >
                    {t("timeline.today")}
                  </span>
                </div>
              ) : null}
            </div>
          </div>

          {/* Rows */}
          <div className="divide-y divide-line">
            {rows.map((row, rowIndex) => {
              const cropName = cropLabel(row.block.crop, lang) ?? t("common.missing")
              const rowTip = activeTip?.rowId === row.block.id ? activeTip : null
              const tipBelow = rowIndex === 0 && rows.length > 1

              return (
                <div
                  key={row.block.id}
                  role="link"
                  tabIndex={0}
                  onClick={() => void navigate(`/blocks/${row.block.id}/overview`)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      void navigate(`/blocks/${row.block.id}/overview`)
                    }
                  }}
                  className="group flex cursor-pointer bg-white transition-colors hover:bg-[#F9FBF9] focus:bg-[#F9FBF9] focus:outline-none"
                >
                  {/* Sticky left block cell */}
                  <div
                    className="sticky left-0 z-10 flex w-[196px] shrink-0 items-center justify-between gap-2 border-r border-line bg-white px-4 py-2.5 group-hover:bg-[#F9FBF9] group-focus:bg-[#F9FBF9]"
                    dir={isRtl ? "rtl" : "ltr"}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span
                          className="inline-block size-2 shrink-0 rounded-full"
                          style={{ backgroundColor: row.palette.solid }}
                          aria-hidden="true"
                        />
                        <span className="truncate text-[13px] font-semibold text-text group-hover:underline">
                          {row.block.name}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-[11px] text-mut">{cropName}</p>
                    </div>
                    {row.partialError ? (
                      <span
                        className="inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-[#FEF3C7] text-amb"
                        title={t("timeline.partialRowWarning")}
                        aria-label={t("timeline.partialRowWarning")}
                      >
                        <AlertTriangle className="size-3" aria-hidden="true" />
                      </span>
                    ) : null}
                  </div>

                  {/* Timeline track */}
                  <div className={`relative h-[64px] flex-1 ${minTrackWidth}`}>
                    {/* Month + week background grid */}
                    <div
                      aria-hidden="true"
                      className="pointer-events-none absolute inset-0 grid"
                      style={{ gridTemplateColumns: `repeat(${totalMonths}, minmax(0, 1fr))` }}
                    >
                      {Array.from({ length: totalMonths }, (_, index) => (
                        <div
                          key={index}
                          className={`relative h-full ${index > 0 ? "border-l border-line/60" : ""}`}
                        >
                          <div className="absolute inset-y-0 left-1/4 w-px bg-line/25" />
                          <div className="absolute inset-y-0 left-1/2 w-px bg-line/25" />
                          <div className="absolute inset-y-0 left-3/4 w-px bg-line/25" />
                        </div>
                      ))}
                    </div>

                    {row.loading ? (
                      <div className="absolute inset-x-3 top-[23px] h-[16px] animate-pulse rounded-md bg-[#E5E7EB]" />
                    ) : (
                      <>
                        {/* Crop bars (lighter before first harvest, solid after) */}
                        {row.bars.map((bar) => {
                          const totalWidth = Math.max(0.4, bar.endPct - bar.startPct)
                          if (bar.splitPct === null) {
                            return (
                              <div
                                key={bar.year}
                                className="pointer-events-none absolute top-[22px] h-[18px] rounded-md"
                                style={{
                                  left: `${bar.startPct}%`,
                                  width: `${totalWidth}%`,
                                  backgroundColor: row.palette.light,
                                  boxShadow: `inset 0 0 0 1px ${row.palette.border}33`,
                                }}
                              />
                            )
                          }
                          const preWidth = Math.max(0, bar.splitPct - bar.startPct)
                          const postWidth = Math.max(0.4, bar.endPct - bar.splitPct)
                          return (
                            <div key={bar.year} className="pointer-events-none">
                              {preWidth > 0 ? (
                                <div
                                  className="absolute top-[22px] h-[18px] rounded-l-md"
                                  style={{
                                    left: `${bar.startPct}%`,
                                    width: `${preWidth}%`,
                                    backgroundColor: row.palette.light,
                                    boxShadow: `inset 0 0 0 1px ${row.palette.border}33`,
                                  }}
                                />
                              ) : null}
                              <div
                                className={`absolute top-[22px] h-[18px] ${
                                  preWidth > 0 ? "rounded-r-md" : "rounded-md"
                                }`}
                                style={{
                                  left: `${bar.splitPct}%`,
                                  width: `${postWidth}%`,
                                  backgroundColor: row.palette.solid,
                                }}
                              />
                            </div>
                          )
                        })}

                        {/* Operation ticks */}
                        {row.operations.map((op) => {
                          const typeLabel =
                            op.operationType !== null
                              ? t(operationTypeKey(op.operationType))
                              : t("journal.kind.operation")
                          const lines = [op.title]
                          if (op.details !== null && op.details !== "") {
                            lines.push(op.details)
                          }
                          lines.push(formatMediumDate(op.date, lang))
                          return (
                            <button
                              key={op.id}
                              type="button"
                              aria-label={`${typeLabel}: ${op.title}`}
                              onClick={(event) => event.stopPropagation()}
                              onMouseEnter={() =>
                                setActiveTip({
                                  rowId: row.block.id,
                                  xPct: op.xPct,
                                  title: typeLabel,
                                  lines,
                                })
                              }
                              onMouseLeave={() => setActiveTip(null)}
                              onFocus={() =>
                                setActiveTip({
                                  rowId: row.block.id,
                                  xPct: op.xPct,
                                  title: typeLabel,
                                  lines,
                                })
                              }
                              onBlur={() => setActiveTip(null)}
                              className="absolute top-[7px] z-10 flex h-[13px] w-[9px] -translate-x-1/2 items-center justify-center rounded-xs focus:outline-none focus:ring-2 focus:ring-pri"
                              style={{ left: `${op.xPct}%` }}
                            >
                              <span
                                className="block h-[10px] w-[3px] rounded-full"
                                style={{ backgroundColor: op.color }}
                              />
                            </button>
                          )
                        })}

                        {/* Confirmed stage dots */}
                        {row.stages.map((stage) => {
                          const stageTitle = `${stage.code} · ${localizedName(stage.name, lang)}`
                          const dateText = formatMediumDate(stage.date, lang)
                          return (
                            <button
                              key={stage.id}
                              type="button"
                              aria-label={`${stageTitle} (${dateText})`}
                              onClick={(event) => event.stopPropagation()}
                              onMouseEnter={() =>
                                setActiveTip({
                                  rowId: row.block.id,
                                  xPct: stage.xPct,
                                  title: stageTitle,
                                  lines: [dateText],
                                })
                              }
                              onMouseLeave={() => setActiveTip(null)}
                              onFocus={() =>
                                setActiveTip({
                                  rowId: row.block.id,
                                  xPct: stage.xPct,
                                  title: stageTitle,
                                  lines: [dateText],
                                })
                              }
                              onBlur={() => setActiveTip(null)}
                              className="absolute top-[31px] z-10 flex size-4 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full focus:outline-none focus:ring-2 focus:ring-pri"
                              style={{ left: `${stage.xPct}%` }}
                            >
                              <span className="block size-2.5 rounded-full border-[1.5px] border-white bg-pri shadow-xs" />
                            </button>
                          )
                        })}

                        {/* Harvest pass basket markers */}
                        {row.harvests.map((harvest) => {
                          const passTitle = t("timeline.tooltip.harvestPass", {
                            pass: formatNumber(harvest.passNo, 0, lang),
                          })
                          const kgLine = `${massText(harvest.kg, lang)} ${t("harvest.unit.kg")} · ${formatMediumDate(harvest.date, lang)}`
                          return (
                            <button
                              key={harvest.id}
                              type="button"
                              aria-label={`${passTitle}: ${kgLine}`}
                              onClick={(event) => event.stopPropagation()}
                              onMouseEnter={() =>
                                setActiveTip({
                                  rowId: row.block.id,
                                  xPct: harvest.xPct,
                                  title: passTitle,
                                  lines: [kgLine],
                                })
                              }
                              onMouseLeave={() => setActiveTip(null)}
                              onFocus={() =>
                                setActiveTip({
                                  rowId: row.block.id,
                                  xPct: harvest.xPct,
                                  title: passTitle,
                                  lines: [kgLine],
                                })
                              }
                              onBlur={() => setActiveTip(null)}
                              className="absolute top-[31px] z-10 flex size-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white text-pri shadow-xs ring-1 ring-pri/50 transition-transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-pri"
                              style={{ left: `${harvest.xPct}%` }}
                            >
                              <ShoppingBasket className="size-3" aria-hidden="true" />
                            </button>
                          )
                        })}

                        {/* Irrigation weekly density strip */}
                        <div
                          aria-hidden="true"
                          className="pointer-events-none absolute inset-x-0 bottom-[6px] h-[5px] bg-[#F3F4F6]"
                        />
                        {row.irrigations.map((bin) => {
                          const title = t("timeline.tooltip.irrigationWeek", {
                            week: formatNumber(bin.week, 0, lang),
                            year: String(bin.year),
                          })
                          const countLine = t("timeline.tooltip.irrigationCount", {
                            count: formatNumber(bin.count, 0, lang),
                          })
                          return (
                            <button
                              key={bin.key}
                              type="button"
                              aria-label={`${title}: ${countLine}`}
                              onClick={(event) => event.stopPropagation()}
                              onMouseEnter={() =>
                                setActiveTip({
                                  rowId: row.block.id,
                                  xPct: bin.startPct + bin.widthPct / 2,
                                  title,
                                  lines: [countLine],
                                })
                              }
                              onMouseLeave={() => setActiveTip(null)}
                              onFocus={() =>
                                setActiveTip({
                                  rowId: row.block.id,
                                  xPct: bin.startPct + bin.widthPct / 2,
                                  title,
                                  lines: [countLine],
                                })
                              }
                              onBlur={() => setActiveTip(null)}
                              className="absolute bottom-[5px] z-10 h-[7px] rounded-xs focus:outline-none focus:ring-1 focus:ring-pri"
                              style={{
                                left: `${bin.startPct}%`,
                                width: `${bin.widthPct}%`,
                                backgroundColor: "#0284C7",
                                opacity: irrigationOpacity(bin.count),
                              }}
                            />
                          )
                        })}
                      </>
                    )}

                    {/* Vertical Today line */}
                    {todayPct !== null ? (
                      <div
                        aria-hidden="true"
                        className="pointer-events-none absolute top-0 bottom-0 z-20 w-[1.5px] -translate-x-1/2 bg-red/85"
                        style={{ left: `${todayPct}%` }}
                      />
                    ) : null}

                    {/* Active hover/focus tooltip */}
                    {rowTip !== null ? (
                      <div
                        role="tooltip"
                        dir={isRtl ? "rtl" : "ltr"}
                        className={`pointer-events-none absolute z-30 w-max max-w-[260px] rounded-lg border border-line bg-white px-2.5 py-1.5 text-[11px] leading-snug shadow-md ${
                          tipBelow ? "top-[calc(100%-4px)]" : "bottom-[calc(100%-6px)]"
                        } ${tipAlignClass(rowTip.xPct)}`}
                        style={tipAnchorStyle(rowTip.xPct)}
                      >
                        <p className="font-semibold text-text">{rowTip.title}</p>
                        {rowTip.lines.map((line, index) => (
                          <p key={index} className="mt-0.5 text-mut">
                            {line}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <TimelineLegend />
    </section>
  )
}
