import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { formatNumber } from "../../lib/format"
import { activeLang } from "../blocks/types"
import { primaryBtn } from "../weather/ui"
import { flowText } from "./display"
import type { FarmStation } from "./types"

export function StationSideCard() {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { currentFarmId } = useAuth()
  const stationQuery = useQuery({
    queryKey: ["station", currentFarmId],
    queryFn: () => apiGet<FarmStation>(`/v1/farms/${currentFarmId}/station`),
    enabled: currentFarmId !== null,
  })
  const data = stationQuery.data
  const pumps = data?.pumps ?? []
  let status = t("station.notSetUp")
  if (stationQuery.isLoading) status = t("common.loading")
  else if (stationQuery.isError) status = t("common.loadError")
  else if (data !== undefined && pumps.length > 0) {
    status = t("station.summary", {
      count: formatNumber(pumps.length, 0, lang),
      flow: flowText(data.totals.pumps_flow_m3h, lang),
    })
  }

  return (
    <section className="rounded-2xl border border-line bg-white p-4">
      <h2 className="text-[16px] font-bold">
        <Link to="/station">{t("nav.station")}</Link>
      </h2>
      <p className="mt-1 text-mut">{t("blocks.stationText")}</p>
      <p className="mt-3">{status}</p>
      {stationQuery.isError ? (
        <button type="button" className="mt-2 text-[13px] font-semibold text-pri" onClick={() => void stationQuery.refetch()}>
          {t("common.retry")}
        </button>
      ) : null}
      {data !== undefined && pumps.length === 0 ? (
        <Link to="/station" className={`mt-3 inline-flex items-center ${primaryBtn}`}>
          {t("station.setUp")}
        </Link>
      ) : null}
    </section>
  )
}
