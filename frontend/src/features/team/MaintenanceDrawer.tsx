import { useEffect, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { apiSend } from "../../lib/api"
import { isDecimal, wireDecimal } from "../weather/format"
import { FieldError, FieldLabel, fieldClass, outlineBtn, primaryBtn } from "../weather/ui"
import { teamErrorState } from "./errors"
import type { MaintenanceItem } from "./types"

const FORM_ID = "machine-maintenance-form"

export function MaintenanceDrawer({
  open,
  onOpenChange,
  machineId,
  machineName,
  item,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  machineId: string
  machineName: string
  item: MaintenanceItem | null
  onSaved: () => void
}) {
  const { t } = useTranslation()
  const [task, setTask] = useState("")
  const [intervalH, setIntervalH] = useState("")
  const [intervalDays, setIntervalDays] = useState("")
  const [lastDoneDate, setLastDoneDate] = useState("")
  const [lastDoneH, setLastDoneH] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    if (item === null) {
      setTask("")
      setIntervalH("")
      setIntervalDays("")
      setLastDoneDate("")
      setLastDoneH("")
    } else {
      setTask(item.task)
      setIntervalH(item.interval_h ?? "")
      setIntervalDays(item.interval_days === null ? "" : String(item.interval_days))
      setLastDoneDate(item.last_done_date ?? "")
      setLastDoneH(item.last_done_h ?? "")
    }
    setErrors({})
    setFormError(null)
  }, [open, item])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (task.trim() === "") next.task = "team.machines.errors.taskRequired"

    const hasH = intervalH.trim() !== ""
    const hasDays = intervalDays.trim() !== ""
    const hWire = wireDecimal(intervalH)
    if (!hasH && !hasDays) {
      next.interval_h = "team.machines.errors.intervalRequired"
    } else {
      if (hasH && (hWire === null || !isDecimal(intervalH) || Number(hWire) <= 0)) {
        next.interval_h = "team.machines.errors.intervalInvalid"
      }
      if (hasDays && (!/^\d+$/.test(intervalDays.trim()) || Number(intervalDays.trim()) <= 0)) {
        next.interval_days = "team.machines.errors.intervalInvalid"
      }
    }

    const lastHWire = wireDecimal(lastDoneH)
    if (lastDoneH.trim() !== "") {
      if (lastHWire === null || !isDecimal(lastDoneH) || Number(lastHWire) < 0) {
        next.last_done_h = "team.machines.errors.hoursInvalid"
      }
    }

    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0) return

    setSaving(true)
    const payload = {
      task: task.trim(),
      interval_h: hasH ? hWire : null,
      interval_days: hasDays ? Number(intervalDays.trim()) : null,
      last_done_date: lastDoneDate.trim() === "" ? null : lastDoneDate.trim(),
      last_done_h: lastDoneH.trim() === "" ? null : lastHWire,
    }
    try {
      if (item === null) {
        await apiSend<MaintenanceItem>("POST", `/v1/machines/${machineId}/maintenance`, payload)
      } else {
        await apiSend<MaintenanceItem>("PATCH", `/v1/maintenance/${item.id}`, payload, {
          "If-Match": String(item.version),
        })
      }
    } catch (error) {
      setSaving(false)
      const parsed = teamErrorState(error)
      setErrors(parsed.fields)
      setFormError(parsed.form)
      return
    }
    setSaving(false)
    onSaved()
    onOpenChange(false)
  }

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={machineName}
      title={t(
        item === null
          ? "team.machines.maintenance.addTitle"
          : "team.machines.maintenance.editTitle",
      )}
      footer={
        <div className="flex justify-end gap-2">
          <button type="button" className={outlineBtn} onClick={() => onOpenChange(false)}>
            {t("journal.cancel")}
          </button>
          <button type="submit" form={FORM_ID} className={primaryBtn} disabled={saving}>
            {t("journal.save")}
          </button>
        </div>
      }
    >
      <form
        id={FORM_ID}
        className="flex flex-col gap-4"
        onSubmit={(event) => void onSubmit(event)}
      >
        <label className="block">
          <FieldLabel label={t("team.machines.maintenance.task")} tag="required" />
          <input
            className={fieldClass}
            value={task}
            aria-invalid={errors.task !== undefined}
            onChange={(change) => setTask(change.target.value)}
          />
          <FieldError message={errors.task} />
        </label>

        <div className="rounded-xl border border-line p-3">
          <p className="mb-2 text-[12px] text-mut">{t("team.machines.maintenance.intervalHint")}</p>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <FieldLabel label={t("team.machines.maintenance.intervalHours")} />
              <input
                className={fieldClass}
                inputMode="decimal"
                dir="ltr"
                lang="en"
                value={intervalH}
                aria-invalid={errors.interval_h !== undefined}
                onChange={(change) => setIntervalH(change.target.value)}
              />
              <FieldError message={errors.interval_h} />
            </label>
            <label className="block">
              <FieldLabel label={t("team.machines.maintenance.intervalDays")} />
              <input
                className={fieldClass}
                inputMode="numeric"
                dir="ltr"
                lang="en"
                value={intervalDays}
                aria-invalid={errors.interval_days !== undefined}
                onChange={(change) => setIntervalDays(change.target.value)}
              />
              <FieldError message={errors.interval_days} />
            </label>
          </div>
        </div>

        <label className="block">
          <FieldLabel label={t("team.machines.maintenance.lastDoneDate")} tag="optional" />
          <input
            type="date"
            dir="ltr"
            lang="en"
            className={fieldClass}
            value={lastDoneDate}
            onChange={(change) => setLastDoneDate(change.target.value)}
          />
        </label>

        <label className="block">
          <FieldLabel label={t("team.machines.maintenance.lastDoneHours")} tag="optional" />
          <input
            className={fieldClass}
            inputMode="decimal"
            dir="ltr"
            lang="en"
            value={lastDoneH}
            aria-invalid={errors.last_done_h !== undefined}
            onChange={(change) => setLastDoneH(change.target.value)}
          />
          <FieldError message={errors.last_done_h} />
        </label>

        {formError !== null ? <FieldError message={formError} /> : null}
      </form>
    </Drawer>
  )
}
