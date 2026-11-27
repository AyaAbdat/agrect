import { useTranslation } from "react-i18next"
import { Link, useSearchParams } from "react-router"
import { PageHeader, outlineBtn } from "../weather/ui"
import { PricesTab } from "./PricesTab"
import { ProductsTab } from "./ProductsTab"
import { StockTab } from "./StockTab"

type Tab = "products" | "stock" | "prices"

function parseTab(value: string | null): Tab {
  if (value === "stock" || value === "prices") return value
  return "products"
}

export function InventoriesPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = parseTab(searchParams.get("tab"))
  function setTab(next: Tab) {
    setSearchParams(next === "products" ? {} : { tab: next }, { replace: true })
  }
  const tabs: { id: Tab; label: string }[] = [
    { id: "products", label: t("inventories.tabs.products") },
    { id: "stock", label: t("inventories.tabs.stock") },
    { id: "prices", label: t("inventories.tabs.prices") },
  ]
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("settings.title")}
        title={t("settings.inventories")}
        sub={t("inventories.sub")}
        actions={
          <Link to="/costs" className={outlineBtn}>
            {t("inventories.openCosts")}
          </Link>
        }
      />
      <div className="flex gap-1 border-b border-line">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-[13px] font-semibold ${
              tab === item.id ? "border-pri text-pri" : "border-transparent text-mut"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
      {tab === "products" ? <ProductsTab /> : tab === "stock" ? <StockTab /> : <PricesTab />}
    </div>
  )
}
