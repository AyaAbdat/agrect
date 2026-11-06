import { useParams } from "react-router"
import { settingsTitleKey } from "../app/navigation"
import { PlaceholderPage } from "../components/PlaceholderPage"

export function SettingsSectionPage() {
  const { section } = useParams()
  return (
    <PlaceholderPage titleKey={settingsTitleKey(section)} phase="phase2" />
  )
}
