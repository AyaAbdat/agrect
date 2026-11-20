import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { ApiError, apiSend } from "../../lib/api"
import { FieldError, FieldLabel, fieldClass, outlineBtn, primaryBtn } from "../weather/ui"
import { stageErrorKey } from "./errors"
import type { SeasonOut } from "./types"

const FORM_ID = "sowing-date"

export function SowingDrawer({
  open,
  onOpenChange,
  blockId,
  year,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  blockId: string
  year: number
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [date, setDate] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setDate("")
    setError(null)
    setFormError(null)
  }, [open])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (date === "") {
      setError("stages.errors.date")
      return
    }
    setError(null)
    setFormError(null)
    setSaving(true)
    try {
      await apiSend<SeasonOut>("PUT", `/v1/blocks/${blockId}/seasons/${year}`, {
        start_date: date,
      })
    } catch (caught) {
      if (caught instanceof ApiError) {
        const code = caught.fields.start_date
        setError(code === undefined ? null : stageErrorKey(code))
        if (code === undefined) setFormError("stages.errors.save")
      } else {
        setFormError("stages.errors.save")
      }
      setSaving(false)
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["block-stages", blockId] })
    await queryClient.invalidateQueries({ queryKey: ["stage-summary"] })
    setSaving(false)
    onOpenChange(false)
  }

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={t("stages.season")}
      title={t("stages.sowingTitle")}
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
        <label className="block">
          <FieldLabel label={t("stages.sowingDate")} tag="required" />
          <input
            type="date"
            dir="ltr"
            lang="en"
            className={fieldClass}
            value={date}
            aria-invalid={error !== null}
            onChange={(change) => setDate(change.target.value)}
          />
          <FieldError message={error ?? undefined} />
        </label>
        {formError !== null ? <FieldError message={formError} /> : null}
      </form>
    </Drawer>
  )
}
