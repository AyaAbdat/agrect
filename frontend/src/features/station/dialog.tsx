import type { ReactNode } from "react"
import { outlineBtn, primaryBtn } from "../weather/ui"

export function ConfirmDialog({
  title,
  text,
  error,
  cancelLabel,
  confirmLabel,
  pending,
  onCancel,
  onConfirm,
}: {
  title: string
  text: string
  error: string | null
  cancelLabel: string
  confirmLabel: string
  pending: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="station-confirm-title" className="w-full max-w-sm rounded-2xl bg-white p-5">
        <h2 id="station-confirm-title" className="text-[16px] font-bold">
          {title}
        </h2>
        <p className="mt-2 text-[13px] text-mut">{text}</p>
        {error !== null ? <p className="mt-2 text-[12px] text-red">{error}</p> : null}
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className={outlineBtn} onClick={onCancel} disabled={pending}>
            {cancelLabel}
          </button>
          <button type="button" className={`${primaryBtn} disabled:opacity-60`} onClick={onConfirm} disabled={pending}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

export function Help({ children }: { children: ReactNode }) {
  return <p className="mt-1 text-[12px] text-mut">{children}</p>
}
