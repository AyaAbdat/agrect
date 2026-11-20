import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Drawer } from "../../components/Drawer"
import { ApiError, apiSend } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { localizedName, type LocalizedName } from "../blocks/types"
import { asNumber, formatMediumDate, isDecimal, wireDecimal } from "../weather/format"
import { FieldError, FieldLabel, fieldClass, outlineBtn, primaryBtn } from "../weather/ui"
import { stageErrorKey } from "./errors"
import type { ObservationItem, SeasonOut } from "./types"

type StageChoice = {
  id: string
  name: LocalizedName
}

const FORM_ID = "confirm-stage"

function shareWire(value: string): string | null | "bad" {
  const trimmed = value.trim()
  if (trimmed === "") return null
  const wire = wireDecimal(trimmed)
  if (wire === null || !isDecimal(trimmed)) return "bad"
  const number = Number(wire)
  if (!Number.isFinite(number) || number < 0 || number > 100) return "bad"
  return wire
}

export function ConfirmStageDrawer({
  open,
  onOpenChange,
  blockId,
  year,
  today,
  seasonId,
  stages,
  observations,
  stageId,
  dateSeen,
  share,
  lang,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  blockId: string
  year: number
  today: string
  seasonId: string | null
  stages: StageChoice[]
  observations: ObservationItem[]
  stageId: string
  dateSeen: string
  share: string
  lang: string
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [chosen, setChosen] = useState(stageId)
  const [date, setDate] = useState(dateSeen)
  const [plants, setPlants] = useState(share)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const items = Object.fromEntries(stages.map((stage) => [stage.id, localizedName(stage.name, lang)]))
  const names = new Map(stages.map((stage) => [stage.id, localizedName(stage.name, lang)]))

  useEffect(() => {
    if (!open) return
    setChosen(stageId)
    setDate(dateSeen)
    setPlants(share)
    setErrors({})
    setFormError(null)
    setPendingDelete(null)
  }, [open, stageId, dateSeen, share])

  function applyError(error: ApiError) {
    const next: Record<string, string> = {}
    for (const [key, code] of Object.entries(error.fields)) {
      const target =
        key === "observed_on" || key === "start_date"
          ? "date"
          : key === "share_pct"
            ? "share"
            : key === "stage_def_id" || key === "start_stage_def_id"
              ? "stage"
              : null
      if (target !== null) next[target] = stageErrorKey(code)
    }
    setErrors(next)
    if (Object.keys(next).length === 0) setFormError("stages.errors.save")
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (chosen === "") next.stage = "stages.errors.stage"
    if (date === "") next.date = "stages.errors.date"
    else if (date > today) next.date = "stages.errors.future"
    const shareValue = shareWire(plants)
    if (shareValue === "bad") next.share = "stages.errors.share"
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0 || shareValue === "bad") return
    setSaving(true)
    try {
      let season = seasonId
      if (season === null) {
        const created = await apiSend<SeasonOut>(
          "PUT",
          `/v1/blocks/${blockId}/seasons/${year}`,
          { start_stage_def_id: chosen },
        )
        season = created.id
      }
      await apiSend("POST", `/v1/block-seasons/${season}/observations`, {
        stage_def_id: chosen,
        observed_on: date,
        share_pct: shareValue,
      })
    } catch (error) {
      if (error instanceof ApiError) applyError(error)
      else setFormError("stages.errors.save")
      setSaving(false)
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["block-stages", blockId] })
    await queryClient.invalidateQueries({ queryKey: ["stage-summary"] })
    setSaving(false)
    onOpenChange(false)
  }

  async function remove(id: string) {
    if (seasonId === null) return
    setDeleting(true)
    setFormError(null)
    try {
      await apiSend("DELETE", `/v1/block-seasons/${seasonId}/observations/${id}`)
    } catch (error) {
      if (error instanceof ApiError) setFormError(stageErrorKey(error.code))
      else setFormError("stages.errors.delete")
      setDeleting(false)
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["block-stages", blockId] })
    await queryClient.invalidateQueries({ queryKey: ["stage-summary"] })
    setPendingDelete(null)
    setDeleting(false)
  }

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={t("stages.season")}
      title={t("stages.confirm")}
      footer={
        <div className="flex items-center justify-end gap-2">
          <button type="button" className={outlineBtn} onClick={() => onOpenChange(false)}>
            {t("stages.cancel")}
          </button>
          <button type="submit" form={FORM_ID} className={primaryBtn} disabled={saving}>
            {saving ? t("stages.saving") : t("stages.save")}
          </button>
        </div>
      }
    >
      <form id={FORM_ID} className="flex flex-col gap-4" onSubmit={(event) => void onSubmit(event)}>
        <p className="text-mut">{t("stages.drawerWhat")}</p>
        <label className="block">
          <FieldLabel label={t("stages.stage")} tag="required" />
          <Select
            value={chosen === "" ? null : chosen}
            items={items}
            onValueChange={(value) => {
              if (value !== null) setChosen(value)
            }}
          >
            <SelectTrigger className="h-10 w-full rounded-[10px] border-[#C7D2C9] text-[13px]">
              <SelectValue placeholder={t("stages.chooseStage")} />
            </SelectTrigger>
            <SelectContent>
              {stages.map((stage) => (
                <SelectItem key={stage.id} value={stage.id}>
                  {localizedName(stage.name, lang)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldError message={errors.stage} />
        </label>
        <label className="block">
          <FieldLabel label={t("stages.dateSeen")} tag="required" />
          <input
            type="date"
            dir="ltr"
            lang="en"
            max={today}
            className={fieldClass}
            value={date}
            aria-invalid={errors.date !== undefined}
            onChange={(change) => setDate(change.target.value)}
          />
          <FieldError message={errors.date} />
        </label>
        <label className="block">
          <FieldLabel label={t("stages.share")} tag="optional" />
          <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
            <input
              className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
              inputMode="decimal"
              dir="ltr"
              lang="en"
              value={plants}
              aria-invalid={errors.share !== undefined}
              onChange={(change) => setPlants(change.target.value)}
            />
            <span className="text-[12px] text-mut">%</span>
          </span>
          <FieldError message={errors.share} />
        </label>
        <div>
          <span className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold">{t("stages.photo")}</span>
            <span className="rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
              {t("settings.phase2")}
            </span>
          </span>
          <button type="button" className={outlineBtn} disabled>
            {t("stages.addPhoto")}
          </button>
        </div>
        <div className="rounded-xl bg-mint px-4 py-3 text-[13px] text-pri">
          <p className="font-semibold">{t("stages.laterNote")}</p>
          <p>{t("stages.laterNoteText")}</p>
        </div>
        {observations.length > 0 ? (
          <section>
            <h2 className="text-[15px] font-bold">{t("stages.observations")}</h2>
            <ul className="mt-2">
              {observations.map((row) => (
                <li
                  key={row.id}
                  className="flex items-center justify-between gap-3 border-b border-line py-2 last:border-b-0"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">
                      {names.get(row.stage_def_id) ?? t("common.missing")}
                    </span>
                    <span className="block text-[12px] text-mut">
                      {formatMediumDate(row.observed_on, lang)}
                      {row.share_pct !== null
                        ? ` · ${formatNumber(asNumber(row.share_pct), 0, lang)} %`
                        : ""}
                    </span>
                  </span>
                  {pendingDelete === row.id ? (
                    <span className="flex shrink-0 items-center gap-2">
                      <button
                        type="button"
                        className="text-[12px] font-semibold text-red"
                        disabled={deleting}
                        onClick={() => void remove(row.id)}
                      >
                        {t("stages.deleteConfirm")}
                      </button>
                      <button
                        type="button"
                        className="text-[12px] font-semibold text-mut"
                        onClick={() => setPendingDelete(null)}
                      >
                        {t("stages.cancel")}
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="shrink-0 text-[12px] font-semibold text-red"
                      onClick={() => setPendingDelete(row.id)}
                    >
                      {t("stages.delete")}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {formError !== null ? <FieldError message={formError} /> : null}
      </form>
    </Drawer>
  )
}
