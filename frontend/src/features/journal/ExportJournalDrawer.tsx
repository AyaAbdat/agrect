import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"
import { Drawer } from "../../components/Drawer"
import { activeLang } from "../blocks/types"
import { outlineBtn, primaryBtn } from "../weather/ui"
import type { JournalKind } from "./types"

const KIND_OPTIONS: { kind: JournalKind; labelKey: string }[] = [
  { kind: "operation", labelKey: "journal.print.includeOperations" },
  { kind: "irrigation", labelKey: "journal.print.includeIrrigations" },
  { kind: "harvest", labelKey: "journal.print.includeHarvests" },
  { kind: "stage", labelKey: "journal.print.includeStages" },
]

function seasonStart(today: string): string {
  const year = today.slice(0, 4)
  if (/^\d{4}$/.test(year)) return `${year}-01-01`
  return `${new Date().getFullYear()}-01-01`
}

function langLabelKey(lang: string): string {
  if (lang === "ar") return "journal.print.langAr"
  if (lang === "en") return "journal.print.langEn"
  return "journal.print.langFr"
}

function ExportJournalForm({
  blockId,
  today,
  onClose,
}: {
  blockId: string
  today: string
  onClose: () => void
}) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [from, setFrom] = useState(() => seasonStart(today))
  const [to, setTo] = useState(() => today)
  const [selected, setSelected] = useState<Record<JournalKind, boolean>>({
    operation: true,
    irrigation: true,
    harvest: true,
    stage: true,
  })

  const chosenKinds = KIND_OPTIONS.filter((opt) => selected[opt.kind]).map((opt) => opt.kind)
  const invalidPeriod = from !== "" && to !== "" && from > to
  const canOpen = chosenKinds.length > 0 && !invalidPeriod

  function toggleKind(kind: JournalKind) {
    setSelected((prev) => ({ ...prev, [kind]: !prev[kind] }))
  }

  function openPrintView() {
    if (!canOpen) return
    const params = new URLSearchParams()
    if (from.trim() !== "") params.set("from", from.trim())
    if (to.trim() !== "") params.set("to", to.trim())
    params.set("types", chosenKinds.join(","))
    onClose()
    void navigate(`/blocks/${blockId}/journal/print?${params.toString()}`)
  }

  return (
    <div className="flex flex-col gap-5">
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1.5 text-[13px] font-semibold">
          {t("journal.print.period")}
        </legend>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[12px] text-mut">{t("journal.print.from")}</span>
            <input
              type="date"
              dir="ltr"
              lang="en"
              className="h-9 rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px]"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] text-mut">{t("journal.print.to")}</span>
            <input
              type="date"
              dir="ltr"
              lang="en"
              className="h-9 rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px]"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </label>
        </div>
        {invalidPeriod ? (
          <p className="text-[12px] text-red">{t("journal.print.invalidPeriod")}</p>
        ) : null}
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1.5 text-[13px] font-semibold">
          {t("journal.print.include")}
        </legend>
        <div className="flex flex-col gap-2">
          {KIND_OPTIONS.map((opt) => (
            <label
              key={opt.kind}
              className="flex cursor-pointer items-center gap-2.5 text-[13px]"
            >
              <input
                type="checkbox"
                className="size-4 accent-pri"
                checked={selected[opt.kind]}
                onChange={() => toggleKind(opt.kind)}
              />
              <span>{t(opt.labelKey)}</span>
            </label>
          ))}
        </div>
        {chosenKinds.length === 0 ? (
          <p className="text-[12px] text-red">{t("journal.print.selectOneType")}</p>
        ) : null}
      </fieldset>

      <div className="flex items-center justify-between rounded-[10px] border border-line bg-bg px-3 py-2.5 text-[13px]">
        <span className="text-mut">{t("journal.print.language")}</span>
        <span className="font-semibold">{t(langLabelKey(lang))}</span>
      </div>

      <div className="flex items-center justify-end gap-2 pt-2">
        <button type="button" className={outlineBtn} onClick={onClose}>
          {t("journal.cancel")}
        </button>
        <button
          type="button"
          className={primaryBtn}
          disabled={!canOpen}
          onClick={openPrintView}
        >
          {t("journal.print.openPrintView")}
        </button>
      </div>
    </div>
  )
}

export function ExportJournalDrawer({
  open,
  onOpenChange,
  blockId,
  blockName,
  today,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  blockId: string
  blockName: string
  today: string
}) {
  const { t } = useTranslation()
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={blockName}
      title={t("journal.print.drawerTitle")}
    >
      {open ? (
        <ExportJournalForm
          blockId={blockId}
          today={today}
          onClose={() => onOpenChange(false)}
        />
      ) : null}
    </Drawer>
  )
}
