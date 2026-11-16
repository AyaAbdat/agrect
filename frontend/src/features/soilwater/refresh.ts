import type { QueryClient } from "@tanstack/react-query"

export async function refreshWater(
  queryClient: QueryClient,
  blockId: string,
  farmId: string | null,
): Promise<void> {
  const tasks = [
    queryClient.invalidateQueries({ queryKey: ["irrigation-events", blockId] }),
    queryClient.invalidateQueries({ queryKey: ["water-balance", blockId] }),
    queryClient.invalidateQueries({ queryKey: ["irrigation-today", blockId] }),
    queryClient.invalidateQueries({ queryKey: ["soil", blockId] }),
  ]
  if (farmId !== null) {
    tasks.push(
      queryClient.invalidateQueries({ queryKey: ["irrigation-today", "farm", farmId] }),
    )
  }
  await Promise.all(tasks)
}
