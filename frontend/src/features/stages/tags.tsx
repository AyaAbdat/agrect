import { useTranslation } from "react-i18next"
import type { StageLabel, StageSource } from "./types"

const STATUS: Record<StageLabel, { key: string; className: string }> = {
  observed: { key: "stages.observed", className: "bg-mint text-pri" },
  predicted: { key: "stages.predicted", className: "bg-[#DBEAFE] text-[#1D4ED8]" },
  not_enough_data: { key: "stages.notEnough", className: "bg-[#E5E7EB] text-mut" },
  beyond_data: {
    key: "stages.beyond",
    className: "border border-[#C7D2C9] bg-white text-mut",
  },
}

export function StatusTag({ label }: { label: StageLabel }) {
  const { t } = useTranslation()
  const status = STATUS[label]
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${status.className}`}>
      {t(status.key)}
    </span>
  )
}

export function SourcePill({
  source,
  citation,
}: {
  source: StageSource
  citation?: string | null
}) {
  const { t } = useTranslation()
  const entered = source === "entered"
  const label = t(entered ? "stages.entered" : "stages.literature")
  const className = `inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${
    entered ? "bg-mint text-pri" : "bg-[#E5E7EB] text-mut"
  }`
  if (entered || citation === null || citation === undefined || citation === "") {
    return <span className={className}>{label}</span>
  }
  return (
    <span className="group relative inline-flex">
      <span className={className} tabIndex={0}>
        {label}
      </span>
      <span
        role="tooltip"
        className="absolute start-0 top-full z-20 mt-1 hidden w-64 rounded-lg border border-line bg-white p-2 text-[12px] font-normal leading-snug text-text shadow group-hover:block group-focus-within:block"
      >
        {citation}
      </span>
    </span>
  )
}
