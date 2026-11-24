import { useParams } from "react-router"
import { settingsTitleKey } from "../app/navigation"
import { PlaceholderPage } from "../components/PlaceholderPage"
import { ProductsPage } from "../features/journal/ProductsPage"

export function SettingsSectionPage() {
  const { section } = useParams()
  if (section === "inventories") return <ProductsPage />
  return <PlaceholderPage titleKey={settingsTitleKey(section)} phase="phase2" />
}
