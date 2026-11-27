import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useAuth } from "../../app/auth"
import { apiGet, apiSend } from "../../lib/api"
import { formatMediumDate } from "../weather/format"
import { activeLang } from "../blocks/types"
import { ConfirmDialog } from "../station/dialog"
import { LoadError, PageSkeleton, cardClass, outlineBtn, primaryBtn } from "../weather/ui"
import type { Product, ProductList } from "../journal/types"
import { AdjustDrawer } from "./AdjustDrawer"
import { PurchaseDrawer } from "./PurchaseDrawer"
import { amount } from "./money"
import type { Stock, StockMove, StockMoveList } from "./types"

function MoveRow({
  move,
  productName,
  lang,
  onDelete,
}: {
  move: StockMove
  productName: string
  lang: string
  onDelete: (move: StockMove) => void
}) {
  const { t } = useTranslation()
  return (
    <tr className="border-b border-line last:border-b-0">
      <td className="py-2" dir="ltr">
        {formatMediumDate(move.date, lang)}
      </td>
      <td className="py-2 font-semibold">{productName}</td>
      <td className="py-2">{t(`inventories.kinds.${move.kind}`)}</td>
      <td className="py-2" dir="ltr">
        {amount(move.qty, lang)}
      </td>
      <td className="py-2 text-end">
        {move.kind === "use" ? (
          <span className="text-[12px] text-mut">{t("inventories.stock.fromOperation")}</span>
        ) : (
          <button
            type="button"
            className="text-[12px] font-semibold text-red"
            onClick={() => onDelete(move)}
          >
            {t("journal.delete")}
          </button>
        )}
      </td>
    </tr>
  )
}

export function StockTab() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId
  const [purchaseOpen, setPurchaseOpen] = useState(false)
  const [adjustOpen, setAdjustOpen] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<StockMove | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const stockQuery = useQuery({
    queryKey: ["stock", farmId],
    queryFn: () => apiGet<Stock>(`/v1/farms/${farmId}/stock`),
    enabled: farmId !== null,
  })
  const movesQuery = useQuery({
    queryKey: ["stock-moves", farmId],
    queryFn: () => apiGet<StockMoveList>(`/v1/farms/${farmId}/stock-moves`),
    enabled: farmId !== null,
  })
  const productsQuery = useQuery({
    queryKey: ["products", farmId],
    queryFn: () => apiGet<ProductList>(`/v1/farms/${farmId}/products`),
    enabled: farmId !== null,
  })

  if (farmId === null) return null
  if (stockQuery.isLoading || movesQuery.isLoading || productsQuery.isLoading) {
    return <PageSkeleton />
  }
  if (
    stockQuery.isError ||
    movesQuery.isError ||
    productsQuery.isError ||
    stockQuery.data === undefined ||
    movesQuery.data === undefined ||
    productsQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void stockQuery.refetch()
          void movesQuery.refetch()
          void productsQuery.refetch()
        }}
      />
    )
  }

  const items = stockQuery.data.items
  const moves = movesQuery.data.moves
  const products: Product[] = productsQuery.data.products
  const productName = (id: string) => products.find((row) => row.id === id)?.name ?? "—"

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["stock", farmId] })
    void queryClient.invalidateQueries({ queryKey: ["stock-moves", farmId] })
  }

  async function confirmDelete() {
    if (pendingDelete === null) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiSend("DELETE", `/v1/stock-moves/${pendingDelete.id}`)
    } catch {
      setDeleting(false)
      setDeleteError("inventories.errors.save")
      return
    }
    setDeleting(false)
    setPendingDelete(null)
    refresh()
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end gap-2">
        <button
          type="button"
          className={outlineBtn}
          onClick={() => setAdjustOpen(true)}
          disabled={products.length === 0}
        >
          {t("inventories.stock.adjust")}
        </button>
        <button
          type="button"
          className={primaryBtn}
          onClick={() => setPurchaseOpen(true)}
          disabled={products.length === 0}
        >
          {t("inventories.stock.recordPurchase")}
        </button>
      </div>
      <section className={cardClass}>
        {items.length === 0 ? (
          <p className="px-2 py-10 text-center text-[13px] text-mut">{t("inventories.stock.empty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-start text-[13px]">
              <thead className="text-[11px] uppercase tracking-wide text-mut">
                <tr className="border-b border-line">
                  <th className="py-2 text-start font-semibold">{t("inventories.stock.product")}</th>
                  <th className="py-2 text-start font-semibold">{t("inventories.stock.onHand")}</th>
                  <th className="py-2 text-start font-semibold">{t("inventories.stock.uses")}</th>
                  <th className="py-2 text-start font-semibold">
                    {t("inventories.stock.lastPurchase")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.product_id} className="border-b border-line last:border-b-0">
                    <td className="py-3 font-semibold">
                      <span className="flex items-center gap-2">
                        {row.product_name}
                        {row.unit_mismatch_count > 0 ? (
                          <span
                            className="rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[10px] font-semibold text-amb"
                            title={t("inventories.stock.mismatchTip")}
                          >
                            {t("inventories.stock.mismatchBadge", {
                              count: row.unit_mismatch_count,
                            })}
                          </span>
                        ) : null}
                      </span>
                    </td>
                    <td className="py-3" dir="ltr">
                      {amount(row.on_hand, lang)} {t(`journal.units.${row.unit}`)}
                    </td>
                    <td className="py-3" dir="ltr">
                      {amount(row.uses_this_season, lang)}
                    </td>
                    <td className="py-3" dir="ltr">
                      {row.last_purchase === null ? "—" : formatMediumDate(row.last_purchase, lang)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section className={cardClass}>
        <h2 className="text-[14px] font-bold">{t("inventories.stock.movesTitle")}</h2>
        {moves.length === 0 ? (
          <p className="px-2 py-6 text-center text-[13px] text-mut">{t("inventories.stock.noMoves")}</p>
        ) : (
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[640px] text-start text-[13px]">
              <thead className="text-[11px] uppercase tracking-wide text-mut">
                <tr className="border-b border-line">
                  <th className="py-2 text-start font-semibold">{t("inventories.date")}</th>
                  <th className="py-2 text-start font-semibold">{t("inventories.stock.product")}</th>
                  <th className="py-2 text-start font-semibold">{t("inventories.stock.kind")}</th>
                  <th className="py-2 text-start font-semibold">{t("inventories.stock.quantity")}</th>
                  <th className="py-2 text-end font-semibold">
                    <span className="sr-only">{t("journal.rowMenu")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {moves.map((move) => (
                  <MoveRow
                    key={move.id}
                    move={move}
                    productName={productName(move.product_id)}
                    lang={lang}
                    onDelete={setPendingDelete}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <PurchaseDrawer
        open={purchaseOpen}
        onOpenChange={setPurchaseOpen}
        farmId={farmId}
        products={products}
        onSaved={refresh}
      />
      <AdjustDrawer
        open={adjustOpen}
        onOpenChange={setAdjustOpen}
        farmId={farmId}
        products={products}
        onSaved={refresh}
      />
      {pendingDelete !== null ? (
        <ConfirmDialog
          title={t("inventories.stock.deleteTitle")}
          text={t("inventories.stock.deleteText")}
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
