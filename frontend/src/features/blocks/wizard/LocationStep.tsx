import { zodResolver } from "@hookform/resolvers/zod"
import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"
import { z } from "zod"
import { SatelliteMap } from "../../../components/map/SatelliteMap"
import type { MapGeometry } from "../../../components/map/geometry"
import { useAuth } from "../../../app/auth"
import { ApiError, apiSend } from "../../../lib/api"
import { formatNumber } from "../../../lib/format"
import {
  blockErrorKey,
  decimalInput,
  isPositiveDecimal,
  normalizeDecimal,
} from "../errors"
import { reasonPayload, requireReason } from "./blockWrite"
import { activeLang, type BlockDetail } from "../types"
import { LOCATION_FORM_ID } from "./steps"

const locationSchema = z.object({
  name: z.string().trim().min(1, "blocks.errors.nameRequired").max(255, "blocks.errors.nameRequired"),
  net_area_ha: z
    .string()
    .trim()
    .refine((value) => isPositiveDecimal(value), { message: "blocks.errors.netPositive" }),
})

type LocationValues = z.infer<typeof locationSchema>

type GeometryPreview = {
  gross_area_ha: string | null
  row_bearing_deg: string | null
  source: "calculated"
}

type GeoErrors = {
  outline?: string
  row_line?: string
}

const fieldClass =
  "h-10 w-full rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px] outline-none focus:ring-2 focus:ring-mint"

function showDecimal(value: string | null, places: number, lang: string, missing: string): string {
  if (value === null) return missing
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return missing
  return formatNumber(parsed, places, lang)
}

