import { useState } from "react"
import { ChevronDown, Settings } from "lucide-react"
import { useTranslation } from "react-i18next"
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router"
import { blockNav, farmNav, plansNav } from "./navigation"
import { Drawer } from "../components/Drawer"
import { EmptyState } from "../components/PlaceholderPage"
import { LogoMark } from "../components/LogoMark"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { LANGS, isLang } from "../i18n"
import {
  navDisabledClass,
  navItemClass,
  sectionLabelClass,
} from "../lib/navStyles"
import {
  UNIT_RADIATION_W_M2,
  UNIT_RH_PERCENT,
  UNIT_TEMP_C,
  UNIT_WIND_M_S,
} from "../lib/units"

const pillClass =
  "inline-flex h-9 shrink-0 items-center rounded-full px-3.5 text-[12px] font-semibold"

function OutsideStrip() {
  const { t } = useTranslation()
  const parts = [
    { label: t("top.outside"), unit: UNIT_TEMP_C },
    { label: t("top.rh"), unit: UNIT_RH_PERCENT },
    { label: t("top.wind"), unit: UNIT_WIND_M_S },
    { label: t("top.radiation"), unit: UNIT_RADIATION_W_M2 },
  ]
  return (
    <div className={`${pillClass} gap-1 border border-line`}>
      {parts.map((part, index) => (
        <span key={part.label} className="inline-flex items-center gap-1">
          {index > 0 ? <span className="text-mut">·</span> : null}
          <span className="text-mut">{part.label}</span>
          <span>{t("common.missing")}</span>
          <span>{part.unit}</span>
        </span>
      ))}
    </div>
  )
}

export function AppShell() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [captureOpen, setCaptureOpen] = useState(false)
  const settingsActive = pathname.startsWith("/settings")
  const language = isLang(i18n.resolvedLanguage)
    ? i18n.resolvedLanguage
    : isLang(i18n.language)
      ? i18n.language
      : "fr"

  return (
    <div className="grid h-screen min-w-[1100px] grid-cols-[240px_minmax(0,1fr)] grid-rows-[64px_minmax(0,1fr)] bg-bg text-text">
      <aside className="row-span-2 flex h-full flex-col border-e border-line bg-white px-3 pb-3">
        <div className="flex h-16 shrink-0 items-center gap-2.5">
          <LogoMark size={30} />
          <div className="min-w-0 leading-tight">
            <div className="text-[15px] font-bold">{t("app.name")}</div>
            <div className="text-[11px] text-mut">{t("app.workspace")}</div>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <p className={sectionLabelClass}>{t("nav.farm")}</p>
          {farmNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) => navItemClass(isActive)}
            >
              {t(item.labelKey)}
            </NavLink>
          ))}
          <p className={sectionLabelClass}>{t("nav.block")}</p>
          <Select disabled value="none">
            <SelectTrigger className="mb-1 h-[34px] w-full rounded-[10px] border-line bg-[#F9FAFB] text-[12px] text-mut disabled:cursor-not-allowed disabled:opacity-100">
              <SelectValue>{() => t("nav.noBlocks")}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">{t("nav.noBlocks")}</SelectItem>
            </SelectContent>
          </Select>
          {blockNav.map((item) => (
            <div key={item.segment} className={navDisabledClass}>
              {t(item.labelKey)}
            </div>
          ))}
          <p className={sectionLabelClass}>{t("nav.plansAndTeam")}</p>
          {plansNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) => navItemClass(isActive)}
            >
              {t(item.labelKey)}
            </NavLink>
          ))}
        </div>
        <div className="shrink-0 border-t border-line pt-2">
          <NavLink
            to="/settings/workspace"
            className={() => navItemClass(settingsActive)}
          >
            <Settings className="me-2 size-4" aria-hidden="true" />
            {t("nav.settings")}
          </NavLink>
        </div>
      </aside>
      <header className="flex min-w-0 items-center gap-3 border-b border-line bg-white ps-8 pe-6">
        <div className={`${pillClass} gap-1 bg-mint text-pri`}>
          {t("top.allBlocks")}
          <ChevronDown className="size-4" aria-hidden="true" />
        </div>
        <OutsideStrip />
        <div className="flex-1" />
        <button
          type="button"
          className={`${pillClass} border border-[#C7D2C9] text-pri`}
          onClick={() => setCaptureOpen(true)}
        >
          {t("top.capture")}
        </button>
        <Link to="/ask" className={`${pillClass} bg-pri font-bold text-white`}>
          {t("top.ask")}
        </Link>
        <Link
          to="/alerts"
          className={`${pillClass} gap-2 border border-line`}
        >
          {t("top.alerts")}
          <Badge variant="secondary" className="bg-[#E5E7EB] text-mut">
            {t("common.missing")}
          </Badge>
        </Link>
        <DropdownMenu>
          <DropdownMenuTrigger className="flex size-9 shrink-0 items-center justify-center rounded-full border border-line bg-[#F1F3F2] text-[12px] font-semibold">
            {t("common.missing")}
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-44">
            <DropdownMenuRadioGroup
              value={language}
              onValueChange={(value: string) => {
                if (isLang(value)) void i18n.changeLanguage(value)
              }}
            >
              <DropdownMenuLabel>{t("menu.language")}</DropdownMenuLabel>
              {LANGS.map((code) => (
                <DropdownMenuRadioItem key={code} value={code}>
                  {t(`menu.${code}`)}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                void navigate("/login")
              }}
            >
              {t("menu.logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>
      <main className="min-h-0 overflow-y-auto px-8 pt-7 pb-12">
        <div className="flex w-full max-w-[1136px] flex-col gap-5">
          <Outlet />
        </div>
      </main>
      <Drawer
        open={captureOpen}
        onOpenChange={setCaptureOpen}
        title={t("drawer.captureTitle")}
      >
        <EmptyState phase="phase2" fill={false} />
      </Drawer>
    </div>
  )
}
