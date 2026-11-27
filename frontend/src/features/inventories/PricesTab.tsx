import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useAuth } from "../../app/auth"
import { apiGet, apiSend } from "../../lib/api"
import { activeLang } from "../blocks/types"
import type { Product, ProductList } from "../journal/types"
import { formatMediumDate } from "../weather/format"
import { LoadError, PageSkeleton, cardClass, outlineBtn, primaryBtn } from "../weather/ui"
import { PriceDrawer } from "./PriceDrawer"
import { ReasonDialog } from "./ReasonDialog"
import { unitPrice } from "./money"
import type { Price, PriceList, PriceResource } from "./types"

const RESOURCES: PriceResource[] = [
  "water_m3",
  "labour_h",
  "machine_h",
  "fuel_l",
  "energy_kwh",
]

function latest(prices: Price[]): Price[] {
  return [...prices].sort((a, b) => (a.valid_from < b.valid_from ? 1 : -1))
}

export function PricesTab() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId
  const [drawer, setDrawer] = useState<{ resource: PriceResource; price: Price | null } | null>(
    null,
  )
  const [deleteTarget, setDeleteTarget] = useState<Price | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const pricesQuery = useQuery({
    queryKey: ["prices", farmId],
    queryFn: () => apiGet<PriceList>(`/v1/farms/${farmId}/prices`),
    enabled: farmId !== null,
  })
  const productsQuery = useQuery({
    queryKey: ["products", farmId],
    queryFn: () => apiGet<ProductList>(`/v1/farms/${farmId}/products`),
    enabled: farmId !== null,
  })

  if (farmId === null) return null
  if (pricesQuery.isLoading || productsQuery.isLoading) return <PageSkeleton />
  if (
    pricesQuery.isError ||
    productsQuery.isError ||
    pricesQuery.data === undefined ||
    productsQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void pricesQuery.refetch()
          void productsQuery.refetch()
        }}
      />
    )
  }

  const prices = pricesQuery.data.prices
  const products: Product[] = productsQuery.data.products
  const productName = (id: string | null) =>
    products.find((row) => row.id === id)?.name ?? "—"

  const byProduct = new Map<string, Price[]>()
  for (const price of prices) {
    if (price.resource !== "product" || price.product_id === null) continue
    const list = byProduct.get(price.product_id) ?? []
    list.push(price)
    byProduct.set(price.product_id, list)
  }
  const productIds = [...byProduct.keys()].sort((a, b) =>
    productName(a).localeCompare(productName(b)),
  )

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["prices", farmId] })
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function confirmDelete(reason: string) {
    if (deleteTarget === null) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiSend(
        "DELETE",
        `/v1/prices/${deleteTarget.id}?reason=${encodeURIComponent(reason)}`,
        undefined,
        { "If-Match": String(deleteTarget.version) },
      )
    } catch {
      setDeleting(false)
      setDeleteError("inventories.errors.save")
      return
    }
    setDeleting(false)
    setDeleteTarget(null)
    refresh()
  }

  const resourcePrice = (resource: PriceResource): Price | null => {
    const list = latest(prices.filter((row) => row.resource === resource))
    return list[0] ?? null
  }

  return (
    <div className="flex flex-col gap-3">
      <section className={cardClass}>
        <div className="flex items-center justify-between">
          <h2 className="text-[14px] font-bold">{t("inventories.prices.products")}</h2>
          <button
            type="button"
            className={primaryBtn}
            disabled={products.length === 0}
            onClick={() => setDrawer({ resource: "product", price: null })}
          >
            {t("inventories.prices.add")}
          </button>
        </div>
        {productIds.length === 0 ? (
          <p className="px-2 py-8 text-center text-[13px] text-mut">{t("inventories.prices.empty")}</p>
        ) : (
          <ul className="mt-3 flex flex-col gap-2">
            {productIds.map((id) => {
              const list = latest(byProduct.get(id) ?? [])
              const current = list[0]
              const history = list.slice(1)
              return (
                <li key={id} className="rounded-xl border border-line p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="font-semibold">{productName(id)}</p>
                      <p className="text-[12px] text-mut" dir="ltr">
                        {unitPrice(current.dzd_per_unit, lang)} {t("common.dzd")}/
                        {t(`journal.units.${current.unit}` as const, { defaultValue: current.unit })}{" "}
                        · {t("inventories.prices.from")} {formatMediumDate(current.valid_from, lang)}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <button
                        type="button"
                        className="text-[12px] font-semibold text-pri"
                        onClick={() => setDrawer({ resource: "product", price: current })}
                      >
                        {t("journal.edit")}
                      </button>
                      <button
                        type="button"
                        className="text-[12px] font-semibold text-red"
                        onClick={() => setDeleteTarget(current)}
                      >
                        {t("journal.delete")}
                      </button>
                    </div>
                  </div>
                  {history.length > 0 ? (
                    <div className="mt-2">
                      <button
                        type="button"
                        className="text-[12px] font-semibold text-mut"
                        onClick={() => toggle(id)}
                      >
                        {t("inventories.prices.history")} ({history.length})
                      </button>
                      {expanded.has(id) ? (
                        <ul className="mt-2 flex flex-col gap-1">
                          {history.map((price) => (
                            <li
                              key={price.id}
                              className="flex items-center justify-between text-[12px] text-mut"
                              dir="ltr"
                            >
                              <span>
                                {unitPrice(price.dzd_per_unit, lang)} {t("common.dzd")} ·{" "}
                                {formatMediumDate(price.valid_from, lang)}
                              </span>
                              <button
                                type="button"
                                className="font-semibold text-red"
                                onClick={() => setDeleteTarget(price)}
                              >
                                {t("journal.delete")}
                              </button>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <section className={cardClass}>
        <h2 className="text-[14px] font-bold">{t("inventories.prices.resources")}</h2>
        <ul className="mt-3 flex flex-col gap-2">
          {RESOURCES.map((resource) => {
            const current = resourcePrice(resource)
            const usedLater = resource === "energy_kwh"
            return (
              <li
                key={resource}
                className="flex items-center justify-between gap-2 rounded-xl border border-line p-3"
              >
                <div>
                  <p className="flex items-center gap-2 font-semibold">
                    {t(`inventories.resources.${resource}`)}
                    {usedLater ? (
                      <span className="rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
                        {t("inventories.prices.usedLater")}
                      </span>
                    ) : null}
                  </p>
                  <p className="text-[12px] text-mut" dir="ltr">
                    {current === null
                      ? "—"
                      : `${unitPrice(current.dzd_per_unit, lang)} ${t("common.dzd")}/${current.unit}`}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {current === null ? (
                    <button
                      type="button"
                      className={outlineBtn}
                      onClick={() => setDrawer({ resource, price: null })}
                    >
                      {t("inventories.prices.add")}
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="text-[12px] font-semibold text-pri"
                        onClick={() => setDrawer({ resource, price: current })}
                      >
                        {t("journal.edit")}
                      </button>
                      <button
                        type="button"
                        className="text-[12px] font-semibold text-red"
                        onClick={() => setDeleteTarget(current)}
                      >
                        {t("journal.delete")}
                      </button>
                    </>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      </section>

      {drawer !== null ? (
        <PriceDrawer
          open={true}
          onOpenChange={(open) => {
            if (!open) setDrawer(null)
          }}
          farmId={farmId}
          resource={drawer.resource}
          products={products}
          price={drawer.price}
          onSaved={refresh}
        />
      ) : null}
      {deleteTarget !== null ? (
        <ReasonDialog
          title={t("inventories.prices.deleteTitle")}
          text={t("inventories.prices.deleteText")}
          label={t("inventories.prices.reason")}
          cancelLabel={t("journal.cancel")}
          confirmLabel={t("journal.delete")}
          pending={deleting}
          error={deleteError === null ? null : t(deleteError)}
          onCancel={() => {
            setDeleteTarget(null)
            setDeleteError(null)
          }}
          onConfirm={(reason) => void confirmDelete(reason)}
        />
      ) : null}
    </div>
  )
}
