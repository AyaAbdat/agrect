import { useTranslation } from "react-i18next"
import type { Phase } from "../app/navigation"
import { crumbClass } from "../lib/navStyles"
import { EmptyState } from "./EmptyState"

export function PlaceholderPage({
  titleKey,
  phase,
}: {
  titleKey: string
  phase: Phase
}) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-5">
      <header>
        <p className={crumbClass}>{t("app.workspace")}</p>
        <h1 className="text-[24px] font-bold leading-tight">{t(titleKey)}</h1>
      </header>
      <div className="rounded-2xl border border-line bg-white p-5">
        <EmptyState phase={phase} />
      </div>
    </div>
  )
}
