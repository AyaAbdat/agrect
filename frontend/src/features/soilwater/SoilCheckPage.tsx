import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useNavigate, useParams } from "react-router"
import { useAuth } from "../../app/auth"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { activeLang, type BlockDetail } from "../blocks/types"
import { EnteredTag } from "../blocks/wizard/wizardUi"
import { asNumber, farmToday } from "../weather/format"
import {
  ChoiceChip,
  FieldError,
  FieldLabel,
  LoadError,
  PageHeader,
  PageSkeleton,
  SourceTag,
  cardClass,
  fieldClass,
  outlineBtn,
  primaryBtn,
} from "../weather/ui"
import { mm2 } from "./display"
import { soilErrorKey } from "./errors"
import { refreshWater } from "./refresh"
import type { DepthBand, FarmClock, SoilCheckPreview, SoilFeel } from "./types"

const feels: { id: SoilFeel; label: string; help: string }[] = [
  { id: "dry", label: "soil.feelDry", help: "soil.feelDryHelp" },
  { id: "slightly_moist", label: "soil.feelSlight", help: "soil.feelSlightHelp" },
  { id: "moist", label: "soil.feelMoist", help: "soil.feelMoistHelp" },
  { id: "wet", label: "soil.feelWet", help: "soil.feelWetHelp" },
]

export function SoilCheckPage() {
  const { t, i18n } = useTranslation()
  const { blockId } = useParams()
  const navigate = useNavigate()
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const farmId = currentFarmId
  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const today = farmQuery.data === undefined ? "" : farmToday(farmQuery.data.timezone)
  const [date, setDate] = useState<string | null>(null)
  const [depth, setDepth] = useState<DepthBand>("0_30")
  const [feel, setFeel] = useState<SoilFeel | null>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const chosenDate = date ?? today
  const previewQuery = useQuery({
    queryKey: ["soil-check-preview", blockId, feel],
    queryFn: () =>
      apiSend<SoilCheckPreview>("POST", `/v1/blocks/${blockId}/soil-checks/preview`, { feel }),
    enabled: blockId !== undefined && feel !== null,
    retry: false,
  })

  if (blockId === undefined || farmId === null) return null
  if (farmQuery.isPending || blockQuery.isPending) return <PageSkeleton />
  if (
    farmQuery.isError ||
    blockQuery.isError ||
    farmQuery.data === undefined ||
    blockQuery.data === undefined
  ) {
    return (
      <LoadError
        onRetry={() => {
          void queryClient.invalidateQueries({ queryKey: ["farm", farmId] })
          void queryClient.invalidateQueries({ queryKey: ["block", blockId] })
        }}
      />
    )
  }

  const preview = previewQuery.data
  const tawMissing =
    previewQuery.error instanceof ApiError && previewQuery.error.fields.taw_mm === "soil.taw_missing"
  const left = preview === undefined ? null : preview.water_left_mm
  const pct =
    preview === undefined
      ? formatNumber(null, 1, lang)
      : formatNumber(asNumber(preview.pct_of_taw), 1, lang)

  async function onSave() {
    if (feel === null || chosenDate === "") return
    setSaving(true)
    setFormError(null)
    try {
      await apiSend("POST", `/v1/blocks/${blockId}/soil-checks`, {
        date: chosenDate,
        depth_band: depth,
        feel,
      })
    } catch (error) {
      setSaving(false)
      if (error instanceof ApiError && error.fields.taw_mm !== undefined) {
        setFormError(soilErrorKey(error.fields.taw_mm))
        return
      }
      setFormError("soil.errors.save")
      return
    }
    await refreshWater(queryClient, blockId, farmId)
    navigate(`/blocks/${blockId}/soil-water`)
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumb={t("soil.setupCrumb")}
        title={t("soil.checkTitle")}
        sub={t("soil.checkPageSub", { block: blockQuery.data.name })}
        actions={
          <Link
            to={`/blocks/${blockId}/soil-water`}
            className={`inline-flex items-center ${outlineBtn}`}
          >
            {t("soil.back")}
          </Link>
        }
      />
      <section className={cardClass}>
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-4">
          <label className="block max-w-sm">
            <FieldLabel label={t("soil.date")} tag="required" />
            <input
              type="date"
              dir="ltr"
              lang="en"
              className={fieldClass}
              value={chosenDate}
              onChange={(change) => setDate(change.target.value)}
            />
          </label>
          <div>
            <FieldLabel label={t("soil.depthBand")} />
            <div className="flex gap-2">
              <ChoiceChip selected={depth === "0_30"} onClick={() => setDepth("0_30")}>
                {t("soil.depth030")}
              </ChoiceChip>
              <ChoiceChip selected={depth === "30_60"} onClick={() => setDepth("30_60")}>
                {t("soil.depth3060")}
              </ChoiceChip>
            </div>
          </div>
        </div>
        <h2 className="mt-5 text-[13px] font-semibold uppercase tracking-wide text-pri">
          {t("soil.feelTitle")}
        </h2>
        <div className="mt-3 grid grid-cols-4 gap-3" role="radiogroup" aria-label={t("soil.feelTitle")}>
          {feels.map((option) => {
            const selected = feel === option.id
            return (
              <button
                key={option.id}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setFeel(option.id)}
                className={`rounded-xl border p-3 text-start ${
                  selected ? "border-pri bg-mint" : "border-line bg-white"
                }`}
              >
                <span className="flex items-center gap-2 font-semibold">
                  <span
                    className={`size-4 shrink-0 rounded-full border ${
                      selected ? "border-pri bg-pri" : "border-[#C7D2C9] bg-white"
                    }`}
                  />
                  {t(option.label)}
                </span>
                <span className="mt-1 block ps-6 text-[12px] text-mut">{t(option.help)}</span>
              </button>
            )
          })}
        </div>
        <div className="mt-4 rounded-xl bg-[#F7F8F7] p-4">
          <div className="flex items-start justify-between gap-2">
            <p className="text-[15px] font-bold">
              {t("soil.resetLine", { left: mm2(left, lang), pct })}
            </p>
            <SourceTag kind="calculated" />
          </div>
          <p className="mt-2 flex items-center gap-2 text-[13px] text-mut">
            <span>{t("soil.resetNote")}</span>
            <EnteredTag />
          </p>
          {tawMissing ? (
            <p className="mt-2 text-[12px] text-red">
              {t("soil.errors.tawMissing")}{" "}
              <Link to={`/blocks/${blockId}/soil-water/soil`} className="font-semibold text-pri">
                {t("soil.setupSoil")}
              </Link>
            </p>
          ) : null}
        </div>
        {formError !== null ? <FieldError message={formError} /> : null}
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            className={primaryBtn}
            disabled={feel === null || chosenDate === "" || saving}
            onClick={() => void onSave()}
          >
            {t("soil.saveCheck")}
          </button>
        </div>
      </section>
    </div>
  )
}
