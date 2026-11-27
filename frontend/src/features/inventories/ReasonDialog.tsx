import { useState } from "react"
import { useTranslation } from "react-i18next"
import { fieldClass, outlineBtn, primaryBtn } from "../weather/ui"

export function ReasonDialog({
  title,
  text,
  label,
  cancelLabel,
  confirmLabel,
  pending,
  error,
  onCancel,
  onConfirm,
}: {
  title: string
  text: string
  label: string
  cancelLabel: string
  confirmLabel: string
  pending: boolean
  error: string | null
  onCancel: () => void
  onConfirm: (reason: string) => void
}) {
  const { t } = useTranslation()
  const [reason, setReason] = useState("")
  const [touched, setTouched] = useState(false)
  const empty = reason.trim() === ""
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4">
      <div role="dialog" aria-modal="true" className="w-full max-w-sm rounded-2xl bg-white p-5">
        <h2 className="text-[16px] font-bold">{title}</h2>
        <p className="mt-2 text-[13px] text-mut">{text}</p>
        <label className="mt-3 block">
          <span className="mb-1 block text-[12px] font-semibold text-mut">{label}</span>
          <textarea
            className={fieldClass}
            rows={2}
            value={reason}
            onChange={(change) => setReason(change.target.value)}
          />
        </label>
        {touched && empty ? (
          <p className="mt-1 text-[12px] text-red">{t("inventories.errors.reason")}</p>
        ) : null}
        {error !== null ? <p className="mt-2 text-[12px] text-red">{error}</p> : null}
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className={outlineBtn} onClick={onCancel} disabled={pending}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`${primaryBtn} disabled:opacity-60`}
            disabled={pending}
            onClick={() => {
              setTouched(true)
              if (empty) return
              onConfirm(reason.trim())
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
