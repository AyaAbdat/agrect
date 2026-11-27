import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "../../app/auth"
import { apiGet, apiSend } from "../../lib/api"
import { activeLang, type BlockDetail } from "../blocks/types"
import { money } from "../inventories/money"
import { RegisterHarvestDrawer } from "../harvest/RegisterHarvestDrawer"
import type { HarvestEntry, HarvestList } from "../harvest/types"
import { ConfirmDialog } from "../station/dialog"
import { LogIrrigationDrawer } from "../soilwater/LogIrrigationDrawer"
import type { FarmClock, IrrigationEvent, IrrigationEvents } from "../soilwater/types"
import { weekRange } from "../soilwater/period"
import { farmToday, formatMediumDate } from "../weather/format"
import {
  ChoiceChip,
  LoadError,
  PageHeader,
  PageSkeleton,
  cardClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import {
  groupByOperationType,
  isoWeekText,
  itemTypeKey,
  journalTypesQuery,
  labourDetailsText,
  machinesDetailsText,
  operationTypeKey,
  sourceBadgeClass,
  sourceKey,
  warningKey,
  warningText,
} from "./display"
import { ExportJournalDrawer } from "./ExportJournalDrawer"
import { NewEntryDrawer } from "./NewEntryDrawer"
import type {
  JournalItem,
  JournalList,
  JournalTypeFilter,
  JournalViewTab,
  Operation,
  OperationList,
  OperationType,
} from "./types"

const CHIP_FILTERS: JournalTypeFilter[] = [
  "all",
  "fertigation",
  "treatment",
  "foliar",
  "irrigation",
  "weed",
  "pruning",
  "thinning",
  "harvest",
  "stages",
  "more",
]

function JournalSourceTag({ kind }: { kind: JournalItem["source"] }) {
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

function journalPath(blockId: string, from: string | null, to: string | null, types: string | null) {
  const params = new URLSearchParams()
  if (from !== null) params.set("from", from)
  if (to !== null) params.set("to", to)
  if (types !== null) params.set("types", types)
  const query = params.toString()
  return query === "" ? `/v1/blocks/${blockId}/journal` : `/v1/blocks/${blockId}/journal?${query}`
}

export function JournalPage() {
  const { t, i18n } = useTranslation()
  const { blockId } = useParams()
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const farmId = currentFarmId
  const [tab, setTab] = useState<JournalViewTab>("crop")
  const [filter, setFilter] = useState<JournalTypeFilter>("all")
  const [weekFrom, setWeekFrom] = useState<string>("")
  const [weekTo, setWeekTo] = useState<string>("")
  const [entryOpen, setEntryOpen] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const [entryType, setEntryType] = useState<OperationType | null>(null)
  const [editingOperation, setEditingOperation] = useState<Operation | null>(null)
  const [irrigationOpen, setIrrigationOpen] = useState(false)
  const [harvestOpen, setHarvestOpen] = useState(false)
  const [irrigationEvent, setIrrigationEvent] = useState<IrrigationEvent | null>(null)
  const [harvestEntry, setHarvestEntry] = useState<HarvestEntry | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Operation | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const today = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)
  const typesParam = journalTypesQuery(filter)
  const fromParam = weekFrom.trim() === "" ? null : weekFrom
  const toParam = weekTo.trim() === "" ? null : weekTo
  const journalQuery = useQuery({
    queryKey: ["journal", blockId, fromParam, toParam, typesParam],
    queryFn: () =>
      apiGet<JournalList>(journalPath(blockId ?? "", fromParam, toParam, typesParam)),
    enabled: blockId !== undefined,
  })
  const operationsQuery = useQuery({
    queryKey: ["operations", farmId, blockId, fromParam, toParam],
    queryFn: () => {
      const params = new URLSearchParams()
      if (blockId !== undefined) params.set("block_id", blockId)
      if (fromParam !== null) params.set("from", fromParam)
      if (toParam !== null) params.set("to", toParam)
      return apiGet<OperationList>(`/v1/farms/${farmId}/operations?${params.toString()}`)
    },
    enabled: farmId !== null && blockId !== undefined,
  })
  const operationById = useMemo(
    () => new Map((operationsQuery.data?.operations ?? []).map((row) => [row.id, row])),
    [operationsQuery.data],
  )
  const eventsQuery = useQuery({
    queryKey: ["irrigation-events", blockId, "all"],
    queryFn: () => apiGet<IrrigationEvents>(`/v1/blocks/${blockId}/irrigation-events`),
    enabled: blockId !== undefined,
  })
  const harvestQuery = useQuery({
    queryKey: ["harvest", blockId],
    queryFn: () => apiGet<HarvestList>(`/v1/blocks/${blockId}/harvest`),
    enabled: blockId !== undefined,
  })
  const items = journalQuery.data?.items ?? []
  const grouped = useMemo(() => groupByOperationType(items), [items])

  if (blockId === undefined || farmId === null) return null
  if (
    farmQuery.isPending ||
    blockQuery.isPending ||
    journalQuery.isLoading ||
    farmQuery.data === undefined ||
    blockQuery.data === undefined
  ) {
    return <PageSkeleton />
  }
  if (farmQuery.isError || blockQuery.isError || journalQuery.isError || journalQuery.data === undefined) {
    return (
      <LoadError
        onRetry={() => {
          void queryClient.invalidateQueries({ queryKey: ["farm", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["block", blockId] })
          void queryClient.invalidateQueries({ queryKey: ["journal", blockId] })
        }}
      />
    )
  }

  const block = blockQuery.data
  const zone = farmQuery.data.timezone
  const empty = items.length === 0

  function openCreate() {
    setEditingOperation(null)
    setEntryType(null)
    setEntryOpen(true)
  }

  function openOperationEdit(id: string) {
    void apiGet<Operation>(`/v1/operations/${id}`).then((body) => {
      setEditingOperation(body)
      setEntryType(body.type)
      setEntryOpen(true)
    })
  }

  function openIrrigation(item: JournalItem) {
    const event = eventsQuery.data?.events.find((row) => row.id === item.link_id) ?? null
    setIrrigationEvent(event)
    setIrrigationOpen(true)
  }

  function openHarvest(item: JournalItem) {
    const entry = harvestQuery.data?.entries.find((row) => row.id === item.link_id) ?? null
    setHarvestEntry(entry)
    setHarvestOpen(true)
  }

  async function confirmDelete() {
    if (pendingDelete === null) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiSend("DELETE", `/v1/operations/${pendingDelete.id}`, undefined, {
        "If-Match": String(pendingDelete.version),
      })
    } catch {
      setDeleting(false)
      setDeleteError("journal.errors.save")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["journal", blockId] })
    await queryClient.invalidateQueries({ queryKey: ["operations", farmId, blockId] })
    await queryClient.invalidateQueries({ queryKey: ["labour-norms", farmId] })
    await queryClient.invalidateQueries({ queryKey: ["machines", farmId] })
    await queryClient.invalidateQueries({ queryKey: ["machine"] })
    await queryClient.invalidateQueries({ queryKey: ["maintenance-due", farmId] })
    setDeleting(false)
    setPendingDelete(null)
  }

  function setThisWeek() {
    if (today === null) return
    const range = weekRange(today)
    setWeekFrom(range.from)
    setWeekTo(range.to)
  }

  function RowList({ rows }: { rows: JournalItem[] }) {
    return (
      <ul className="divide-y divide-line">
        {rows.map((item) => (
          <li key={`${item.kind}-${item.link_id}`} className="flex flex-wrap items-start gap-3 py-3">
            <div className="min-w-[120px]">
              <p className="text-[13px] font-semibold">{formatMediumDate(item.date, lang)}</p>
              <p className="text-[11px] text-mut" dir="ltr">
                {t("journal.isoWeek", { week: isoWeekText(item.date, lang) })}
              </p>
            </div>
            <span className="inline-flex rounded-full border border-line px-2 py-0.5 text-[11px] font-semibold">
              {t(itemTypeKey(item))}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold">{item.title}</p>
              {(() => {
                const op = item.kind === "operation" ? operationById.get(item.link_id) : undefined
                const labour =
                  item.kind === "operation" ? (item.labour ?? op?.labour ?? null) : null
                const machines =
                  item.kind === "operation" ? (item.machines ?? op?.machines ?? []) : []
                const labourLine = labourDetailsText(labour, lang, t)
                const machinesLine = machinesDetailsText(machines, lang, t)
                const detailParts = [item.details, labourLine, machinesLine].filter(
                  (part): part is string => part !== null && part !== "",
                )
                return detailParts.length > 0 ? (
                  <p className="text-[12px] text-mut">{detailParts.join(" · ")}</p>
                ) : null
              })()}
              {item.cost_dzd !== null ? (
                <p className="text-[12px] text-mut" dir="ltr">
                  {money(item.cost_dzd, lang)} {t("common.dzd")}
                </p>
              ) : null}
              {item.warnings.map((warning, index) => (
                <p key={warningKey(warning, index)} className="text-[12px] text-amb">
                  {warningText(warning, t)}
                </p>
              ))}
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <JournalSourceTag kind={item.source} />
              </div>
            </div>
            <div className="ms-auto flex flex-wrap items-center gap-2">
              {item.kind === "operation" ? (
                <DropdownMenu>
                  <DropdownMenuTrigger
                    className="inline-flex size-8 items-center justify-center rounded-full text-[16px] text-mut"
                    aria-label={t("journal.rowMenu")}
                  >
                    ⋯
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => openOperationEdit(item.link_id)}>
                      {t("journal.edit")}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        void apiGet<Operation>(`/v1/operations/${item.link_id}`).then(setPendingDelete)
                      }}
                    >
                      {t("journal.delete")}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
              {item.kind === "irrigation" ? (
                <button type="button" className={outlineBtn} onClick={() => openIrrigation(item)}>
                  {t("journal.open")}
                </button>
              ) : null}
              {item.kind === "harvest" ? (
                <button type="button" className={outlineBtn} onClick={() => openHarvest(item)}>
                  {t("journal.open")}
                </button>
              ) : null}
              {item.kind === "stage" ? (
                <Link
                  to={`/blocks/${blockId}/stages/${item.link_id}`}
                  className={`inline-flex items-center ${outlineBtn}`}
                >
                  {t("journal.openStage")}
                </Link>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("nav.block")}
        title={t("journal.title")}
        sub={t("journal.sub")}
        actions={
          <>
            <button type="button" className={outlineBtn} onClick={() => setExportOpen(true)}>
              {t("journal.exportPdf")}
            </button>
            <button type="button" className={primaryBtn} onClick={openCreate}>
              {t("journal.newEntry")}
            </button>
          </>
        }
      />

      <div className="flex flex-wrap gap-2">
        <ChoiceChip selected={tab === "crop"} onClick={() => setTab("crop")}>
          {t("journal.tabByCrop")}
        </ChoiceChip>
        <ChoiceChip selected={tab === "operation"} onClick={() => setTab("operation")}>
          {t("journal.tabByOperation")}
        </ChoiceChip>
      </div>

      <div className="flex flex-wrap gap-2">
        {CHIP_FILTERS.map((chip) => (
          <ChoiceChip
            key={chip}
            selected={filter === chip}
            onClick={() => setFilter(chip)}
            badge={chip === "more" ? t("journal.more") : undefined}
          >
            {chip === "treatment"
              ? t("journal.types.treatment")
              : chip === "weed"
                ? t("journal.types.weed")
                : chip === "thinning"
                  ? t("journal.types.thinning")
                  : chip === "stages"
                    ? t("journal.kind.stage")
                    : chip === "more"
                      ? t("journal.moreTypes")
                      : t(
                          chip === "all"
                            ? "journal.filterAll"
                            : chip === "foliar"
                              ? "journal.types.foliar"
                              : chip === "irrigation"
                                ? "journal.types.irrigation"
                                : chip === "harvest"
                                  ? "journal.types.harvest"
                                  : `journal.types.${chip}`,
                        )}
          </ChoiceChip>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="block">
          <span className="mb-1.5 block text-[13px] font-semibold">{t("journal.weeksFilter")}</span>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="date"
              dir="ltr"
              lang="en"
              className="h-9 rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px]"
              value={weekFrom}
              onChange={(change) => setWeekFrom(change.target.value)}
            />
            <span className="text-mut">–</span>
            <input
              type="date"
              dir="ltr"
              lang="en"
              className="h-9 rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px]"
              value={weekTo}
              onChange={(change) => setWeekTo(change.target.value)}
            />
            <button type="button" className={outlineBtn} onClick={setThisWeek}>
              {t("journal.thisWeek")}
            </button>
            <button
              type="button"
              className={outlineBtn}
              onClick={() => {
                setWeekFrom("")
                setWeekTo("")
              }}
            >
              {t("journal.clearWeeks")}
            </button>
          </div>
        </label>
      </div>

      <section className={cardClass}>
        {empty ? (
          <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
            <p className="text-[16px] font-bold">{t("journal.emptyTitle")}</p>
            <p className="max-w-[480px] text-[13px] text-mut">{t("journal.emptyText")}</p>
            <button type="button" className={primaryBtn} onClick={openCreate}>
              {t("journal.newEntry")}
            </button>
          </div>
        ) : tab === "crop" ? (
          <RowList rows={items} />
        ) : (
          <div className="flex flex-col gap-4">
            {grouped.map((group) => (
              <div key={group.key}>
                <h3 className="text-[14px] font-bold">
                  {t(
                    group.key === "irrigation" ||
                      group.key === "harvest" ||
                      group.key === "stage"
                      ? `journal.kind.${group.key}`
                      : operationTypeKey(group.key as OperationType),
                  )}
                </h3>
                <RowList rows={group.items} />
              </div>
            ))}
          </div>
        )}
      </section>

      <ExportJournalDrawer
        open={exportOpen}
        onOpenChange={setExportOpen}
        blockId={blockId}
        blockName={block.name}
        today={today ?? ""}
      />
      <NewEntryDrawer
        open={entryOpen}
        onOpenChange={setEntryOpen}
        farmId={farmId}
        block={block}
        blockId={blockId}
        timeZone={zone}
        operation={editingOperation}
        initialType={entryType}
        onOpenIrrigation={() => {
          setIrrigationEvent(null)
          setIrrigationOpen(true)
        }}
        onOpenHarvest={() => {
          setHarvestEntry(null)
          setHarvestOpen(true)
        }}
        onSaved={() => void journalQuery.refetch()}
      />
      <LogIrrigationDrawer
        open={irrigationOpen}
        onOpenChange={setIrrigationOpen}
        blockId={blockId}
        blockName={block.name}
        valves={block.valves}
        timeZone={zone}
        today={today ?? ""}
        event={irrigationEvent}
      />
      <RegisterHarvestDrawer
        open={harvestOpen}
        onOpenChange={setHarvestOpen}
        farmId={farmId}
        blocks={[block]}
        timeZone={zone}
        entry={harvestEntry}
        entryBlock={block}
      />
      {pendingDelete !== null ? (
        <ConfirmDialog
          title={t("journal.deleteTitle")}
          text={t("journal.deleteText")}
          cancelLabel={t("journal.cancel")}
          confirmLabel={t("journal.delete")}
          pending={deleting}
          error={deleteError === null ? null : t(deleteError)}
          onCancel={() => {
            setPendingDelete(null)
            setDeleteError(null)
          }}
          onConfirm={() => void confirmDelete()}
        />
      ) : null}
    </div>
  )
}