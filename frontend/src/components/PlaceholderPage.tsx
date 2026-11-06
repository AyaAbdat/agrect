import { Sprout } from "lucide-react"
import { useTranslation } from "react-i18next"
import type { Phase } from "../app/navigation"
import { crumbClass } from "../lib/navStyles"

export function EmptyState({
  phase,
  fill = true,
}: {
  phase: Phase
  fill?: boolean
}) {
  const { t } = useTranslation()
  const title =
    phase === "phase2"
      ? t("placeholder.phase2Title")
      : t("placeholder.mvpTitle")
  const text =
    phase === "phase2" ? t("placeholder.phase2Text") : t("placeholder.mvpText")
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 text-center ${fill ? "min-h-[420px]" : "py-8"}`}
    >
      <div className="flex size-12 items-center justify-center rounded-[14px] bg-mint text-pri">
        <Sprout className="size-5" aria-hidden="true" />
      </div>
      <p className="text-[16px] font-bold">{title}</p>
      <p className="max-w-[400px] text-mut">{text}</p>
    </div>
  )
}

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
