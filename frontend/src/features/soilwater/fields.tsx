import type { UseFormRegisterReturn } from "react-hook-form"
import { FieldError, FieldLabel, fieldClass } from "../weather/ui"

export function Help({ children }: { children: string }) {
  return <p className="mt-1 text-[12px] text-mut">{children}</p>
}

export function NumberField({
  label,
  unit,
  tag,
  error,
  help,
  registration,
  placeholder,
}: {
  label: string
  unit?: string
  tag?: "required" | "optional"
  error?: string
  help?: string
  registration: UseFormRegisterReturn
  placeholder?: string
}) {
  return (
    <label className="block min-w-0">
      <FieldLabel label={label} tag={tag} />
      <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
        <input
          className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
          inputMode="decimal"
          dir="ltr"
          lang="en"
          placeholder={placeholder}
          autoComplete="off"
          aria-invalid={error !== undefined}
          {...registration}
        />
        {unit !== undefined ? <span className="text-[12px] text-mut">{unit}</span> : null}
      </span>
      {help !== undefined ? <Help>{help}</Help> : null}
      <FieldError message={error} />
    </label>
  )
}

export function DateField({
  label,
  error,
  help,
  registration,
}: {
  label: string
  error?: string
  help?: string
  registration: UseFormRegisterReturn
}) {
  return (
    <label className="block min-w-0">
      <FieldLabel label={label} tag="required" />
      <input
        type="date"
        dir="ltr"
        lang="en"
        className={fieldClass}
        aria-invalid={error !== undefined}
        {...registration}
      />
      {help !== undefined ? <Help>{help}</Help> : null}
      <FieldError message={error} />
    </label>
  )
}
