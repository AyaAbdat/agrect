import { useEffect, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { ApiError, apiSend } from "../../lib/api"
import type { Product } from "../journal/types"
import { FieldError, FieldLabel, fieldClass, outlineBtn, primaryBtn } from "../weather/ui"
import { inventoryErrorState } from "./errors"

const FORM_ID = "inventory-adjust"

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

export function AdjustDrawer({
  open,
  onOpenChange,
  farmId,
  products,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  farmId: string
  products: Product[]
  onSaved: () => void
}) {
  const { t } = useTranslation()
  const [productId, setProductId] = useState("")
  const [date, setDate] = useState(todayIso())
  const [quantity, setQuantity] = useState("")
  const [note, setNote] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setProductId(products[0]?.id ?? "")
    setDate(todayIso())
    setQuantity("")
    setNote("")
    setErrors({})
    setFormError(null)
  }, [open, products])

  async function onSubmit(submitEvent: FormEvent) {
    submitEvent.preventDefault()
    const next: Record<string, string> = {}
    if (productId === "") next.product_id = "inventories.errors.product"
    if (quantity.trim() === "" || Number.isNaN(Number(quantity)) || Number(quantity) === 0) {
      next.qty = "inventories.errors.adjustQuantity"
    }
    if (note.trim() === "") next.note = "inventories.errors.reason"
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0) return
    setSaving(true)
    try {
      await apiSend("POST", `/v1/farms/${farmId}/stock-moves`, {
        product_id: productId,
        date,
        qty: quantity.trim(),
        kind: "adjustment",
        note: note.trim(),
      })
      setSaving(false)
      onSaved()
      onOpenChange(false)
    } catch (error) {
      setSaving(false)
      if (error instanceof ApiError) {
        const parsed = inventoryErrorState(error)
        setErrors(parsed.fields)
        setFormError(parsed.form)
      } else {
        setFormError("inventories.errors.save")
      }
    }
  }

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={t("settings.inventories")}
      title={t("inventories.adjust.title")}
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
        onSubmit={(submitEvent) => void onSubmit(submitEvent)}
      >
        <label className="block">
          <FieldLabel label={t("inventories.stock.product")} tag="required" />
          <select
            className={fieldClass}
            value={productId}
            onChange={(change) => setProductId(change.target.value)}
          >
            <option value="">{t("inventories.selectProduct")}</option>
            {products.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
          <FieldError message={errors.product_id} />
        </label>
        <label className="block">
          <FieldLabel label={t("inventories.date")} tag="required" />
          <input
            type="date"
            className={fieldClass}
            dir="ltr"
            value={date}
            onChange={(change) => setDate(change.target.value)}
          />
        </label>
        <label className="block">
          <FieldLabel label={t("inventories.adjust.quantity")} tag="required" />
          <input
            className={fieldClass}
            inputMode="decimal"
            dir="ltr"
            lang="en"
            value={quantity}
            aria-invalid={errors.qty !== undefined}
            onChange={(change) => setQuantity(change.target.value)}
          />
          <FieldError message={errors.qty} />
        </label>
        <label className="block">
          <FieldLabel label={t("inventories.adjust.note")} tag="required" />
          <textarea
            className={fieldClass}
            rows={2}
            value={note}
            aria-invalid={errors.note !== undefined}
            onChange={(change) => setNote(change.target.value)}
          />
          <FieldError message={errors.note} />
        </label>
        {formError !== null ? <FieldError message={formError} /> : null}
      </form>
    </Drawer>
  )
}
