import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "../../app/auth"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import { LoadError, PageSkeleton, cardClass, outlineBtn, primaryBtn } from "../weather/ui"
import { teamErrorKey } from "./errors"
import type { Worker, WorkerList } from "./types"
import { WorkerDrawer } from "./WorkerDrawer"

export function WorkersTab() {
  const { t } = useTranslation()
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editing, setEditing] = useState<Worker | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Worker | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [workerInUse, setWorkerInUse] = useState(false)

  const workersQuery = useQuery({
    queryKey: ["workers", farmId],
    queryFn: () => apiGet<WorkerList>(`/v1/farms/${farmId}/workers`),
    enabled: farmId !== null,
  })

  if (farmId === null) return null
  if (workersQuery.isLoading) return <PageSkeleton />
  if (workersQuery.isError || workersQuery.data === undefined) {
    return (
      <LoadError
        onRetry={() => void queryClient.invalidateQueries({ queryKey: ["workers", farmId] })}
      />
    )
  }

  const workers = workersQuery.data.workers

  function openCreate() {
    setEditing(null)
    setDrawerOpen(true)
  }

  function closeDeleteDialog() {
    setPendingDelete(null)
    setDeleteError(null)
    setWorkerInUse(false)
  }

  async function confirmDelete() {
    if (pendingDelete === null) return
    setDeleting(true)
    setDeleteError(null)
    setWorkerInUse(false)
    try {
      await apiSend("DELETE", `/v1/workers/${pendingDelete.id}`, undefined, {
        "If-Match": String(pendingDelete.version),
      })
    } catch (error) {
      setDeleting(false)
      if (error instanceof ApiError && error.code === "labour.worker_in_use") {
        setWorkerInUse(true)
        return
      }
      setDeleteError(error instanceof ApiError ? teamErrorKey(error.code) : "team.errors.save")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["workers", farmId] })
    setDeleting(false)
    closeDeleteDialog()
  }

  async function markInactive() {
    if (pendingDelete === null) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiSend<Worker>(
        "PATCH",
        `/v1/workers/${pendingDelete.id}`,
        { active: false },
        { "If-Match": String(pendingDelete.version) },
      )
    } catch (error) {
      setDeleting(false)
      setDeleteError(error instanceof ApiError ? teamErrorKey(error.code) : "team.errors.save")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["workers", farmId] })
    setDeleting(false)
    closeDeleteDialog()
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <button type="button" className={primaryBtn} onClick={openCreate}>
          {t("team.workers.add")}
        </button>
      </div>

      <section className={cardClass}>
        {workers.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
            <p className="text-[16px] font-bold">{t("team.workers.emptyTitle")}</p>
            <p className="max-w-[420px] text-[13px] text-mut">{t("team.workers.emptyText")}</p>
            <button type="button" className={outlineBtn} onClick={openCreate}>
              {t("team.workers.add")}
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-start text-[13px]">
              <thead className="text-[11px] uppercase tracking-wide text-mut">
                <tr className="border-b border-line">
                  <th className="py-2 text-start font-semibold">{t("team.workers.name")}</th>
                  <th className="py-2 text-start font-semibold">{t("team.workers.role")}</th>
                  <th className="py-2 text-start font-semibold">{t("team.workers.kind")}</th>
                  <th className="py-2 text-start font-semibold">{t("team.workers.phone")}</th>
                  <th className="py-2 text-start font-semibold">{t("team.workers.active")}</th>
                  <th className="py-2 text-end font-semibold">
                    <span className="sr-only">{t("journal.rowMenu")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {workers.map((row) => (
                  <tr key={row.id} className="border-b border-line last:border-b-0">
                    <td className="py-3 font-semibold">{row.name}</td>
                    <td className="py-3">{t(`team.roles.${row.role}`)}</td>
                    <td className="py-3">{t(`team.kinds.${row.kind}`)}</td>
                    <td className="py-3" dir="ltr">
                      {row.phone ?? t("common.missing")}
                    </td>
                    <td className="py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                          row.active
                            ? "bg-mint text-pri"
                            : "bg-[#E5E7EB] text-mut"
                        }`}
                      >
                        {t(row.active ? "team.workers.statusActive" : "team.workers.statusInactive")}
                      </span>
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
                              setWorkerInUse(false)
                            }}
                          >
                            {t("journal.delete")}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <WorkerDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        farmId={farmId}
        worker={editing}
        onSaved={() => void queryClient.invalidateQueries({ queryKey: ["workers", farmId] })}
      />

      {pendingDelete !== null ? (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="worker-delete-title"
            className="w-full max-w-sm rounded-2xl bg-white p-5"
          >
            <h2 id="worker-delete-title" className="text-[16px] font-bold">
              {t("team.workers.deleteTitle")}
            </h2>
            {workerInUse ? (
              <p className="mt-2 text-[13px] text-mut">{t("team.workers.inUseText")}</p>
            ) : (
              <p className="mt-2 text-[13px] text-mut">
                {t("team.workers.deleteText", { name: pendingDelete.name })}
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
                {t("journal.cancel")}
              </button>
              {workerInUse ? (
                <button
                  type="button"
                  className={`${primaryBtn} disabled:opacity-60`}
                  onClick={() => void markInactive()}
                  disabled={deleting}
                >
                  {t("team.workers.markInactive")}
                </button>
              ) : (
                <button
                  type="button"
                  className={`${primaryBtn} disabled:opacity-60`}
                  onClick={() => void confirmDelete()}
                  disabled={deleting}
                >
                  {t("journal.delete")}
                </button>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
