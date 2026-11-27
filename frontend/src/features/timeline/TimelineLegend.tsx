import { ShoppingBasket } from "lucide-react"
import { useTranslation } from "react-i18next"
import { OP_COLORS } from "./model"

export function TimelineLegend() {
  const { t } = useTranslation()

  const opItems = [
    { key: "nutrition", color: OP_COLORS.nutrition, label: t("timeline.legend.opNutrition") },
    { key: "protection", color: OP_COLORS.protection, label: t("timeline.legend.opProtection") },
    { key: "foliar", color: OP_COLORS.foliar, label: t("timeline.legend.opFoliar") },
    { key: "canopy", color: OP_COLORS.canopy, label: t("timeline.legend.opCanopy") },
    { key: "other", color: OP_COLORS.other, label: t("timeline.legend.opOther") },
  ]

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line px-4 py-3 text-[11px] text-mut">
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-5 rounded-sm bg-[#D8F3DC] ring-1 ring-inset ring-[#2D6A4F]/30" />
        {t("timeline.legend.preHarvest")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-5 rounded-sm bg-sec" />
        {t("timeline.legend.harvested")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block size-2.5 rounded-full border-[1.5px] border-white bg-pri ring-1 ring-pri/40" />
        {t("timeline.legend.stage")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-flex size-4 items-center justify-center rounded-full bg-white text-pri ring-1 ring-pri/40">
          <ShoppingBasket className="size-2.5" aria-hidden="true" />
        </span>
        {t("timeline.legend.harvest")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-flex items-center gap-0.5">
          <span className="inline-block h-1.5 w-2 rounded-xs bg-[#0284C7]/35" />
          <span className="inline-block h-1.5 w-2 rounded-xs bg-[#0284C7]/65" />
          <span className="inline-block h-1.5 w-2 rounded-xs bg-[#0284C7]" />
        </span>
        {t("timeline.legend.irrigation")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-3.5 w-0.5 bg-red" />
        {t("timeline.today")}
      </span>
      <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1 border-s border-line ps-3">
        <span className="font-semibold text-text">{t("timeline.legend.operations")}:</span>
        {opItems.map((item) => (
          <span key={item.key} className="inline-flex items-center gap-1">
            <span
              className="inline-block h-3 w-1 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            {item.label}
          </span>
        ))}
      </span>
    </div>
  )
}
