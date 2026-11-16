import { Navigate, Route, Routes } from "react-router"
import { AppShell } from "./app/AppShell"
import { RequireAuth } from "./app/auth"
import { blockNav, farmNav, plansNav } from "./app/navigation"
import { PlaceholderPage } from "./components/PlaceholderPage"
import { BlocksPage } from "./features/blocks/BlocksPage"
import { BlockSetupPage } from "./features/blocks/BlockSetupPage"
import { BlockWizardPage } from "./features/blocks/wizard/BlockWizardPage"
import { IrrigationLogPage } from "./features/soilwater/IrrigationLogPage"
import { IrrigationSettingsPage } from "./features/soilwater/IrrigationSettingsPage"
import { SoilCheckPage } from "./features/soilwater/SoilCheckPage"
import { SoilSetupPage } from "./features/soilwater/SoilSetupPage"
import { SoilWaterPage } from "./features/soilwater/SoilWaterPage"
import { WaterBalancePage } from "./features/soilwater/WaterBalancePage"
import { DegreeDaySettingsPage } from "./features/weather/DegreeDaySettingsPage"
import { DegreeDaysPage } from "./features/weather/DegreeDaysPage"
import { TodayPage } from "./features/today/TodayPage"
import { WeatherPage } from "./features/weather/WeatherPage"
import { LoginPage } from "./pages/LoginPage"
import { SettingsSectionPage } from "./pages/SettingsSectionPage"
import { SettingsWorkspacePage } from "./pages/SettingsWorkspacePage"

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/today" element={<TodayPage />} />
          {farmNav
            .filter((item) => item.to !== "/blocks" && item.to !== "/today")
            .map((item) => (
              <Route
                key={item.to}
                path={item.to}
                element={
                  <PlaceholderPage titleKey={item.labelKey} phase={item.phase} />
                }
              />
            ))}
          <Route path="/blocks" element={<BlocksPage />} />
          <Route path="/blocks/new" element={<BlockWizardPage />} />
          <Route path="/blocks/:blockId/edit" element={<BlockWizardPage />} />
          <Route path="/blocks/:blockId/setup" element={<BlockSetupPage />} />
          <Route path="/blocks/:blockId/weather/degree-day-settings" element={<DegreeDaySettingsPage />} />
          <Route path="/blocks/:blockId/weather/degree-days" element={<DegreeDaysPage />} />
          <Route path="/blocks/:blockId/weather" element={<WeatherPage />} />
          <Route path="/blocks/:blockId/soil-water" element={<SoilWaterPage />} />
          <Route path="/blocks/:blockId/soil-water/soil" element={<SoilSetupPage />} />
          <Route path="/blocks/:blockId/soil-water/settings" element={<IrrigationSettingsPage />} />
          <Route path="/blocks/:blockId/soil-water/log" element={<IrrigationLogPage />} />
          <Route path="/blocks/:blockId/soil-water/balance" element={<WaterBalancePage />} />
          <Route path="/blocks/:blockId/soil-water/soil-check" element={<SoilCheckPage />} />
          {plansNav.map((item) => (
            <Route
              key={item.to}
              path={item.to}
              element={
                <PlaceholderPage titleKey={item.labelKey} phase={item.phase} />
              }
            />
          ))}
          {blockNav
            .filter(
              (item) =>
                item.segment !== "setup" &&
                item.segment !== "weather" &&
                item.segment !== "soil-water",
            )
            .map((item) => (
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
      </Route>
      <Route path="/" element={<Navigate to="/today" replace />} />
      <Route path="*" element={<Navigate to="/today" replace />} />
    </Routes>
  )
}
