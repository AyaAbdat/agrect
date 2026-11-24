import { useQuery } from "@tanstack/react-query"
import { useAuth } from "../../app/auth"
import { apiGet } from "../../lib/api"
import { farmToday, shiftIsoDate } from "../weather/format"
import type { BalanceRow, FarmClock, IrrigationToday, WaterBalance } from "./types"

const LOOKBACK_DAYS = 30

export function waterLeftFrom(today: string): string {
  return shiftIsoDate(today, -LOOKBACK_DAYS)
}

/** Latest balance row on or before `today`. Forecast rows after today are ignored. */
export function waterLeftNow(rows: BalanceRow[], today: string): BalanceRow | undefined {
  return rows.reduce<BalanceRow | undefined>((latest, row) => {
    if (row.date > today) return latest
    if (latest === undefined || row.date > latest.date) return row
    return latest
  }, undefined)
}

export function useWaterLeftNow(blockId: string | undefined) {
  const { currentFarmId } = useAuth()
  const farmQuery = useQuery({
    queryKey: ["farm", currentFarmId],
    queryFn: () => apiGet<FarmClock>(`/v1/farms/${currentFarmId}`),
    enabled: currentFarmId !== null,
  })
  const today = farmQuery.data === undefined ? null : farmToday(farmQuery.data.timezone)
  const adviceQuery = useQuery({
    queryKey: ["irrigation-today", blockId],
    queryFn: () => apiGet<IrrigationToday>(`/v1/blocks/${blockId}/irrigation-today`),
    enabled: blockId !== undefined,
  })
  const balanceQuery = useQuery({
    queryKey: ["water-balance", blockId, today],
    queryFn: () =>
      apiGet<WaterBalance>(
        `/v1/blocks/${blockId}/water-balance?from=${waterLeftFrom(today ?? "")}`,
      ),
    enabled: blockId !== undefined && today !== null,
  })
  const anchor = adviceQuery.data?.date
  const row =
    balanceQuery.data === undefined || anchor === undefined
      ? undefined
      : waterLeftNow(balanceQuery.data.rows, anchor)
  const pending =
    farmQuery.isLoading || adviceQuery.isLoading || (today !== null && balanceQuery.isLoading)
  const failed = farmQuery.isError || adviceQuery.isError || balanceQuery.isError
  function refetch() {
    void farmQuery.refetch()
    void adviceQuery.refetch()
    void balanceQuery.refetch()
  }
  return { row, balanceQuery, today, pending, failed, refetch }
}
