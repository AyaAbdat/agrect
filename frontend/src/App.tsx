import { lazy, Suspense, type ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Navigate, Route, Routes } from "react-router"
import { AppShell } from "./app/AppShell"
import { RequireAuth } from "./app/auth"
import { blockNav, farmNav, plansNav } from "./app/navigation"
import { LoginPage } from "./pages/LoginPage"

const TodayPage = lazy(() =>
  import("./features/today/TodayPage").then((m) => ({ default: m.TodayPage })),
)
const BlocksPage = lazy(() =>
  import("./features/blocks/BlocksPage").then((m) => ({ default: m.BlocksPage })),
)
const BlockWizardPage = lazy(() =>
  import("./features/blocks/wizard/BlockWizardPage").then((m) => ({
    default: m.BlockWizardPage,
  })),
)
const BlockSetupPage = lazy(() =>
  import("./features/blocks/BlockSetupPage").then((m) => ({
    default: m.BlockSetupPage,
  })),
)
const WeatherPage = lazy(() =>
  import("./features/weather/WeatherPage").then((m) => ({ default: m.WeatherPage })),
)
const DegreeDaysPage = lazy(() =>
  import("./features/weather/DegreeDaysPage").then((m) => ({
    default: m.DegreeDaysPage,
  })),
)
const DegreeDaySettingsPage = lazy(() =>
  import("./features/weather/DegreeDaySettingsPage").then((m) => ({
    default: m.DegreeDaySettingsPage,
  })),
)
const SoilWaterPage = lazy(() =>
  import("./features/soilwater/SoilWaterPage").then((m) => ({
    default: m.SoilWaterPage,
  })),
)
const SoilSetupPage = lazy(() =>
  import("./features/soilwater/SoilSetupPage").then((m) => ({
    default: m.SoilSetupPage,
  })),
)
const IrrigationSettingsPage = lazy(() =>
  import("./features/soilwater/IrrigationSettingsPage").then((m) => ({
    default: m.IrrigationSettingsPage,
  })),
)
const IrrigationLogPage = lazy(() =>
  import("./features/soilwater/IrrigationLogPage").then((m) => ({
    default: m.IrrigationLogPage,
  })),
)
const WaterBalancePage = lazy(() =>
  import("./features/soilwater/WaterBalancePage").then((m) => ({
    default: m.WaterBalancePage,
  })),
)
const SoilCheckPage = lazy(() =>
  import("./features/soilwater/SoilCheckPage").then((m) => ({
    default: m.SoilCheckPage,
  })),
)
const StagesPage = lazy(() =>
  import("./features/stages/StagesPage").then((m) => ({ default: m.StagesPage })),
)
const StageDetailPage = lazy(() =>
  import("./features/stages/StageDetailPage").then((m) => ({
    default: m.StageDetailPage,
  })),
)
const ModelSettingsPage = lazy(() =>
  import("./features/stages/ModelSettingsPage").then((m) => ({
    default: m.ModelSettingsPage,
  })),
)
const AllStagesPage = lazy(() =>
  import("./features/stages/AllStagesPage").then((m) => ({
    default: m.AllStagesPage,
  })),
)
const SettingsWorkspacePage = lazy(() =>
  import("./pages/SettingsWorkspacePage").then((m) => ({
    default: m.SettingsWorkspacePage,
  })),
)
const SettingsSectionPage = lazy(() =>
  import("./pages/SettingsSectionPage").then((m) => ({
    default: m.SettingsSectionPage,
  })),
)
const PlaceholderPage = lazy(() =>
  import("./components/PlaceholderPage").then((m) => ({
    default: m.PlaceholderPage,
  })),
)

function RouteLoading() {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-40 items-center justify-center text-mut">
      {t("common.loading")}
    </div>
  )
}

function suspended(node: ReactNode) {
  return <Suspense fallback={<RouteLoading />}>{node}</Suspense>
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/today" element={suspended(<TodayPage />)} />
          {farmNav
            .filter((item) => item.to !== "/blocks" && item.to !== "/today")
            .map((item) => (
              <Route
                key={item.to}
                path={item.to}
                element={suspended(
                  <PlaceholderPage titleKey={item.labelKey} phase={item.phase} />,
                )}
              />
            ))}
          <Route path="/stages/settings" element={suspended(<ModelSettingsPage />)} />
          <Route path="/stages" element={suspended(<AllStagesPage />)} />
          <Route path="/blocks" element={suspended(<BlocksPage />)} />
          <Route path="/blocks/new" element={suspended(<BlockWizardPage />)} />
          <Route path="/blocks/:blockId/edit" element={suspended(<BlockWizardPage />)} />
          <Route path="/blocks/:blockId/setup" element={suspended(<BlockSetupPage />)} />
          <Route
            path="/blocks/:blockId/weather/degree-day-settings"
            element={suspended(<DegreeDaySettingsPage />)}
          />
          <Route
            path="/blocks/:blockId/weather/degree-days"
            element={suspended(<DegreeDaysPage />)}
          />
          <Route path="/blocks/:blockId/weather" element={suspended(<WeatherPage />)} />
          <Route path="/blocks/:blockId/soil-water" element={suspended(<SoilWaterPage />)} />
          <Route
            path="/blocks/:blockId/soil-water/soil"
            element={suspended(<SoilSetupPage />)}
          />
          <Route
            path="/blocks/:blockId/soil-water/settings"
            element={suspended(<IrrigationSettingsPage />)}
          />
          <Route
            path="/blocks/:blockId/soil-water/log"
            element={suspended(<IrrigationLogPage />)}
          />
          <Route
            path="/blocks/:blockId/soil-water/balance"
            element={suspended(<WaterBalancePage />)}
          />
          <Route
            path="/blocks/:blockId/soil-water/soil-check"
            element={suspended(<SoilCheckPage />)}
          />
          <Route
            path="/blocks/:blockId/stages/:stageDefId"
            element={suspended(<StageDetailPage />)}
          />
          <Route path="/blocks/:blockId/stages" element={suspended(<StagesPage />)} />
          {plansNav.map((item) => (
            <Route
              key={item.to}
              path={item.to}
              element={suspended(
                <PlaceholderPage titleKey={item.labelKey} phase={item.phase} />,
              )}
            />
          ))}
          {blockNav
            .filter(
              (item) =>
                item.segment !== "setup" &&
                item.segment !== "weather" &&
                item.segment !== "soil-water" &&
                item.segment !== "stages",
            )
            .map((item) => (
              <Route
                key={item.segment}
                path={`/blocks/:blockId/${item.segment}`}
                element={suspended(
                  <PlaceholderPage titleKey={item.labelKey} phase={item.phase} />,
                )}
              />
            ))}
          <Route
            path="/ask"
            element={suspended(<PlaceholderPage titleKey="top.ask" phase="phase2" />)}
          />
          <Route
            path="/alerts"
            element={suspended(<PlaceholderPage titleKey="top.alerts" phase="phase2" />)}
          />
          <Route path="/settings/workspace" element={suspended(<SettingsWorkspacePage />)} />
          <Route path="/settings/:section" element={suspended(<SettingsSectionPage />)} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/today" replace />} />
      <Route path="*" element={<Navigate to="/today" replace />} />
    </Routes>
  )
}
