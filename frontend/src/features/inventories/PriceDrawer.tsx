import { useEffect, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { ApiError, apiSend } from "../../lib/api"
import type { Product } from "../journal/types"
import { FieldError, FieldLabel, fieldClass, outlineBtn, primaryBtn } from "../weather/ui"
import { inventoryErrorState } from "./errors"
import type { Price, PriceResource } from "./types"

const FORM_ID = "inventory-price"

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

export function PriceDrawer({
  open,
  onOpenChange,
  farmId,
  resource,
  products,
  price,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  farmId: string
  resource: PriceResource
  products: Product[]
  price: Price | null
  onSaved: () => void
}) {
  const { t } = useTranslation()
  const isEdit = price !== null
  const [productId, setProductId] = useState("")
  const [validFrom, setValidFrom] = useState(todayIso())
  const [perUnit, setPerUnit] = useState("")
  const [note, setNote] = useState("")
  const [reason, setReason] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    if (price === null) {
      setProductId(resource === "product" ? (products[0]?.id ?? "") : "")
      setValidFrom(todayIso())
      setPerUnit("")
      setNote("")
    } else {
      setProductId(price.product_id ?? "")
      setValidFrom(price.valid_from)
      setPerUnit(price.dzd_per_unit)
      setNote(price.note ?? "")
    }
    setReason("")
    setErrors({})
    setFormError(null)
  }, [open, price, resource, products])

  async function onSubmit(submitEvent: FormEvent) {
    submitEvent.preventDefault()
    const next: Record<string, string> = {}
    if (resource === "product" && !isEdit && productId === "") {
      next.product_id = "inventories.errors.product"
    }
    if (perUnit.trim() === "" || Number.isNaN(Number(perUnit)) || Number(perUnit) <= 0) {
      next.dzd_per_unit = "inventories.errors.price"
    }
    if (isEdit && reason.trim() === "") next.reason = "inventories.errors.reason"
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0) return
    setSaving(true)
    try {
      if (isEdit && price !== null) {
        await apiSend(
          "PATCH",
          `/v1/prices/${price.id}`,
          {
            valid_from: validFrom,
            dzd_per_unit: perUnit.trim(),
            note: note.trim() === "" ? null : note.trim(),
            reason: reason.trim(),
          },
          { "If-Match": String(price.version) },
        )
      } else {
        await apiSend("POST", `/v1/farms/${farmId}/prices`, {
          resource,
          product_id: resource === "product" ? productId : null,
          valid_from: validFrom,
          dzd_per_unit: perUnit.trim(),
          note: note.trim() === "" ? null : note.trim(),
        })
      }
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

  const title = isEdit
    ? t("inventories.priceDrawer.editTitle")
    : t("inventories.priceDrawer.title")

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={t("inventories.tabs.prices")}
      title={title}
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
        {resource === "product" ? (
          <label className="block">
            <FieldLabel label={t("inventories.stock.product")} tag="required" />
            <select
              className={fieldClass}
              value={productId}
              disabled={isEdit}
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
        ) : (
          <p className="text-[13px] font-semibold">{t(`inventories.resources.${resource}`)}</p>
        )}
        <label className="block">
          <FieldLabel label={t("inventories.prices.perUnit")} tag="required" />
          <input
            className={fieldClass}
            inputMode="decimal"
            dir="ltr"
            lang="en"
            value={perUnit}
            aria-invalid={errors.dzd_per_unit !== undefined}
            onChange={(change) => setPerUnit(change.target.value)}
          />
          <FieldError message={errors.dzd_per_unit} />
        </label>
        <label className="block">
          <FieldLabel label={t("inventories.prices.validFrom")} tag="required" />
          <input
            type="date"
            className={fieldClass}
            dir="ltr"
            value={validFrom}
            onChange={(change) => setValidFrom(change.target.value)}
          />
        </label>
        <label className="block">
          <FieldLabel label={t("inventories.prices.note")} />
          <input
            className={fieldClass}
            value={note}
            onChange={(change) => setNote(change.target.value)}
          />
        </label>
        {isEdit ? (
          <label className="block">
            <FieldLabel label={t("inventories.prices.reason")} tag="required" />
            <textarea
              className={fieldClass}
              rows={2}
              value={reason}
              aria-invalid={errors.reason !== undefined}
              onChange={(change) => setReason(change.target.value)}
            />
            <p className="mt-1 text-[12px] text-mut">{t("inventories.prices.reasonHint")}</p>
            <FieldError message={errors.reason} />
          </label>
        ) : null}
        {formError !== null ? <FieldError message={formError} /> : null}
      </form>
    </Drawer>
  )
}
