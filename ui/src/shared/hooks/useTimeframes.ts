// ---------------------------------------------------------------------------
// TanStack Query hook for GET /market-data/{instrument}/timeframes (PR-CHART-2).
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchTimeframes,
  type TimeframesResponse,
} from "@shared/api/marketData";
import { parseOpsErrorEnvelope } from "@shared/api/ops";

/** Cache key factory for timeframe discovery queries. */
export const timeframesKey = (instrument: string) =>
  ["market-data", "timeframes", instrument] as const;

export const TIMEFRAMES_KEY = "timeframes";

export function useTimeframes(
  instrument: string | null,
): UseQueryResult<TimeframesResponse, Error> {
  return useQuery<TimeframesResponse, Error>({
    queryKey: timeframesKey(instrument ?? ""),
    queryFn: async () => {
      const result = await fetchTimeframes(instrument!);
      if (!result.ok) {
        const opsError = parseOpsErrorEnvelope(result.detail);
        throw new Error(
          opsError
            ? opsError.message
            : typeof result.detail === "string"
              ? result.detail
              : `Timeframe discovery failed (${result.status})`,
        );
      }
      const data = result.data;
      // Validate response shape defensively
      if (
        !data ||
        typeof data.instrument !== "string" ||
        !Array.isArray(data.available_timeframes)
      ) {
        throw new Error("Malformed timeframe discovery response");
      }
      return data;
    },
    enabled: instrument != null,
    staleTime: 60_000,
  });
}
