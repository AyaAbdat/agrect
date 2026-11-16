import { useTranslation } from "react-i18next"
import { sectionLabelClass } from "../../../lib/navStyles"
import { WIZARD_STEPS } from "./steps"

export function WizardStepper({
  step,
  onStep,
}: {
  step: number
  onStep: (step: number) => void
}) {
  const { t } = useTranslation()
  return (
    <nav className="w-[220px] shrink-0 rounded-2xl border border-line bg-white p-3">
      <p className={sectionLabelClass}>{t("blocks.wizardLabel")}</p>
      <ol className="flex flex-col gap-1">
        {WIZARD_STEPS.map((item) => {
          const state = item.id === step ? "current" : item.id < step ? "done" : "future"
          const row =
            state === "current"
              ? "bg-mint font-semibold text-pri"
              : state === "done"
                ? "font-medium text-text"
                : "font-medium text-[#9CA3AF]"
          const badge =
            state === "future"
              ? "border border-[#D1D5DB] text-[#9CA3AF]"
              : "bg-pri text-white"
          const body = (
            <>
              <span
                className={`flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${badge}`}
              >
                {item.id}
              </span>
              <span>{t(item.labelKey)}</span>
            </>
          )
          if (state === "done") {
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className={`flex h-8 w-full items-center gap-2 rounded-lg px-2 text-start ${row}`}
                  onClick={() => onStep(item.id)}
                >
                  {body}
                </button>
              </li>
            )
          }
          return (
            <li key={item.id}>
              <div className={`flex h-8 items-center gap-2 rounded-lg px-2 ${row}`}>{body}</div>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
