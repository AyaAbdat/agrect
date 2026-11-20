import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useNavigate, useSearchParams } from "react-router"
import { useAuth } from "../../app/auth"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { activeLang, localizedName, type BlockListItem, type CatalogCrop } from "../blocks/types"
import { asNumber, decimalInput, isDecimal, wireDecimal } from "../weather/format"
import type { GddSettingListItem } from "../weather/types"
import {
  ChoiceChip,
  FieldError,
  LoadError,
  PageHeader,
  PageSkeleton,
  cardClass,
  fieldClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { codeLabelKey, countKey, fractionDigits, methodKey, scaleLabelKey } from "./display"
import { stageErrorKey } from "./errors"
import { SourcePill } from "./tags"
import type { CropStages, StageDdOut, StagePrefs } from "./types"

type DdChange = {
  stage_def_id: string
  dd_value: string | null
}

function ShowSwitch({
  shown,
  label,
  onChange,
}: {
  shown: boolean
  label: string
  onChange: (shown: boolean) => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={shown}
      aria-label={label}
      onClick={() => onChange(!shown)}
      className={`relative h-5 w-9 rounded-full ${shown ? "bg-pri" : "bg-[#D1D5DB]"}`}
    >
      <span
        className={`absolute top-0.5 size-4 rounded-full bg-white ${shown ? "end-0.5" : "start-0.5"}`}
      />
    </button>
  )
}

export function ModelSettingsPage() {
  const { t, i18n } = useTranslation()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { currentFarmId } = useAuth()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const [cropId, setCropId] = useState<string | null>(params.get("crop"))
  const [values, setValues] = useState<Record<string, string>>({})
  const [shown, setShown] = useState<Record<string, boolean>>({})
  const [seed, setSeed] = useState("")
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const farmId = currentFarmId
  const cropsQuery = useQuery({
    queryKey: ["catalog", "crops"],
    queryFn: () => apiGet<CatalogCrop[]>("/v1/catalog/crops"),
  })
  const blocksQuery = useQuery({
    queryKey: ["blocks", farmId],
    queryFn: () => apiGet<BlockListItem[]>(`/v1/farms/${farmId}/blocks`),
    enabled: farmId !== null,
  })
  const settingsQuery = useQuery({
    queryKey: ["gdd-settings", farmId],
    queryFn: () => apiGet<GddSettingListItem[]>(`/v1/farms/${farmId}/gdd-settings`),
    enabled: farmId !== null,
  })
  const catalogQuery = useQuery({
    queryKey: ["catalog", "stages", cropId],
    queryFn: () => apiGet<CropStages>(`/v1/catalog/crops/${cropId}/stages`),
    enabled: cropId !== null,
  })
  const ddQuery = useQuery({
    queryKey: ["stage-dd", farmId, cropId],
    queryFn: () => apiGet<StageDdOut>(`/v1/farms/${farmId}/stage-dd?crop_id=${cropId}`),
    enabled: farmId !== null && cropId !== null,
    staleTime: Infinity,
  })
  const prefsQuery = useQuery({
    queryKey: ["stage-prefs", farmId, cropId],
    queryFn: () => apiGet<StagePrefs>(`/v1/farms/${farmId}/stage-prefs?crop_id=${cropId}`),
    enabled: farmId !== null && cropId !== null,
    staleTime: Infinity,
  })

  useEffect(() => {
    if (cropId === null || ddQuery.data === undefined || prefsQuery.data === undefined) return
    const key = `${cropId}:${ddQuery.dataUpdatedAt}:${prefsQuery.dataUpdatedAt}`
    if (seed === key) return
    const nextValues: Record<string, string> = {}
    for (const row of ddQuery.data.stages) nextValues[row.stage_def_id] = decimalInput(row.dd_value)
    const hidden = new Map(prefsQuery.data.items.map((item) => [item.stage_def_id, item.hidden]))
    const nextShown: Record<string, boolean> = {}
    for (const row of ddQuery.data.stages) nextShown[row.stage_def_id] = hidden.get(row.stage_def_id) !== true
    setValues(nextValues)
    setShown(nextShown)
    setFieldErrors({})
    setSeed(key)
  }, [cropId, ddQuery.data, ddQuery.dataUpdatedAt, prefsQuery.data, prefsQuery.dataUpdatedAt, seed])

  if (farmId === null) return null
  const cropPending = cropId !== null && (catalogQuery.isPending || ddQuery.isPending || prefsQuery.isPending)
  if (cropsQuery.isPending || blocksQuery.isPending || settingsQuery.isPending || cropPending) {
    return <PageSkeleton />
  }
  if (
    cropsQuery.isError ||
    blocksQuery.isError ||
    settingsQuery.isError ||
    cropsQuery.data === undefined ||
    blocksQuery.data === undefined ||
    settingsQuery.data === undefined ||
    (cropId !== null &&
      (catalogQuery.isError ||
        ddQuery.isError ||
        prefsQuery.isError ||
        catalogQuery.data === undefined ||
        ddQuery.data === undefined ||
        prefsQuery.data === undefined))
  ) {
    return (
      <LoadError
        onRetry={() => {
          void cropsQuery.refetch()
          void blocksQuery.refetch()
          void settingsQuery.refetch()
          void catalogQuery.refetch()
          void ddQuery.refetch()
          void prefsQuery.refetch()
        }}
      />
    )
  }

  const crops = cropsQuery.data
  const crop = crops.find((row) => row.id === cropId) ?? null
  const setting = settingsQuery.data.find((row) => row.crop_id === cropId)
  const stages = ddQuery.data?.stages ?? []
  const scale = catalogQuery.data?.scale
  const block =
    blocksQuery.data.find((row) => row.crop?.id === cropId && row.status !== "archived") ??
    blocksQuery.data.find((row) => row.status !== "archived")
  const settingsTo = block === undefined ? "/blocks" : `/blocks/${block.id}/weather/degree-day-settings`
  const baseNumber = asNumber(setting?.base_c)
  const upperNumber = asNumber(setting?.upper_c ?? null)
  const baseLine =
    setting === undefined
      ? t("stages.notSet")
      : t("stages.baseLine", {
          base: formatNumber(baseNumber, fractionDigits(baseNumber), lang),
          upper:
            setting.upper_c === null
              ? t("common.missing")
              : formatNumber(upperNumber, fractionDigits(upperNumber), lang),
          method: t(methodKey(setting.method)),
        })

  function chooseCrop(next: string) {
    setCropId(next)
    setFormError(null)
    setFieldErrors({})
  }

  async function onSave() {
    if (cropId === null || ddQuery.data === undefined || prefsQuery.data === undefined) return
    setFormError(null)
    const nextErrors: Record<string, string> = {}
    const changed: DdChange[] = []
    const kept: DdChange[] = []
    const initialHidden = new Map(prefsQuery.data.items.map((item) => [item.stage_def_id, item.hidden]))
    for (const row of ddQuery.data.stages) {
      const current = (values[row.stage_def_id] ?? "").trim()
      const initial = decimalInput(row.dd_value)
      const entered = row.source === "entered"
      if (current === initial) {
        const wire = wireDecimal(current)
        if (entered && wire !== null) kept.push({ stage_def_id: row.stage_def_id, dd_value: wire })
        continue
      }
      if (current === "") {
        if (entered) changed.push({ stage_def_id: row.stage_def_id, dd_value: null })
        continue
      }
      if (!isDecimal(current)) {
        nextErrors[row.stage_def_id] = "stages.errors.number"
        continue
      }
      const wire = wireDecimal(current)
      if (wire === null || Number(wire) <= 0) {
        nextErrors[row.stage_def_id] = "stages.errors.positive"
        continue
      }
      changed.push({ stage_def_id: row.stage_def_id, dd_value: wire })
    }
    setFieldErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return
    if (changed.length > 0 && setting === undefined) {
      setFormError("stages.errors.noSetting")
      return
    }
    const prefItems = ddQuery.data.stages.flatMap((row) => {
      const hidden = shown[row.stage_def_id] === false
      const was = initialHidden.get(row.stage_def_id) === true
      if (hidden === was) return []
      return [{ stage_def_id: row.stage_def_id, hidden, local_name: null }]
    })
    if (changed.length === 0 && prefItems.length === 0) return
    const payload = setting === undefined ? [] : [...changed, ...kept]
    setSaving(true)
    try {
      if (prefItems.length > 0) {
        await apiSend<StagePrefs>("PUT", `/v1/farms/${farmId}/stage-prefs`, { items: prefItems })
      }
      if (payload.length > 0 && setting !== undefined) {
        await apiSend<StageDdOut>("PUT", `/v1/farms/${farmId}/stage-dd`, {
          crop_id: cropId,
          items: payload.map((item) => ({
            stage_def_id: item.stage_def_id,
            dd_value: item.dd_value,
            base_c: setting.base_c,
            upper_c: setting.upper_c,
            method: setting.method,
          })),
        })
      }
    } catch (error) {
      if (error instanceof ApiError) {
        const mapped: Record<string, string> = {}
        for (const [key, code] of Object.entries(error.fields)) {
          const match = /^items\.(\d+)\./.exec(key)
          const index = match === null ? null : Number(match[1])
          const stageId = index === null ? undefined : payload[index]?.stage_def_id
          if (stageId !== undefined) mapped[stageId] = stageErrorKey(code)
        }
        setFieldErrors(mapped)
        if (Object.keys(mapped).length === 0) setFormError(stageErrorKey(error.code))
      } else {
        setFormError("stages.errors.save")
      }
      setSaving(false)
      return
    }
    setSeed("")
    await queryClient.invalidateQueries({ queryKey: ["stage-dd", farmId, cropId] })
    await queryClient.invalidateQueries({ queryKey: ["stage-prefs", farmId, cropId] })
    await queryClient.invalidateQueries({ queryKey: ["block-stages"] })
    await queryClient.invalidateQueries({ queryKey: ["stage-summary"] })
    setSaving(false)
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("stages.season")}
        title={t("stages.settingsTitle")}
        sub={t("stages.settingsSub")}
        actions={
          <button type="button" className={outlineBtn} onClick={() => void navigate(-1)}>
            {t("stages.back")}
          </button>
        }
      />
      <div className="flex flex-wrap gap-2">
        {crops.map((row) => (
          <ChoiceChip
            key={row.id}
            selected={row.id === cropId}
            onClick={() => chooseCrop(row.id)}
          >
            {localizedName(row.name, lang)}
          </ChoiceChip>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <span className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold">{t("stages.variety")}</span>
            <span className="rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
              {t("settings.phase2")}
            </span>
          </span>
          <button type="button" disabled className={`${fieldClass} text-start text-mut`}>
            {t("stages.chooseVariety")}
          </button>
          <p className="mt-1 text-[12px] text-mut">{t("stages.varietyHelp")}</p>
        </div>
        <div>
          <p className="mb-1.5 text-[13px] font-semibold">{t("stages.countFrom")}</p>
          <p className={`${fieldClass} flex items-center bg-[#F7F8F7] text-mut`}>
            {crop === null ? t("common.missing") : t(countKey(crop.code))}
          </p>
        </div>
      </div>
      <section className={cardClass}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-[16px] font-bold">{t("stages.baseCard")}</h2>
            <p className="mt-1 text-[13px] text-mut">{t("stages.baseHelp")}</p>
          </div>
          <Link to={settingsTo} className={`inline-flex items-center ${outlineBtn}`}>
            {t("stages.openSettings")}
          </Link>
        </div>
        <p className="mt-3 text-[15px] font-semibold">{baseLine}</p>
      </section>
      <section className={cardClass}>
        <h2 className="text-[16px] font-bold">{t("stages.stagesDd")}</h2>
        {crop === null || scale === undefined ? (
          <div className="py-12 text-center">
            <p className="font-semibold">{t("stages.pickCrop")}</p>
            <p className="mt-1 text-[13px] text-mut">{t("stages.pickCropText")}</p>
          </div>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[680px] text-start text-[13px]">
              <thead>
                <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-wide text-mut">
                  <th className="px-2 py-2 font-semibold">{t("stages.colStage")}</th>
                  <th className="px-2 py-2 font-semibold">{t("stages.colCode")}</th>
                  <th className="px-2 py-2 font-semibold">{t("stages.colDd")}</th>
                  <th className="px-2 py-2 font-semibold">{t("stages.colSource")}</th>
                  <th className="px-2 py-2 text-end font-semibold">{t("stages.colShow")}</th>
                </tr>
              </thead>
              <tbody>
                {stages.map((row) => (
                  <tr key={row.stage_def_id} className="border-b border-line last:border-b-0">
                    <td className="px-2 py-3 font-semibold">{localizedName(row.name, lang)}</td>
                    <td className="px-2 py-3 text-mut">
                      {t(codeLabelKey(scale), { code: row.code })}
                    </td>
                    <td className="px-2 py-3">
                      <input
                        className={`${fieldClass} max-w-[140px]`}
                        inputMode="decimal"
                        dir="ltr"
                        lang="en"
                        value={values[row.stage_def_id] ?? ""}
                        aria-invalid={fieldErrors[row.stage_def_id] !== undefined}
                        onChange={(change) =>
                          setValues((current) => ({ ...current, [row.stage_def_id]: change.target.value }))
                        }
                      />
                      <FieldError message={fieldErrors[row.stage_def_id]} />
                    </td>
                    <td className="px-2 py-3">
                      {row.source === null || row.dd_value === null ? (
                        t("common.missing")
                      ) : (
                        <SourcePill source={row.source} citation={row.citation} />
                      )}
                    </td>
                    <td className="px-2 py-3 text-end">
                      <ShowSwitch
                        shown={shown[row.stage_def_id] !== false}
                        label={t("stages.colShow")}
                        onChange={(next) =>
                          setShown((current) => ({ ...current, [row.stage_def_id]: next }))
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[12px] text-mut">
              {t("stages.tableIntro", { crop: localizedName(crop.name, lang), scale: t(scaleLabelKey(scale)) })}
            </p>
          </div>
        )}
      </section>
      <section className={cardClass}>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[16px] font-bold">{t("stages.chill")}</h2>
          <span className="rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
            {t("settings.phase2")}
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-4">
          <label className="block">
            <span className="mb-1.5 flex items-center justify-between">
              <span className="text-[13px] font-semibold">{t("stages.chillHours")}</span>
              <span className="rounded-full bg-[#E5E7EB] px-2 py-0.5 text-[10px] font-semibold text-mut">
                {t("stages.optional")}
              </span>
            </span>
            <span className="flex h-10 items-center rounded-[10px] border border-line bg-[#F3F5F3] pe-3 text-mut">
              <input
                disabled
                value="0"
                dir="ltr"
                lang="en"
                className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
              />
              <span className="text-[12px]">{t("stages.unitHour")}</span>
            </span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-semibold">{t("stages.chillPortions")}</span>
            <input
              disabled
              value="0"
              dir="ltr"
              lang="en"
              className={`${fieldClass} bg-[#F3F5F3] text-mut`}
            />
          </label>
        </div>
      </section>
      <div className="flex items-center justify-end gap-3">
        {formError !== null ? <FieldError message={formError} /> : null}
        <button type="button" className={primaryBtn} disabled={saving || cropId === null} onClick={() => void onSave()}>
          {saving ? t("stages.saving") : t("stages.save")}
        </button>
      </div>
    </div>
  )
}
