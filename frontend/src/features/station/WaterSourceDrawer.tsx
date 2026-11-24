import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Drawer } from "../../components/Drawer"
import { apiSend } from "../../lib/api"
import { activeLang } from "../blocks/types"
import { decimalInput } from "../weather/format"
import { FieldError, FieldLabel, fieldClass, outlineBtn, primaryBtn } from "../weather/ui"
import { flowText } from "./display"
import { Help } from "./dialog"
import { optionalWire, stationErrorState } from "./errors"
import type { WaterSource, WaterSourceKind } from "./types"

const FORM_ID = "water-source-form"
const KINDS: WaterSourceKind[] = ["borehole", "basin", "network"]

function kindKey(kind: WaterSourceKind): string {
  if (kind === "basin") return "station.kinds.basin"
  if (kind === "network") return "station.kinds.network"
  return "station.kinds.borehole"
}

export function WaterSourceDrawer({
  open,
  onOpenChange,
  farmId,
  sources,
  intent,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  farmId: string
  sources: WaterSource[]
  intent: "list" | "add"
  onCreated?: (id: string) => void
}) {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<"list" | "form">("list")
  const [editing, setEditing] = useState<WaterSource | null>(null)
  const [name, setName] = useState("")
  const [kind, setKind] = useState<WaterSourceKind>("borehole")
  const [ec, setEc] = useState("")
  const [volume, setVolume] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<WaterSource | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  function blank() {
    setEditing(null)
    setName("")
    setKind("borehole")
    setEc("")
    setVolume("")
    setErrors({})
    setFormError(null)
  }

  useEffect(() => {
    if (!open) return
    setPendingDelete(null)
    setDeleteError(null)
    if (intent === "add") {
      blank()
      setMode("form")
      return
    }
    setMode("list")
    blank()
  }, [open, intent])

  function startEdit(source: WaterSource) {
    setEditing(source)
    setName(source.name)
    setKind(source.kind)
    setEc(decimalInput(source.ec_ds_m))
    setVolume(decimalInput(source.basin_volume_m3))
    setErrors({})
    setFormError(null)
    setMode("form")
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (name.trim() === "") next.name = "station.errors.nameRequired"
    const ecParsed = optionalWire(ec)
    const volumeParsed = optionalWire(volume)
    if (!ecParsed.ok) next.ec_ds_m = "station.errors.number"
    if (!volumeParsed.ok) next.basin_volume_m3 = "station.errors.number"
    setErrors(next)
    setFormError(null)
    if (Object.keys(next).length > 0 || !ecParsed.ok || !volumeParsed.ok) return
    const body = {
      name: name.trim(),
      kind,
      ec_ds_m: ecParsed.wire,
      basin_volume_m3: volumeParsed.wire,
    }
    setSaving(true)
    try {
      const saved =
        editing === null
          ? await apiSend<WaterSource>("POST", `/v1/farms/${farmId}/water-sources`, body)
          : await apiSend<WaterSource>("PATCH", `/v1/water-sources/${editing.id}`, body)
      await queryClient.invalidateQueries({ queryKey: ["station", farmId] })
      setSaving(false)
      if (intent === "add" && editing === null) {
        onCreated?.(saved.id)
        onOpenChange(false)
        return
      }
      setMode("list")
      blank()
    } catch (error) {
      const parsed = stationErrorState(error)
      setErrors(parsed.fields)
      setFormError(parsed.form)
      setSaving(false)
    }
  }

  async function confirmDelete() {
    if (pendingDelete === null) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiSend("DELETE", `/v1/water-sources/${pendingDelete.id}`)
    } catch (error) {
      const parsed = stationErrorState(error)
      setDeleting(false)
      setDeleteError(parsed.form ?? "station.errors.delete")
      return
    }
    await queryClient.invalidateQueries({ queryKey: ["station", farmId] })
    setDeleting(false)
    setPendingDelete(null)
  }

  const title =
    mode === "list"
      ? t("station.sourcesTitle")
      : t(editing === null ? "station.drawerSourceAdd" : "station.drawerSourceEdit")

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      crumb={t("nav.station")}
      title={title}
      footer={
        mode === "form" ? (
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className={outlineBtn}
              onClick={() => {
                if (intent === "add" && editing === null) onOpenChange(false)
                else {
                  setMode("list")
                  blank()
                }
              }}
            >
              {t("station.cancel")}
            </button>
            <button type="submit" form={FORM_ID} className={`${primaryBtn} disabled:opacity-60`} disabled={saving}>
              {t("station.save")}
            </button>
          </div>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-4">
        {mode === "list" ? (
          <button
            type="button"
            className={outlineBtn}
            onClick={() => {
              blank()
              setMode("form")
            }}
          >
            {t("station.addSource")}
          </button>
        ) : (
          <form id={FORM_ID} className="flex flex-col gap-4" onSubmit={(event) => void onSubmit(event)}>
            {formError !== null ? <p className="text-[12px] text-red">{t(formError)}</p> : null}
            <label className="block">
              <FieldLabel label={t("station.name")} tag="required" />
              <input
                className={fieldClass}
                value={name}
                aria-invalid={errors.name !== undefined}
                onChange={(event) => setName(event.target.value)}
              />
              <FieldError message={errors.name} />
            </label>
            <label className="block">
              <FieldLabel label={t("station.kind")} tag="required" />
              <select
                className={fieldClass}
                value={kind}
                onChange={(event) => setKind(event.target.value as WaterSourceKind)}
              >
                {KINDS.map((item) => (
                  <option key={item} value={item}>
                    {t(kindKey(item))}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <FieldLabel label={t("station.ec")} tag="optional" />
              <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
                <input
                  className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
                  inputMode="decimal"
                  dir="ltr"
                  lang="en"
                  value={ec}
                  aria-invalid={errors.ec_ds_m !== undefined}
                  onChange={(event) => setEc(event.target.value)}
                />
                <span className="text-[12px] text-mut">{t("station.unitEc")}</span>
              </span>
              <FieldError message={errors.ec_ds_m} />
            </label>
            <label className="block">
              <FieldLabel label={t("station.basinVolume")} tag="optional" />
              <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
                <input
                  className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
                  inputMode="decimal"
                  dir="ltr"
                  lang="en"
                  value={volume}
                  aria-invalid={errors.basin_volume_m3 !== undefined}
                  onChange={(event) => setVolume(event.target.value)}
                />
                <span className="text-[12px] text-mut">{t("station.unitM3")}</span>
              </span>
              <Help>{t("station.basinHelp")}</Help>
              <FieldError message={errors.basin_volume_m3} />
            </label>
          </form>
        )}
        {sources.length === 0 && mode === "list" ? (
          <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
            <p className="text-[16px] font-bold">{t("station.sourcesEmpty")}</p>
            <p className="text-[13px] text-mut">{t("station.sourcesEmptyText")}</p>
          </div>
        ) : (
          <ul>
            {sources.map((source) => {
              const parts = [t(kindKey(source.kind))]
              if (source.ec_ds_m !== null) {
                parts.push(`${flowText(source.ec_ds_m, lang)} ${t("station.unitEc")}`)
              }
              if (source.basin_volume_m3 !== null) {
                parts.push(`${flowText(source.basin_volume_m3, lang)} ${t("station.unitM3")}`)
              }
              return (
                <li key={source.id} className="flex items-center gap-3 border-b border-line py-3 last:border-b-0">
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{source.name}</span>
                    <span className="block text-[12px] text-mut">{parts.join(" · ")}</span>
                  </span>
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      className="inline-flex size-8 items-center justify-center rounded-full text-[16px] text-mut"
                      aria-label={t("station.sourceMenu")}
                    >
                      ⋯
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => startEdit(source)}>{t("station.edit")}</DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => {
                          setDeleteError(null)
                          setPendingDelete(source)
                        }}
                      >
                        {t("station.delete")}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </li>
              )
            })}
          </ul>
        )}
        {pendingDelete !== null ? (
          <div className="rounded-2xl border border-line bg-[#F7F8F7] p-4">
            <h2 className="text-[16px] font-bold">{t("station.sourceDeleteTitle")}</h2>
            <p className="mt-2 text-[13px] text-mut">{t("station.sourceDeleteText")}</p>
            {deleteError !== null ? <p className="mt-2 text-[12px] text-red">{t(deleteError)}</p> : null}
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className={outlineBtn} onClick={() => setPendingDelete(null)} disabled={deleting}>
                {t("station.cancel")}
              </button>
              <button
                type="button"
                className={`${primaryBtn} disabled:opacity-60`}
                onClick={() => void confirmDelete()}
                disabled={deleting}
              >
                {t("station.deleteConfirm")}
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </Drawer>
  )
}
