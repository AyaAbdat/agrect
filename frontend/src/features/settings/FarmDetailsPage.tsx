import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { NavLink } from "react-router"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useAuth } from "../../app/auth"
import { settingsNav, settingsPath } from "../../app/navigation"
import { SatelliteMap, type MarkerPosition } from "../../components/map/SatelliteMap"
import { ApiError, apiGet, apiSend } from "../../lib/api"
import { crumbClass, navItemClass, sectionLabelClass } from "../../lib/navStyles"
import {
  FieldError,
  FieldLabel,
  LoadError,
  PageSkeleton,
  fieldClass,
  primaryBtn,
} from "../weather/ui"

type FarmDetailsOut = {
  id: string
  name: string
  lat: string | number | null
  lon: string | number | null
  timezone: string
  weather_source: "service" | "station"
  version: number
}

type FieldErrors = {
  lat?: string
  lon?: string
  timezone?: string
  weather_source?: string
}

function formatCoord(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return ""
  const parsed = typeof value === "number" ? value : Number(value)
  if (!Number.isFinite(parsed)) return ""
  return parsed.toFixed(6)
}

function parseFiniteCoord(value: string): number | null {
  const trimmed = value.trim()
  if (trimmed === "") return null
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

function serverErrorKey(code: string): string {
  switch (code) {
    case "farm.lat_out_of_range":
      return "farmDetails.errors.latOutOfRange"
    case "farm.lon_out_of_range":
      return "farmDetails.errors.lonOutOfRange"
    case "farm.timezone_invalid":
      return "farmDetails.errors.timezoneInvalid"
    case "farm.station_not_supported":
      return "farmDetails.errors.stationNotSupported"
    default:
      return "farmDetails.errors.save"
  }
}

function supportedTimeZones(current: string): string[] {
  let list: string[] = []
  if (typeof Intl.supportedValuesOf === "function") {
    try {
      list = Intl.supportedValuesOf("timeZone")
    } catch {
      list = []
    }
  }
  if (current !== "" && !list.includes(current)) {
    return [current, ...list]
  }
  return list
}

export function FarmDetailsPage() {
  const { t } = useTranslation()
  const { currentFarmId } = useAuth()
  const queryClient = useQueryClient()
  const farmId = currentFarmId

  const farmQuery = useQuery({
    queryKey: ["farm", farmId],
    queryFn: () => apiGet<FarmDetailsOut>(`/v1/farms/${farmId}`),
    enabled: farmId !== null,
  })

  const [latInput, setLatInput] = useState("")
  const [lonInput, setLonInput] = useState("")
  const [timezone, setTimezone] = useState("")
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [savedNotice, setSavedNotice] = useState(false)
  const [saving, setSaving] = useState(false)
  const seededFarmId = useRef<string | null>(null)

  useEffect(() => {
    const farm = farmQuery.data
    if (farm === undefined || seededFarmId.current === farm.id) return
    seededFarmId.current = farm.id
    setLatInput(formatCoord(farm.lat))
    setLonInput(formatCoord(farm.lon))
    setTimezone(farm.timezone)
    setFieldErrors({})
    setFormError(null)
  }, [farmQuery.data])

  const timeZones = useMemo(() => supportedTimeZones(timezone), [timezone])

  const marker: MarkerPosition | null = useMemo(() => {
    const lat = parseFiniteCoord(latInput)
    const lon = parseFiniteCoord(lonInput)
    if (lat === null || lon === null) return null
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null
    return { lat, lon }
  }, [latInput, lonInput])

  function handleMarkerChange(pos: MarkerPosition) {
    setLatInput(pos.lat.toFixed(6))
    setLonInput(pos.lon.toFixed(6))
    setFieldErrors((prev) => ({ ...prev, lat: undefined, lon: undefined }))
    setSavedNotice(false)
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (farmId === null) return
    setFormError(null)
    setSavedNotice(false)

    const nextErrors: FieldErrors = {}
    const parsedLat = parseFiniteCoord(latInput)
    const parsedLon = parseFiniteCoord(lonInput)
    if (latInput.trim() === "") nextErrors.lat = "farmDetails.errors.latRequired"
    else if (parsedLat === null) nextErrors.lat = "farmDetails.errors.number"
    if (lonInput.trim() === "") nextErrors.lon = "farmDetails.errors.lonRequired"
    else if (parsedLon === null) nextErrors.lon = "farmDetails.errors.number"
    if (timezone.trim() === "") nextErrors.timezone = "farmDetails.errors.timezoneInvalid"

    if (Object.keys(nextErrors).length > 0) {
      setFieldErrors(nextErrors)
      return
    }

    setFieldErrors({})
    setSaving(true)
    try {
      const updated = await apiSend<FarmDetailsOut>(
        "PUT",
        `/v1/farms/${farmId}/weather-source`,
        {
          weather_source: "service",
          lat: parsedLat!.toFixed(6),
          lon: parsedLon!.toFixed(6),
          timezone,
        },
      )
      setLatInput(formatCoord(updated.lat))
      setLonInput(formatCoord(updated.lon))
      setTimezone(updated.timezone)
      await queryClient.invalidateQueries({ queryKey: ["farm", farmId] })
      await queryClient.invalidateQueries({ queryKey: ["weather", farmId] })
      setSavedNotice(true)
    } catch (error) {
      if (error instanceof ApiError) {
        const mapped: FieldErrors = {}
        if (error.fields.lat !== undefined) mapped.lat = serverErrorKey(error.fields.lat)
        if (error.fields.lon !== undefined) mapped.lon = serverErrorKey(error.fields.lon)
        if (error.fields.timezone !== undefined) {
          mapped.timezone = serverErrorKey(error.fields.timezone)
        }
        if (error.fields.weather_source !== undefined) {
          mapped.weather_source = serverErrorKey(error.fields.weather_source)
        }
        if (Object.keys(mapped).length > 0) {
          setFieldErrors(mapped)
        } else {
          setFormError(serverErrorKey(error.code))
        }
      } else {
        setFormError("farmDetails.errors.save")
      }
    } finally {
      setSaving(false)
    }
  }

  if (farmId === null) return null

  return (
    <div className="flex flex-col gap-5">
      <header>
        <p className={crumbClass}>{t("settings.crumb")}</p>
        <h1 className="text-[24px] font-bold leading-tight">{t("settings.title")}</h1>
        <p className="mt-1 text-mut">{t("settings.sub")}</p>
      </header>
      <div className="flex items-start gap-5">
        <nav className="w-[260px] shrink-0 rounded-2xl border border-line bg-white p-3">
          {settingsNav.map((group) => (
            <div key={group.labelKey}>
              <p className={sectionLabelClass}>{t(group.labelKey)}</p>
              {group.items.map((item) => (
                <NavLink
                  key={item.id}
                  to={settingsPath(item.id)}
                  end
                  className={({ isActive }) => navItemClass(isActive)}
                >
                  {t(item.labelKey)}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <section className="min-w-0 flex-1">
          {farmQuery.isLoading ? <PageSkeleton /> : null}
          {farmQuery.isError ? (
            <LoadError onRetry={() => void farmQuery.refetch()} />
          ) : null}
          {farmQuery.isSuccess && farmQuery.data !== undefined ? (
            <form
              className="flex flex-col gap-5 rounded-2xl border border-line bg-white p-5"
              onSubmit={(event) => void handleSubmit(event)}
              noValidate
            >
              <div>
                <h2 className="text-[16px] font-bold">{t("settings.farmDetails")}</h2>
                <p className="mt-1 text-[13px] text-mut">{t("farmDetails.sub")}</p>
              </div>

              <div>
                <FieldLabel label={t("farmDetails.nameLabel")} />
                <input
                  type="text"
                  readOnly
                  value={farmQuery.data.name}
                  className={`${fieldClass} cursor-not-allowed bg-[#F9FAFB] text-mut`}
                />
                <p className="mt-1 text-[12px] text-mut">{t("farmDetails.renameNote")}</p>
              </div>

              <div className="flex flex-col gap-3">
                <div>
                  <FieldLabel label={t("farmDetails.locationLabel")} tag="required" />
                  <p className="text-[12px] text-mut">{t("farmDetails.mapHint")}</p>
                </div>
                <SatelliteMap
                  height={320}
                  marker={marker}
                  onMarkerChange={handleMarkerChange}
                />
                <div className="grid grid-cols-2 gap-3">
                  <label className="block min-w-0">
                    <FieldLabel label={t("farmDetails.latLabel")} tag="required" />
                    <input
                      type="text"
                      inputMode="decimal"
                      dir="ltr"
                      lang="en"
                      autoComplete="off"
                      placeholder="36.753800"
                      value={latInput}
                      onChange={(event) => {
                        setLatInput(event.target.value)
                        setFieldErrors((prev) => ({ ...prev, lat: undefined }))
                        setSavedNotice(false)
                      }}
                      aria-invalid={fieldErrors.lat !== undefined}
                      className={fieldClass}
                    />
                    <FieldError message={fieldErrors.lat} />
                  </label>
                  <label className="block min-w-0">
                    <FieldLabel label={t("farmDetails.lonLabel")} tag="required" />
                    <input
                      type="text"
                      inputMode="decimal"
                      dir="ltr"
                      lang="en"
                      autoComplete="off"
                      placeholder="3.058800"
                      value={lonInput}
                      onChange={(event) => {
                        setLonInput(event.target.value)
                        setFieldErrors((prev) => ({ ...prev, lon: undefined }))
                        setSavedNotice(false)
                      }}
                      aria-invalid={fieldErrors.lon !== undefined}
                      className={fieldClass}
                    />
                    <FieldError message={fieldErrors.lon} />
                  </label>
                </div>
              </div>

              <label className="block min-w-0">
                <FieldLabel label={t("farmDetails.timezoneLabel")} tag="required" />
                <select
                  dir="ltr"
                  value={timezone}
                  onChange={(event) => {
                    setTimezone(event.target.value)
                    setFieldErrors((prev) => ({ ...prev, timezone: undefined }))
                    setSavedNotice(false)
                  }}
                  aria-invalid={fieldErrors.timezone !== undefined}
                  className={fieldClass}
                >
                  {timeZones.map((tz) => (
                    <option key={tz} value={tz}>
                      {tz}
                    </option>
                  ))}
                </select>
                <FieldError message={fieldErrors.timezone} />
              </label>

              <div>
                <FieldLabel label={t("farmDetails.weatherSourceLabel")} />
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-2 rounded-[14px] border border-pri bg-mint p-4">
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2 text-[13px] font-semibold">
                        <span className="flex size-4 items-center justify-center rounded-full border-2 border-pri">
                          <span className="size-2 rounded-full bg-pri" />
                        </span>
                        {t("farmDetails.weatherService")}
                      </span>
                      <Badge className="bg-pri text-white">{t("settings.current")}</Badge>
                    </div>
                  </div>
                  <div
                    className="flex flex-col gap-2 rounded-[14px] border border-line bg-[#F9FAFB] p-4"
                    aria-disabled="true"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2 text-[13px] font-semibold text-mut">
                        <span className="size-4 rounded-full border-2 border-[#9CA3AF]" />
                        {t("farmDetails.weatherStation")}
                      </span>
                      <Badge variant="secondary" className="bg-[#E5E7EB] text-mut">
                        {t("settings.phase2")}
                      </Badge>
                    </div>
                  </div>
                </div>
                <FieldError message={fieldErrors.weather_source} />
              </div>

              {savedNotice ? (
                <div
                  role="status"
                  className="rounded-xl bg-mint px-4 py-3 text-[13px] font-medium text-pri"
                >
                  {t("farmDetails.saved")}
                </div>
              ) : null}

              <div className="flex items-center justify-end gap-3">
                <FieldError message={formError ?? undefined} />
                <Button type="submit" className={primaryBtn} disabled={saving}>
                  {saving ? t("farmDetails.saving") : t("farmDetails.save")}
                </Button>
              </div>
            </form>
          ) : null}
        </section>
      </div>
    </div>
  )
}
