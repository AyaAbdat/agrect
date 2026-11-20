import { ApiError, apiGet } from "../../lib/api"
import type { BlockStages } from "./types"

export async function readBlockStages(blockId: string, year: number): Promise<BlockStages | null> {
  try {
    return await apiGet<BlockStages>(`/v1/blocks/${blockId}/stages?year=${year}`)
  } catch (error) {
    if (error instanceof ApiError && error.code === "phenology.season_not_found") return null
    throw error
  }
}
