import { useQuery } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useNavigate } from "react-router"
import { SatelliteMap } from "../../components/map/SatelliteMap"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { crumbClass } from "../../lib/navStyles"
import { StationSideCard } from "../station/StationSideCard"
import { ErrorRow, LoadingRow } from "./Status"
import { activeLang, cropLabel, type BlockListItem } from "./types"

const chipClass = "inline-flex h-8 items-center rounded-full px-4 text-[12px] font-semibold"
const addClass =
  "inline-flex h-9 items-center rounded-full bg-pri px-4 text-[13px] font-semibold text-white"

function SideCards() {
  const { t } = useTranslation()
  return (
    <aside className="flex w-[340px] shrink-0 flex-col gap-4">
      <StationSideCard />
      <section className="rounded-2xl border border-line bg-white p-4">
        <h2 className="text-[16px] font-bold">{t("nav.stages")}</h2>
        <p className="mt-1 text-mut">{t("blocks.stagesText")}</p>
        <p className="mt-3">{t("common.missing")}</p>
      </section>
    </aside>
  )
}

function BlockList({ blocks }: { blocks: BlockListItem[] }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  if (blocks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <p className="text-[16px] font-bold">{t("nav.noBlocks")}</p>
        <Link to="/blocks/new" className={addClass}>
          {t("blocks.add")}
        </Link>
      </div>
    )
  }
  return (
    <ul>
      {blocks.map((block, index) => {
        const crop = cropLabel(block.crop, lang)
        const area =
          block.net_area_ha === null
            ? t("common.missing")
            : t("blocks.netLine", {
                area: formatNumber(Number(block.net_area_ha), 2, lang),
              })
        const trees =
          block.trees_count === null
            ? t("common.missing")
            : t("blocks.trees", { count: formatNumber(block.trees_count, 0, lang) })
        const flow =
          block.q_block_m3h === null
            ? t("common.missing")
            : `${formatNumber(Number(block.q_block_m3h), 2, lang)} ${t("blocks.unitFlow")}`
        return (
          <li key={block.id} className="border-b border-line last:border-b-0">
            <button
              type="button"
              className="flex w-full items-center gap-3 px-4 py-3 text-start hover:bg-[#F7F8F7]"
              onClick={() => void navigate(`/blocks/${block.id}/setup`)}
            >
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-mint text-[12px] font-bold text-pri">
                {formatNumber(index + 1, 0, lang)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-bold">{block.name}</span>
                <span className="block text-mut">
                  {crop ?? t("common.missing")}
                  <span className="px-1">·</span>
                  {area}
                </span>
              </span>
              <span className="shrink-0 text-[12px] text-mut">
                {trees}
                <span className="px-1">·</span>
                {flow}
              </span>
              {block.status === "draft" ? (
                <span className="shrink-0 rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[11px] font-semibold text-amb">
                  {t("blocks.draft")}
                </span>
              ) : null}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export function BlocksPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { currentFarmId } = useAuth()
  const [view, setView] = useState<"map" | "list">("map")
  const blocksQuery = useQuery({
    queryKey: ["blocks", currentFarmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${currentFarmId}/blocks`),
    enabled: currentFarmId !== null,
  })
  const blocks = blocksQuery.data ?? []
  const activeChip = `${chipClass} bg-pri text-white`
  const idleChip = `${chipClass} border border-line bg-white text-text`

  let panel = <LoadingRow />
  if (blocksQuery.isError) {
    panel = <ErrorRow onRetry={() => void blocksQuery.refetch()} />
  } else if (blocksQuery.isSuccess && view === "list") {
    panel = (
      <section className="rounded-2xl border border-line bg-white">
        <h2 className="border-b border-line px-4 py-3 text-[16px] font-bold">
          {t("blocks.listTitle")}
        </h2>
        <BlockList blocks={blocks} />
      </section>
    )
  } else if (blocksQuery.isSuccess) {
    panel = (
      <div className="relative">
        <SatelliteMap
          height={600}
          blocks={blocks}
          onBlockClick={(id) => void navigate(`/blocks/${id}/setup`)}
        />
        {blocks.length === 0 ? (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center p-6">
            <div className="pointer-events-auto flex w-full max-w-[420px] flex-col items-center gap-3 rounded-2xl bg-white px-8 py-8 text-center shadow-sm">
              <div className="flex size-12 items-center justify-center rounded-full bg-mint text-pri">
                <Plus className="size-5" aria-hidden="true" />
              </div>
              <p className="text-[16px] font-bold">{t("blocks.emptyTitle")}</p>
              <p className="text-mut">{t("blocks.emptyText")}</p>
              <Link to="/blocks/new" className={addClass}>
                {t("blocks.add")}
              </Link>
            </div>
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className={crumbClass}>{t("nav.farm")}</p>
          <h1 className="text-[24px] font-bold leading-tight">{t("nav.blocks")}</h1>
          <p className="mt-1 text-mut">{t("blocks.sub")}</p>
        </div>
        <Link to="/blocks/new" className={addClass}>
          {t("blocks.add")}
        </Link>
      </header>
      <div className="flex items-start gap-5">
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <div className="flex gap-2">
            <button
              type="button"
              className={view === "map" ? activeChip : idleChip}
              onClick={() => setView("map")}
            >
              {t("blocks.map")}
            </button>
            <button
              type="button"
              className={view === "list" ? activeChip : idleChip}
              onClick={() => setView("list")}
            >
              {t("blocks.list")}
            </button>
          </div>
          {panel}
        </div>
        <SideCards />
      </div>
    </div>
  )
}
