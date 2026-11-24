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
import { apiGet, apiSend } from "../../lib/api"
import { ConfirmDialog } from "../station/dialog"
import { LoadError, PageHeader, PageSkeleton, cardClass, primaryBtn } from "../weather/ui"
import { ProductDrawer } from "./ProductDrawer"
import type { Product, ProductList } from "./types"

export function ProductsPage() {
  const { t } = useTranslation()
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editing, setEditing] = useState<Product | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Product | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const productsQuery = useQuery({
    queryKey: ["products", farmId],
    queryFn: () => apiGet<ProductList>(`/v1/farms/${farmId}/products`),
    enabled: farmId !== null,
  })

  if (farmId === null) return null
  if (productsQuery.isLoading) return <PageSkeleton />
  if (productsQuery.isError || productsQuery.data === undefined) {
    return (
      <LoadError
        onRetry={() => void queryClient.invalidateQueries({ queryKey: ["products", farmId] })}
      />
    )
  }

  const products = productsQuery.data.products

  function openCreate() {
    setEditing(null)
    setDrawerOpen(true)
  }

  async function confirmDelete() {
    if (pendingDelete === null) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiSend("DELETE", `/v1/products/${pendingDelete.id}`, undefined, {
        "If-Match": String(pendingDelete.version),
      })
    } catch {
      setDeleting(false)
      setDeleteError("journal.errors.save")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["products", farmId] })
    setDeleting(false)
    setPendingDelete(null)
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("settings.title")}
        title={t("settings.inventories")}
        sub={t("journal.productsSub")}
        actions={
          <button type="button" className={primaryBtn} onClick={openCreate}>
            {t("journal.newProduct")}
          </button>
        }
      />
      <section className={cardClass}>
        {products.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
            <p className="text-[16px] font-bold">{t("journal.productsEmptyTitle")}</p>
            <p className="max-w-[420px] text-[13px] text-mut">{t("journal.productsEmptyText")}</p>
            <button type="button" className={primaryBtn} onClick={openCreate}>
              {t("journal.newProduct")}
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-start text-[13px]">
              <thead className="text-[11px] uppercase tracking-wide text-mut">
                <tr className="border-b border-line">
                  <th className="py-2 text-start font-semibold">{t("journal.productName")}</th>
                  <th className="py-2 text-start font-semibold">{t("journal.productKind")}</th>
                  <th className="py-2 text-start font-semibold">{t("journal.productUnit")}</th>
                  <th className="py-2 text-start font-semibold">{t("journal.phiDays")}</th>
                  <th className="py-2 text-start font-semibold">{t("journal.reentryHours")}</th>
                  <th className="py-2 text-end font-semibold">
                    <span className="sr-only">{t("journal.rowMenu")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {products.map((row) => (
                  <tr key={row.id} className="border-b border-line last:border-b-0">
                    <td className="py-3 font-semibold">{row.name}</td>
                    <td className="py-3">{t(`journal.productKinds.${row.kind}`)}</td>
                    <td className="py-3">{t(`journal.units.${row.unit}`)}</td>
                    <td className="py-3" dir="ltr">
                      {row.preharvest_interval_days ?? "—"}
                    </td>
                    <td className="py-3" dir="ltr">
                      {row.reentry_h ?? "—"}
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
                          <DropdownMenuItem onClick={() => setPendingDelete(row)}>
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
      <ProductDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        farmId={farmId}
        product={editing}
        onSaved={() => void productsQuery.refetch()}
      />
      {pendingDelete !== null ? (
        <ConfirmDialog
          title={t("journal.deleteProductTitle")}
          text={t("journal.deleteProductText")}
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