import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useSearchParams } from "react-router"
import { PageHeader } from "../weather/ui"
import { AttendanceTab } from "./AttendanceTab"
import { LabourNormsTab } from "./LabourNormsTab"
import { MachinesTab } from "./MachinesTab"
import { WorkersTab } from "./WorkersTab"

type Tab = "workers" | "attendance" | "norms" | "machines"

function initialTab(param: string | null): Tab {
  if (param === "attendance" || param === "norms" || param === "machines") return param
  return "workers"
}

export function TeamPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [tab, setTab] = useState<Tab>(() => initialTab(searchParams.get("tab")))
  const tabs: { id: Tab; label: string }[] = [
    { id: "workers", label: t("team.tabs.workers") },
    { id: "attendance", label: t("team.tabs.attendance") },
    { id: "norms", label: t("team.tabs.norms") },
    { id: "machines", label: t("team.tabs.machines") },
  ]
  function selectTab(next: Tab) {
    setTab(next)
    if (next === "workers") {
      setSearchParams({}, { replace: true })
    } else {
      setSearchParams({ tab: next }, { replace: true })
    }
  }
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("nav.plansAndTeam")}
        title={t("team.title")}
        sub={t("team.sub")}
      />
      <div className="flex gap-1 border-b border-line">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => selectTab(item.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-[13px] font-semibold ${
              tab === item.id ? "border-pri text-pri" : "border-transparent text-mut"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
      {tab === "workers" ? (
        <WorkersTab />
      ) : tab === "attendance" ? (
        <AttendanceTab />
      ) : tab === "norms" ? (
        <LabourNormsTab />
      ) : (
        <MachinesTab />
      )}
    </div>
  )
}
