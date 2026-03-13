// ---------------------------------------------------------------------------
// TanStack Query hook for GET /watchlist/triage.
// Supports manual refetch via the returned refetch handle.
//
// Cache key convention (PR-UI-3): exported named constant, explicit return
// type, stale time documented.
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchWatchlistTriage,
  type WatchlistTriageResponse,
} from "@shared/api/triage";

/** Cache key for watchlist triage query. */
export const WATCHLIST_TRIAGE_KEY = ["watchlist", "triage"] as const;

export function useWatchlistTriage(): UseQueryResult<WatchlistTriageResponse, Error> {
  return useQuery<WatchlistTriageResponse, Error>({
    queryKey: WATCHLIST_TRIAGE_KEY,
    queryFn: async () => {
      const result = await fetchWatchlistTriage();
      if (!result.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : result.detail.message ?? `Request failed (${result.status})`,
        );
      }
      return result.data;
    },
    // Uses QueryClient default staleTime (30s) — triage data is not latency-critical
  });
}
