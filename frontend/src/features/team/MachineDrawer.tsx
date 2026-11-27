import { useEffect, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { apiSend } from "../../lib/api"
import { isDecimal, wireDecimal } from "../weather/format"
import {
  ChoiceChip,
  FieldError,
  FieldLabel,
  fieldClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { teamErrorState } from "./errors"
import {
  MACHINE_STATUSES,
  MACHINE_TYPES,
  type Machine,
  type MachineStatus,
  type MachineType,
} from "./types"

const FORM_ID = "team-machine-form"

export function MachineDrawer({
  open,
  onOpenChange,
  farmId,
  machine,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  farmId: string
  machine: Machine | null
  onSaved: () => void
}) {
  const { t } = useTranslation()
  const [name, setName] = useState("")
  const [type, setType] = useState<MachineType>("tractor")
  const [status, setStatus] = useState<MachineStatus>("ok")
  const [engineHours, setEngineHours] = useState("")
  const [readingDate, setReadingDate] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    if (machine === null) {
      setName("")
      setType("tractor")
      setStatus("ok")
      setEngineHours("")
      setReadingDate("")
    } else {
      setName(machine.name)
      setType(machine.type)
      setStatus(machine.status)
      setEngineHours(machine.engine_hours_reading ?? "")
      setReadingDate(machine.reading_date ?? "")
    }
    setErrors({})
    setFormError(null)
  }, [open, machine])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (name.trim() === "") next.name = "team.machines.errors.nameRequired"
    const hoursWire = wireDecimal(engineHours)
    if (engineHours.trim() !== "") {
      if (hoursWire === null || !isDecimal(engineHours) || Number(hoursWire) < 0) {
        next.engine_hours_reading = "team.machines.errors.hoursInvalid"
      }
    }
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0) return

    setSaving(true)
    const payload = {
      name: name.trim(),
      type,
      status,
      engine_hours_reading: engineHours.trim() === "" ? null : hoursWire,
      reading_date: readingDate.trim() === "" ? null : readingDate.trim(),
    }
    try {
      if (machine === null) {
        await apiSend<Machine>("POST", `/v1/farms/${farmId}/machines`, payload)
      } else {
        await apiSend<Machine>("PATCH", `/v1/machines/${machine.id}`, payload, {
          "If-Match": String(machine.version),
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
      crumb={t("nav.team")}
      title={t(machine === null ? "team.machines.addTitle" : "team.machines.editTitle")}
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
          <FieldLabel label={t("team.machines.name")} tag="required" />
          <input
            className={fieldClass}
            value={name}
            aria-invalid={errors.name !== undefined}
            onChange={(change) => setName(change.target.value)}
          />
          <FieldError message={errors.name} />
        </label>

        <div>
          <FieldLabel label={t("team.machines.type")} tag="required" />
          <div className="flex flex-wrap gap-2">
            {MACHINE_TYPES.map((item) => (
              <ChoiceChip key={item} selected={type === item} onClick={() => setType(item)}>
                {t(`team.machines.types.${item}`)}
              </ChoiceChip>
            ))}
          </div>
        </div>

        <div>
          <FieldLabel label={t("team.machines.status")} />
          <div className="flex flex-wrap gap-2">
            {MACHINE_STATUSES.map((item) => (
              <ChoiceChip key={item} selected={status === item} onClick={() => setStatus(item)}>
                {t(`team.machines.statuses.${item}`)}
              </ChoiceChip>
            ))}
          </div>
        </div>

        <label className="block">
          <FieldLabel label={t("team.machines.engineHoursReading")} tag="optional" />
          <input
            className={fieldClass}
            inputMode="decimal"
            dir="ltr"
            lang="en"
            value={engineHours}
            aria-invalid={errors.engine_hours_reading !== undefined}
            onChange={(change) => setEngineHours(change.target.value)}
          />
          <FieldError message={errors.engine_hours_reading} />
        </label>

        <label className="block">
          <FieldLabel label={t("team.machines.readingDate")} tag="optional" />
          <input
            type="date"
            dir="ltr"
            lang="en"
            className={fieldClass}
            value={readingDate}
            onChange={(change) => setReadingDate(change.target.value)}
          />
        </label>

        {formError !== null ? <FieldError message={formError} /> : null}
      </form>
    </Drawer>
  )
}