function CalculatedValue({
  value,
  unit,
  tip,
}: {
  value: string
  unit: string
  tip: string
}) {
  return (
    <div
      title={tip}
      className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-[#F4F7F4] px-3 text-[13px]"
    >
      <span className="flex-1">{value}</span>
      <span className="text-mut">{unit}</span>
    </div>
  )
}

function FieldError({ message }: { message: string | undefined }) {
  const { t } = useTranslation()
  if (message === undefined || message === "") return null
  return <p className="mt-1 text-[12px] text-red">{t(message)}</p>
}

export function LocationStep({
  blockId,
  block,
  reason,
  onReasonError,
  onBusy,
}: {
  blockId: string | undefined
  block: BlockDetail | null
  reason: string
  onReasonError: (message: string | null) => void
  onBusy: (busy: boolean) => void
}) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { currentFarmId } = useAuth()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const versionRef = useRef(block?.version ?? 1)
  versionRef.current = block?.version ?? versionRef.current
  const [geometry, setGeometry] = useState<MapGeometry>({
    outline: block?.outline ?? null,
    row_line: block?.row_line ?? null,
  })
  const [preview, setPreview] = useState<GeometryPreview | null>(null)
  const [geoErrors, setGeoErrors] = useState<GeoErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const requestRef = useRef(0)
  const form = useForm<LocationValues>({
    resolver: zodResolver(locationSchema),
    defaultValues: {
      name: block?.name ?? "",
      net_area_ha: decimalInput(block?.net_area_ha ?? null),
    },
  })

  useEffect(() => {
    if (geometry.outline === null && geometry.row_line === null) {
      setPreview(null)
      setGeoErrors({})
      return
    }
    const request = ++requestRef.current
    const timer = window.setTimeout(() => {
      void apiSend<GeometryPreview>("POST", "/v1/calc/registry/geometry", {
        outline: geometry.outline,
        row_line: geometry.row_line,
      })
        .then((result) => {
          if (requestRef.current !== request) return
          setPreview(result)
          setGeoErrors({})
        })
        .catch((error: unknown) => {
          if (requestRef.current !== request) return
          setPreview(null)
          if (error instanceof ApiError && error.code === "validation_error") {
            setGeoErrors({
              outline: error.fields.outline ? blockErrorKey(error.fields.outline) : undefined,
              row_line: error.fields.row_line ? blockErrorKey(error.fields.row_line) : undefined,
            })
            return
          }
          setGeoErrors({ outline: "blocks.errors.preview" })
        })
    }, 300)
    return () => window.clearTimeout(timer)
  }, [geometry])

  async function onSubmit(values: LocationValues, event?: { nativeEvent?: Event }) {
    if (currentFarmId === null) return
    const submitter =
      event?.nativeEvent instanceof SubmitEvent ? event.nativeEvent.submitter : null
    const action =
      submitter instanceof HTMLElement && submitter.dataset.action === "draft" ? "draft" : "next"
    if (block !== null && !requireReason(block, reason, onReasonError)) return
    setFormError(null)
    onBusy(true)
    try {
      const body = {
        name: values.name.trim(),
        net_area_ha: normalizeDecimal(values.net_area_ha),
        outline: geometry.outline,
        row_line: geometry.row_line,
        ...(block === null ? {} : reasonPayload(block, reason)),
      }
      const saved =
        blockId === undefined
          ? await apiSend<BlockDetail>("POST", `/v1/farms/${currentFarmId}/blocks`, body)
          : await apiSend<BlockDetail>("PATCH", `/v1/blocks/${blockId}`, body, {
              "If-Match": String(versionRef.current),
            })
      versionRef.current = saved.version
      queryClient.setQueryData(["block", saved.id], saved)
      await queryClient.invalidateQueries({ queryKey: ["blocks", currentFarmId] })
      if (action === "draft") {
        void navigate("/blocks")
      } else {
        void navigate(`/blocks/${saved.id}/edit?step=2`)
      }
    } catch (error) {
      if (error instanceof ApiError && error.code === "validation_error") {
        if (error.fields.reason) onReasonError(blockErrorKey(error.fields.reason))
        if (error.fields.name) form.setError("name", { message: blockErrorKey(error.fields.name) })
        if (error.fields.net_area_ha) {
          form.setError("net_area_ha", { message: blockErrorKey(error.fields.net_area_ha) })
        }
        setGeoErrors({
          outline: error.fields.outline ? blockErrorKey(error.fields.outline) : geoErrors.outline,
          row_line: error.fields.row_line ? blockErrorKey(error.fields.row_line) : geoErrors.row_line,
        })
      } else if (error instanceof ApiError && (error.status === 409 || error.status === 428)) {
        setFormError("blocks.errors.version")
      } else {
        setFormError("blocks.errors.save")
      }
    } finally {
      onBusy(false)
    }
  }

  const nameError = form.formState.errors.name?.message
  const netError = form.formState.errors.net_area_ha?.message
  const missing = t("common.missing")

  return (
    <>
      <form
        id={LOCATION_FORM_ID}
        className="flex w-[380px] shrink-0 flex-col gap-4 rounded-2xl border border-line bg-white p-4"
        noValidate
        onSubmit={(event) => {
          void form.handleSubmit((values) => onSubmit(values, event))(event)
        }}
      >
        <label className="block">
          <span className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold">{t("blocks.name")}</span>
            <span className="rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[10px] font-semibold text-amb">
              {t("blocks.required")}
            </span>
          </span>
          <input className={fieldClass} autoComplete="off" {...form.register("name")} />
          <FieldError message={nameError} />
        </label>
        <div>
          <span className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold">{t("blocks.grossArea")}</span>
            <span className="rounded-full bg-mint px-2 py-0.5 text-[10px] font-semibold text-pri">
              {t("blocks.calculated")}
            </span>
          </span>
          <CalculatedValue
            value={showDecimal(preview?.gross_area_ha ?? null, 2, lang, missing)}
            unit={t("blocks.unitHa")}
            tip={t("blocks.grossTip")}
          />
          <FieldError message={geoErrors.outline} />
        </div>
        <div>
          <span className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold">{t("blocks.rowDirection")}</span>
            <span className="rounded-full bg-mint px-2 py-0.5 text-[10px] font-semibold text-pri">
              {t("blocks.calculated")}
            </span>
          </span>
          <CalculatedValue
            value={showDecimal(preview?.row_bearing_deg ?? null, 1, lang, missing)}
            unit={t("blocks.unitDeg")}
            tip={t("blocks.bearingTip")}
          />
          <FieldError message={geoErrors.row_line} />
        </div>
        <label className="block">
          <span className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold">{t("blocks.netArea")}</span>
            <span className="rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[10px] font-semibold text-amb">
              {t("blocks.required")}
            </span>
          </span>
          <span className="flex h-10 items-center rounded-[10px] border border-[#C7D2C9] bg-white pe-3 focus-within:ring-2 focus-within:ring-mint">
            <input
              className="h-full min-w-0 flex-1 bg-transparent px-3 text-[13px] outline-none"
              inputMode="decimal"
              autoComplete="off"
              {...form.register("net_area_ha")}
            />
            <span className="text-mut">{t("blocks.unitHa")}</span>
          </span>
          <p className="mt-1 text-[12px] text-mut">{t("blocks.netHelp")}</p>
          <FieldError message={netError} />
        </label>
        {formError !== null ? <p className="text-[12px] text-red">{t(formError)}</p> : null}
      </form>
      <div className="min-w-0 flex-1">
        <SatelliteMap
          height={560}
          drawing
          initial={geometry}
          onChange={setGeometry}
        />
      </div>
    </>
  )
}
