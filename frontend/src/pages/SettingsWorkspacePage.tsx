import { useTranslation } from "react-i18next"
import { NavLink } from "react-router"
import { settingsNav, settingsPath } from "../app/navigation"
import { Badge } from "@/components/ui/badge"
import { crumbClass, navItemClass, sectionLabelClass } from "../lib/navStyles"

export function SettingsWorkspacePage() {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-5">
      <header>
        <p className={crumbClass}>{t("settings.crumb")}</p>
        <h1 className="text-[24px] font-bold leading-tight">
          {t("settings.title")}
        </h1>
        <p className="mt-1 text-mut">{t("settings.sub")}</p>
      </header>
      <div className="flex items-start gap-5">
        <nav className="w-[260px] shrink-0 rounded-2xl border border-line bg-white p-3">
          {settingsNav.map((group) => (
            <div key={group.labelKey}>
              <p className={sectionLabelClass}>{t(group.labelKey)}</p>
              {group.items.map((item) => (
                <NavLink
                  key={item.id}
                  to={settingsPath(item.id)}
                  end
                  className={({ isActive }) => navItemClass(isActive)}
                >
                  {t(item.labelKey)}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <section className="flex min-w-0 flex-1 flex-col gap-4 rounded-2xl border border-line bg-white p-5">
          <div>
            <h2 className="text-[16px] font-bold">{t("settings.workspace")}</h2>
            <p className="mt-1 max-w-[640px] text-mut">
              {t("settings.workspaceLead")}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-2 rounded-[14px] border border-pri bg-mint p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 font-semibold">
                  <span className="flex size-4 items-center justify-center rounded-full border-2 border-pri">
                    <span className="size-2 rounded-full bg-pri" />
                  </span>
                  {t("app.workspace")}
                </span>
                <Badge className="bg-pri text-white">{t("settings.current")}</Badge>
              </div>
              <p className="text-mut">{t("settings.openFieldText")}</p>
            </div>
            <div
              className="flex flex-col gap-2 rounded-[14px] border border-line bg-[#F9FAFB] p-4"
              aria-disabled="true"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 font-semibold text-mut">
                  <span className="size-4 rounded-full border-2 border-[#9CA3AF]" />
                  {t("settings.greenhouse")}
                </span>
                <Badge
                  variant="secondary"
                  className="bg-[#E5E7EB] text-mut"
                >
                  {t("settings.phase2")}
                </Badge>
              </div>
              <p className="text-mut">{t("settings.greenhouseText")}</p>
            </div>
          </div>
          <p className="text-[12px] text-mut">{t("settings.footnote")}</p>
        </section>
      </div>
    </div>
  )
}
