import { useQuery } from "@tanstack/react-query"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import type { BlockDetail, CatalogVariety } from "../blocks/types"
import type { GddSettingListItem } from "../weather/types"
import { farmToday } from "../weather/format"
import { readBlockStages } from "./load"
import type { CropStages, StagePrefs } from "./types"

type FarmClock = {
  timezone: string
}

export function useBlockSeason(blockId: string | undefined) {
  const { currentFarmId } = useAuth()
  const farmQuery = useQuery({
    queryKey: ["farm", currentFarmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${currentFarmId}`),
    enabled: currentFarmId !== null,
  })
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const timezone = farmQuery.data?.timezone ?? null
  const today = timezone === null ? null : farmToday(timezone)
  const year = today === null ? null : Number(today.slice(0, 4))
  const cropId = blockQuery.data?.crop?.id ?? null
  const catalogQuery = useQuery({
    queryKey: ["catalog", "stages", cropId],
    queryFn: () => apiGet<CropStages>(`/v1/catalog/crops/${cropId}/stages`),
    enabled: cropId !== null,
  })
  const varietiesQuery = useQuery({
    queryKey: ["catalog", "varieties", cropId],
    queryFn: () => apiGet<CatalogVariety[]>(`/v1/catalog/crops/${cropId}/varieties`),
    enabled: cropId !== null,
  })
  const settingsQuery = useQuery({
    queryKey: ["gdd-settings", currentFarmId],
    queryFn: () => apiGet<GddSettingListItem[]>(`/v1/farms/${currentFarmId}/gdd-settings`),
    enabled: currentFarmId !== null,
  })
  const prefsQuery = useQuery({
    queryKey: ["stage-prefs", currentFarmId, cropId],
    queryFn: () =>
      apiGet<StagePrefs>(`/v1/farms/${currentFarmId}/stage-prefs?crop_id=${cropId}`),
    enabled: currentFarmId !== null && cropId !== null,
  })
  const stagesQuery = useQuery({
    queryKey: ["block-stages", blockId, year],
    queryFn: () => readBlockStages(blockId ?? "", year ?? 0),
    enabled: blockId !== undefined && year !== null,
  })
  return {
    farmId: currentFarmId,
    farmQuery,
    blockQuery,
    today,
    year,
    cropId,
    catalogQuery,
    varietiesQuery,
    settingsQuery,
    prefsQuery,
    stagesQuery,
  }
}
