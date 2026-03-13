// ---------------------------------------------------------------------------
// TanStack Query hook for GET /watchlist/triage.
// Supports manual refetch via the returned refetch handle.
// ---------------------------------------------------------------------------

import { useQuery } from "@tanstack/react-query";
import {
  fetchWatchlistTriage,
  type WatchlistTriageResponse,
} from "@shared/api/triage";

export const TRIAGE_QUERY_KEY = ["watchlist", "triage"] as const;

export function useWatchlistTriage() {
  return useQuery<WatchlistTriageResponse>({
    queryKey: TRIAGE_QUERY_KEY,
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
  });
}
