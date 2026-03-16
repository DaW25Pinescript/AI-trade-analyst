// ---------------------------------------------------------------------------
// TanStack Query hook for GET /market-data/{instrument}/ohlcv (PR-CHART-1).
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchOHLCV,
  type OHLCVResponse,
} from "@shared/api/marketData";
import { parseOpsErrorEnvelope } from "@shared/api/ops";

/** Cache key factory for market data queries. */
export const marketDataKey = (instrument: string, timeframe?: string) =>
  ["market-data", "ohlcv", instrument, timeframe ?? "4h"] as const;

export const MARKET_DATA_KEY = "market-data";

export function useMarketData(params: {
  instrument: string | null;
  timeframe?: string;
  limit?: number;
}): UseQueryResult<OHLCVResponse, Error> {
  return useQuery<OHLCVResponse, Error>({
    queryKey: marketDataKey(params.instrument ?? "", params.timeframe),
    queryFn: async () => {
      const result = await fetchOHLCV({
        instrument: params.instrument!,
        timeframe: params.timeframe,
        limit: params.limit,
      });
      if (!result.ok) {
        const opsError = parseOpsErrorEnvelope(result.detail);
        throw new Error(
          opsError
            ? opsError.message
            : typeof result.detail === "string"
              ? result.detail
              : `Market data fetch failed (${result.status})`,
        );
      }
      return result.data;
    },
    enabled: params.instrument != null,
    staleTime: 60_000,
  });
}
