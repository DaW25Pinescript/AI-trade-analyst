// ---------------------------------------------------------------------------
// TanStack Query hook for GET /journey/{asset}/bootstrap.
//
// Cache key convention (PR-UI-3): exported named constant, explicit return
// type, stale time documented.
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchJourneyBootstrap,
  type JourneyBootstrapResponse,
} from "@shared/api/journey";

/** Cache key factory for journey bootstrap query. */
export const JOURNEY_BOOTSTRAP_KEY = (asset: string) =>
  ["journey", "bootstrap", asset] as const;

export function useJourneyBootstrap(
  asset: string | undefined,
): UseQueryResult<JourneyBootstrapResponse, Error> {
  return useQuery<JourneyBootstrapResponse, Error>({
    queryKey: JOURNEY_BOOTSTRAP_KEY(asset ?? ""),
    queryFn: async () => {
      if (!asset) {
        throw new Error("No asset specified");
      }
      const result = await fetchJourneyBootstrap(asset);
      if (!result.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : result.detail.message ?? `Request failed (${result.status})`,
        );
      }
      return result.data;
    },
    enabled: !!asset,
    // Bootstrap data is analysis-time context — 60s stale is reasonable
    staleTime: 60_000,
  });
}
