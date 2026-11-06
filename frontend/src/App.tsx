import { Navigate, Route, Routes } from "react-router"
import { AppShell } from "./app/AppShell"
import { blockNav, farmNav, plansNav } from "./app/navigation"
import { PlaceholderPage } from "./components/PlaceholderPage"
import { LoginPage } from "./pages/LoginPage"
import { SettingsSectionPage } from "./pages/SettingsSectionPage"
import { SettingsWorkspacePage } from "./pages/SettingsWorkspacePage"

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppShell />}>
        {farmNav.map((item) => (
          <Route
            key={item.to}
            path={item.to}
            element={
              <PlaceholderPage titleKey={item.labelKey} phase={item.phase} />
            }
          />
        ))}
        {plansNav.map((item) => (
          <Route
            key={item.to}
            path={item.to}
            element={
              <PlaceholderPage titleKey={item.labelKey} phase={item.phase} />
            }
          />
        ))}
        {blockNav.map((item) => (
          <Route
            key={item.segment}
            path={`/blocks/:blockId/${item.segment}`}
            element={
              <PlaceholderPage titleKey={item.labelKey} phase={item.phase} />
            }
          />
        ))}
        <Route path="/ask" element={<PlaceholderPage titleKey="top.ask" phase="phase2" />} />
        <Route path="/alerts" element={<PlaceholderPage titleKey="top.alerts" phase="phase2" />} />
        <Route path="/settings/workspace" element={<SettingsWorkspacePage />} />
        <Route path="/settings/:section" element={<SettingsSectionPage />} />
      </Route>
      <Route path="/" element={<Navigate to="/today" replace />} />
      <Route path="*" element={<Navigate to="/today" replace />} />
    </Routes>
  )
}
