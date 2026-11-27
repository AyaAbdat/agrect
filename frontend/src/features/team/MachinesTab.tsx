import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "../../app/auth"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { activeLang } from "../blocks/types"
import { asNumber, formatMediumDate } from "../weather/format"
import { LoadError, PageSkeleton, SourceTag, cardClass, outlineBtn, primaryBtn } from "../weather/ui"
import { teamErrorKey } from "./errors"
import { MachineDrawer } from "./MachineDrawer"
import type { Machine, MachineDetail, MachineList, MaintenanceItem } from "./types"

function pickNextMaintenance(items: MaintenanceItem[]): MaintenanceItem | null {
  const candidates = items.filter(
    (item) =>
      item.due.overdue ||
      item.due.due_by_hours ||
      item.due.due_by_date ||
      item.due.next_due_date !== null ||
      item.due.next_due_h !== null,
  )
  if (candidates.length === 0) return null
  const rank = (item: MaintenanceItem): number => {
    if (item.due.overdue) return 0
    if (item.due.due_by_hours || item.due.due_by_date) return 1
    return 2
  }
  return [...candidates].sort((left, right) => {
    const rankDiff = rank(left) - rank(right)
    if (rankDiff !== 0) return rankDiff
    if (left.due.next_due_date !== null && right.due.next_due_date !== null) {
      if (left.due.next_due_date !== right.due.next_due_date) {
        return left.due.next_due_date.localeCompare(right.due.next_due_date)
      }
    } else if (left.due.next_due_date !== null) {
      return -1
    } else if (right.due.next_due_date !== null) {
      return 1
    }
    const leftH = asNumber(left.due.next_due_h)
    const rightH = asNumber(right.due.next_due_h)
    if (leftH !== null && rightH !== null && leftH !== rightH) return leftH - rightH
    return left.task.localeCompare(right.task)
  })[0]
}

function formatDueText(
  item: MaintenanceItem,
  lang: string,
  t: (key: string, opts?: Record<string, string>) => string,
): string {
  const parts: string[] = []
  if (item.due.next_due_date !== null) {
    parts.push(formatMediumDate(item.due.next_due_date, lang))
  }
  if (item.due.next_due_h !== null) {
    parts.push(
      t("team.machines.hoursValue", {
        hours: formatNumber(asNumber(item.due.next_due_h), 0, lang),
      }),
    )
  }
  return parts.length > 0 ? parts.join(" · ") : t("common.missing")
}

