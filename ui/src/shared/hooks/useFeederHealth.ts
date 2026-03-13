// ---------------------------------------------------------------------------
// TanStack Query hook for GET /feeder/health.
// Lightweight with short stale time for compact trust signal.
//
// Cache key convention (PR-UI-3): exported named constant, explicit return
// type, stale time documented.
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { fetchFeederHealth, type FeederHealth } from "@shared/api/feeder";

/** Cache key for feeder health query. */
export const FEEDER_HEALTH_KEY = ["feeder", "health"] as const;

export function useFeederHealth(): UseQueryResult<FeederHealth, Error> {
  return useQuery<FeederHealth, Error>({
    queryKey: FEEDER_HEALTH_KEY,
    queryFn: async () => {
      const result = await fetchFeederHealth();
      if (!result.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : result.detail.message ?? `Feeder health failed (${result.status})`,
        );
      }
      return result.data;
    },
    staleTime: 15_000,       // 15s — feeder freshness should be responsive
    refetchInterval: 60_000, // background refresh every 60s
  });
}
