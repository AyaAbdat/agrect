import { useParams } from "react-router"
import { settingsTitleKey } from "../app/navigation"
import { PlaceholderPage } from "../components/PlaceholderPage"
import { InventoriesPage } from "../features/inventories/InventoriesPage"
import { FarmDetailsPage } from "../features/settings/FarmDetailsPage"

export function SettingsSectionPage() {
  const { section } = useParams()
  if (section === "inventories") return <InventoriesPage />
  if (section === "farm-details") return <FarmDetailsPage />
  return <PlaceholderPage titleKey={settingsTitleKey(section)} phase="phase2" />
}
