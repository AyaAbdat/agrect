import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Drawer } from "../../components/Drawer"
import { apiSend } from "../../lib/api"
import { ChoiceChip, FieldError, FieldLabel, fieldClass, outlineBtn, primaryBtn } from "../weather/ui"
import { journalErrorState } from "./errors"
import type { Product, ProductKind, ProductUnit } from "./types"

const FORM_ID = "journal-product"

const KINDS: ProductKind[] = ["crop_protection", "fertiliser", "seed", "packaging", "other"]
const UNITS: ProductUnit[] = ["kg", "g", "l", "ml", "unit"]

export function ProductDrawer({
  open,
  onOpenChange,
  farmId,
  product,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  farmId: string
  product: Product | null
  onSaved: (product: Product) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [name, setName] = useState("")
  const [kind, setKind] = useState<ProductKind>("crop_protection")
  const [unit, setUnit] = useState<ProductUnit>("l")
  const [activeIngredient, setActiveIngredient] = useState("")
  const [phi, setPhi] = useState("")
  const [reentry, setReentry] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    if (product === null) {
      setName("")
      setKind("crop_protection")
      setUnit("l")
      setActiveIngredient("")
      setPhi("")
      setReentry("")
    } else {
      setName(product.name)
      setKind(product.kind)
      setUnit(product.unit)
      setActiveIngredient(product.active_ingredient ?? "")
      setPhi(product.preharvest_interval_days === null ? "" : String(product.preharvest_interval_days))
      setReentry(product.reentry_h === null ? "" : String(product.reentry_h))
    }
    setErrors({})
    setFormError(null)
  }, [open, product])

  async function onSubmit(submitEvent: FormEvent) {
    submitEvent.preventDefault()
    const next: Record<string, string> = {}
    if (name.trim() === "") next.name = "journal.errors.productNameRequired"
    const phiWire = phi.trim() === "" ? null : Number(phi)
    if (phi.trim() !== "" && (!/^\d+$/.test(phi.trim()) || (phiWire ?? 0) < 0)) {
      next.preharvest_interval_days = "journal.errors.phi"
    }
    const reWire = reentry.trim() === "" ? null : Number(reentry)
    if (reentry.trim() !== "" && (!/^\d+$/.test(reentry.trim()) || (reWire ?? 0) < 0)) {
      next.reentry_h = "journal.errors.reentry"
    }
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0) return
    setSaving(true)
    const payload = {
      name: name.trim(),
      kind,
      unit,
      active_ingredient: activeIngredient.trim() === "" ? null : activeIngredient.trim(),
      preharvest_interval_days: phiWire,
      reentry_h: reWire,
    }
    try {
      let saved: Product
      if (product === null) {
        saved = await apiSend<Product>("POST", `/v1/farms/${farmId}/products`, payload)
      } else {
        saved = await apiSend<Product>("PATCH", `/v1/products/${product.id}`, payload, {
          "If-Match": String(product.version),
        })
      }
      await queryClient.invalidateQueries({ queryKey: ["products", farmId] })
      setSaving(false)
      onSaved(saved)
      onOpenChange(false)
    } catch (error) {
      setSaving(false)
      const parsed = journalErrorState(error)
      setErrors(parsed.fields)
      setFormError(parsed.form)
    }
  }

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={t("journal.productsCrumb")}
      title={t(product === null ? "journal.productNewTitle" : "journal.productEditTitle")}
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
          <FieldLabel label={t("journal.productName")} tag="required" />
          <input
            className={fieldClass}
            value={name}
            aria-invalid={errors.name !== undefined}
            onChange={(change) => setName(change.target.value)}
          />
          <FieldError message={errors.name} />
        </label>
        <div>
          <FieldLabel label={t("journal.productKind")} tag="required" />
          <div className="flex flex-wrap gap-2">
            {KINDS.map((item) => (
              <ChoiceChip key={item} selected={kind === item} onClick={() => setKind(item)}>
                {t(`journal.productKinds.${item}`)}
              </ChoiceChip>
            ))}
          </div>
        </div>
        <div>
          <FieldLabel label={t("journal.productUnit")} tag="required" />
          <div className="flex flex-wrap gap-2">
            {UNITS.map((item) => (
              <ChoiceChip key={item} selected={unit === item} onClick={() => setUnit(item)}>
                {t(`journal.units.${item}`)}
              </ChoiceChip>
            ))}
          </div>
        </div>
        <label className="block">
          <FieldLabel label={t("journal.activeIngredient")} />
          <input
            className={fieldClass}
            value={activeIngredient}
            onChange={(change) => setActiveIngredient(change.target.value)}
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <FieldLabel label={t("journal.phiDays")} />
            <input
              className={fieldClass}
              inputMode="numeric"
              dir="ltr"
              lang="en"
              value={phi}
              aria-invalid={errors.preharvest_interval_days !== undefined}
              onChange={(change) => setPhi(change.target.value)}
            />
            <FieldError message={errors.preharvest_interval_days} />
          </label>
          <label className="block">
            <FieldLabel label={t("journal.reentryHours")} />
            <input
              className={fieldClass}
              inputMode="numeric"
              dir="ltr"
              lang="en"
              value={reentry}
              aria-invalid={errors.reentry_h !== undefined}
              onChange={(change) => setReentry(change.target.value)}
            />
            <FieldError message={errors.reentry_h} />
          </label>
        </div>
        {formError !== null ? <FieldError message={formError} /> : null}
      </form>
    </Drawer>
  )
}