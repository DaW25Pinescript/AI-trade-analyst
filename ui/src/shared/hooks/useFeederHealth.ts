// ---------------------------------------------------------------------------
// TanStack Query hook for GET /feeder/health.
// Lightweight with short stale time for compact trust signal.
// ---------------------------------------------------------------------------

import { useQuery } from "@tanstack/react-query";
import { fetchFeederHealth, type FeederHealth } from "@shared/api/feeder";

export const FEEDER_HEALTH_QUERY_KEY = ["feeder", "health"] as const;

export function useFeederHealth() {
  return useQuery<FeederHealth>({
    queryKey: FEEDER_HEALTH_QUERY_KEY,
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
    staleTime: 15_000, // 15 seconds — feeder freshness should be responsive
    refetchInterval: 60_000, // background refresh every 60s
  });
}