export function MachinesTab() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editing, setEditing] = useState<Machine | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Machine | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [machineInUse, setMachineInUse] = useState(false)

  const machinesQuery = useQuery({
    queryKey: ["machines", farmId],
    queryFn: () => apiGet<MachineList>(`/v1/farms/${farmId}/machines`),
    enabled: farmId !== null,
  })
  const machines = machinesQuery.data?.machines ?? []
  const detailQueries = useQueries({
    queries: machines.map((machine) => ({
      queryKey: ["machine", machine.id],
      queryFn: () => apiGet<MachineDetail>(`/v1/machines/${machine.id}`),
    })),
  })

  if (farmId === null) return null
  if (machinesQuery.isLoading) return <PageSkeleton />
  if (machinesQuery.isError || machinesQuery.data === undefined) {
    return (
      <LoadError
        onRetry={() => void queryClient.invalidateQueries({ queryKey: ["machines", farmId] })}
      />
    )
  }

  function openCreate() {
    setEditing(null)
    setDrawerOpen(true)
  }

  function closeDeleteDialog() {
    setPendingDelete(null)
    setDeleteError(null)
    setMachineInUse(false)
  }

  async function confirmDelete() {
    if (pendingDelete === null) return
    setDeleting(true)
    setDeleteError(null)
    setMachineInUse(false)
    try {
      await apiSend("DELETE", `/v1/machines/${pendingDelete.id}`, undefined, {
        "If-Match": String(pendingDelete.version),
      })
    } catch (error) {
      setDeleting(false)
      if (error instanceof ApiError && error.code === "equipment.machine_in_use") {
        setMachineInUse(true)
        return
      }
      setDeleteError(error instanceof ApiError ? teamErrorKey(error.code) : "team.errors.save")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["machines", farmId] })
    await queryClient.invalidateQueries({ queryKey: ["maintenance-due", farmId] })
    setDeleting(false)
    closeDeleteDialog()
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <button type="button" className={primaryBtn} onClick={openCreate}>
          {t("team.machines.add")}
        </button>
      </div>

      <section className={cardClass}>
        {machines.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
            <p className="text-[16px] font-bold">{t("team.machines.emptyTitle")}</p>
            <p className="max-w-[420px] text-[13px] text-mut">{t("team.machines.emptyText")}</p>
            <button type="button" className={outlineBtn} onClick={openCreate}>
              {t("team.machines.add")}
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-start text-[13px]">
              <thead className="text-[11px] uppercase tracking-wide text-mut">
                <tr className="border-b border-line">
                  <th className="py-2 text-start font-semibold">{t("team.machines.name")}</th>
                  <th className="py-2 text-start font-semibold">{t("team.machines.type")}</th>
                  <th className="py-2 text-start font-semibold">{t("team.machines.status")}</th>
                  <th className="py-2 text-start font-semibold">
                    {t("team.machines.engineHours")}
                  </th>
                  <th className="py-2 text-start font-semibold">
                    {t("team.machines.nextMaintenance")}
                  </th>
                  <th className="py-2 text-end font-semibold">
                    <span className="sr-only">{t("journal.rowMenu")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {machines.map((row, index) => {
                  const detailQuery = detailQueries[index]
                  const detail = detailQuery?.data
                  const nextTask = detail !== undefined ? pickNextMaintenance(detail.maintenance) : null
                  const isOverdue = nextTask?.due.overdue === true
                  const isDue =
                    nextTask !== null && (nextTask.due.due_by_hours || nextTask.due.due_by_date)
                  return (
                    <tr key={row.id} className="border-b border-line last:border-b-0">
                      <td className="py-3 font-semibold">
                        <Link to={`/team/machines/${row.id}`} className="text-pri hover:underline">
                          {row.name}
                        </Link>
                      </td>
                      <td className="py-3">{t(`team.machines.types.${row.type}`)}</td>
                      <td className="py-3">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                            row.status === "ok"
                              ? "bg-mint text-pri"
                              : "bg-[#FEF3C7] text-amb"
                          }`}
                        >
                          {t(`team.machines.statuses.${row.status}`)}
                        </span>
                      </td>
                      <td className="py-3">
                        {detailQuery?.isLoading ? (
                          <span className="inline-block h-4 w-16 animate-pulse rounded bg-[#E5E7EB]" />
                        ) : detail?.current_engine_hours != null ? (
                          <span className="inline-flex items-center gap-1.5">
                            <span dir="ltr">
                              {t("team.machines.hoursValue", {
                                hours: formatNumber(
                                  asNumber(detail.current_engine_hours),
                                  1,
                                  lang,
                                ),
                              })}
                            </span>
                            <SourceTag kind="calculated" />
                          </span>
                        ) : (
                          <span className="text-mut">{t("common.missing")}</span>
                        )}
                      </td>
                      <td className="py-3">
                        {detailQuery?.isLoading ? (
                          <span className="inline-block h-4 w-24 animate-pulse rounded bg-[#E5E7EB]" />
                        ) : nextTask === null ? (
                          <span className="text-mut">{t("common.missing")}</span>
                        ) : (
                          <span
                            className={
                              isOverdue
                                ? "font-semibold text-red"
                                : isDue
                                  ? "font-semibold text-amb"
                                  : "text-text"
                            }
                          >
                            {nextTask.task} ·{" "}
                            <span dir="ltr">{formatDueText(nextTask, lang, t)}</span>
                          </span>
                        )}
                      </td>
                      <td className="py-3 text-end">
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            className="inline-flex size-8 items-center justify-center rounded-full text-[16px] text-mut"
                            aria-label={t("journal.rowMenu")}
                          >
                            ⋯
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => {
                                setEditing(row)
                                setDrawerOpen(true)
                              }}
                            >
                              {t("journal.edit")}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => {
                                setPendingDelete(row)
                                setDeleteError(null)
                                setMachineInUse(false)
                              }}
                            >
                              {t("journal.delete")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <MachineDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        farmId={farmId}
        machine={editing}
        onSaved={() => {
          void queryClient.invalidateQueries({ queryKey: ["machines", farmId] })
          if (editing !== null) {
            void queryClient.invalidateQueries({ queryKey: ["machine", editing.id] })
          }
          void queryClient.invalidateQueries({ queryKey: ["maintenance-due", farmId] })
        }}
      />

      {pendingDelete !== null ? (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="machine-delete-title"
            className="w-full max-w-sm rounded-2xl bg-white p-5"
          >
            <h2 id="machine-delete-title" className="text-[16px] font-bold">
              {t("team.machines.deleteTitle")}
            </h2>
            {machineInUse ? (
              <p className="mt-2 text-[13px] text-mut">{t("team.machines.errors.inUse")}</p>
            ) : (
              <p className="mt-2 text-[13px] text-mut">
                {t("team.machines.deleteText", { name: pendingDelete.name })}
              </p>
            )}
            {deleteError !== null ? (
              <p className="mt-2 text-[12px] text-red">{t(deleteError)}</p>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className={outlineBtn}
                onClick={closeDeleteDialog}
                disabled={deleting}
              >
                {t(machineInUse ? "drawer.close" : "journal.cancel")}
              </button>
              {!machineInUse ? (
                <button
                  type="button"
                  className={`${primaryBtn} disabled:opacity-60`}
                  onClick={() => void confirmDelete()}
                  disabled={deleting}
                >
                  {t("journal.delete")}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
