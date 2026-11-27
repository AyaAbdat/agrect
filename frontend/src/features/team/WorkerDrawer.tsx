import { useEffect, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { apiSend } from "../../lib/api"
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
  WORKER_KINDS,
  WORKER_ROLES,
  type Worker,
  type WorkerKind,
  type WorkerRole,
} from "./types"

const FORM_ID = "team-worker-form"

export function WorkerDrawer({
  open,
  onOpenChange,
  farmId,
  worker,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  farmId: string
  worker: Worker | null
  onSaved: () => void
}) {
  const { t } = useTranslation()
  const [name, setName] = useState("")
  const [role, setRole] = useState<WorkerRole>("operator")
  const [kind, setKind] = useState<WorkerKind>("permanent")
  const [phone, setPhone] = useState("")
  const [active, setActive] = useState(true)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    if (worker === null) {
      setName("")
      setRole("operator")
      setKind("permanent")
      setPhone("")
      setActive(true)
    } else {
      setName(worker.name)
      setRole(worker.role)
      setKind(worker.kind)
      setPhone(worker.phone ?? "")
      setActive(worker.active)
    }
    setErrors({})
    setFormError(null)
  }, [open, worker])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (name.trim() === "") next.name = "team.errors.nameRequired"
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0) return

    setSaving(true)
    const payload = {
      name: name.trim(),
      role,
      kind,
      phone: phone.trim() === "" ? null : phone.trim(),
      active,
    }
    try {
      if (worker === null) {
        await apiSend<Worker>("POST", `/v1/farms/${farmId}/workers`, payload)
      } else {
        await apiSend<Worker>("PATCH", `/v1/workers/${worker.id}`, payload, {
          "If-Match": String(worker.version),
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
      title={t(worker === null ? "team.workers.addTitle" : "team.workers.editTitle")}
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
          <FieldLabel label={t("team.workers.name")} tag="required" />
          <input
            className={fieldClass}
            value={name}
            aria-invalid={errors.name !== undefined}
            onChange={(change) => setName(change.target.value)}
          />
          <FieldError message={errors.name} />
        </label>

        <label className="block">
          <span className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold">{t("team.workers.role")}</span>
            <span className="rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
              {t("team.workers.draftList")}
            </span>
          </span>
          <select
            className={fieldClass}
            value={role}
            onChange={(change) => setRole(change.target.value as WorkerRole)}
          >
            {WORKER_ROLES.map((item) => (
              <option key={item} value={item}>
                {t(`team.roles.${item}`)}
              </option>
            ))}
          </select>
        </label>

        <div>
          <FieldLabel label={t("team.workers.kind")} />
          <div className="flex flex-wrap gap-2">
            {WORKER_KINDS.map((item) => (
              <ChoiceChip
                key={item}
                selected={kind === item}
                onClick={() => setKind(item)}
              >
                {t(`team.kinds.${item}`)}
              </ChoiceChip>
            ))}
          </div>
        </div>

        <label className="block">
          <FieldLabel label={t("team.workers.phone")} tag="optional" />
          <input
            className={fieldClass}
            type="tel"
            dir="ltr"
            value={phone}
            onChange={(change) => setPhone(change.target.value)}
          />
        </label>

        <div className="flex items-center justify-between gap-3 rounded-xl border border-line px-3 py-2.5">
          <div>
            <p className="text-[13px] font-semibold">{t("team.workers.active")}</p>
            <p className="text-[12px] text-mut">{t("team.workers.activeHint")}</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={active}
            onClick={() => setActive((prev) => !prev)}
            className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
              active ? "bg-pri" : "bg-[#D1D5DB]"
            }`}
          >
            <span
              className={`inline-block size-4 rounded-full bg-white transition-transform ${
                active ? "translate-x-6 rtl:-translate-x-6" : "translate-x-1 rtl:-translate-x-1"
              }`}
            />
          </button>
        </div>

        {formError !== null ? <FieldError message={formError} /> : null}
      </form>
    </Drawer>
  )
}
