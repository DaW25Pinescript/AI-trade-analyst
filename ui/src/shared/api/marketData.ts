// ---------------------------------------------------------------------------
// Market Data endpoint client — shapes from PR_CHART_1_SPEC.md §6.2.
// ---------------------------------------------------------------------------

import { apiFetch, type ApiResult } from "./client";
import type { ResponseMeta } from "./ops";

// ---- Market Data types ----

export type Candle = {
  timestamp: number; // Unix epoch seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type OHLCVResponse = ResponseMeta & {
  instrument: string;
  timeframe: string;
  candles: Candle[];
  candle_count: number;
};

// ---- Endpoint function ----

export type FetchOHLCVParams = {
  instrument: string;
  timeframe?: string;
  limit?: number;
};

/** Fetch OHLCV candle data for a given instrument and timeframe. */
export function fetchOHLCV(
  params: FetchOHLCVParams,
): Promise<ApiResult<OHLCVResponse>> {
  const searchParams = new URLSearchParams();

  if (params.timeframe) searchParams.set("timeframe", params.timeframe);
  if (params.limit != null) searchParams.set("limit", String(params.limit));

  const query = searchParams.toString();
  const path = `/market-data/${encodeURIComponent(params.instrument)}/ohlcv${query ? `?${query}` : ""}`;

  return apiFetch<OHLCVResponse>(path);
}
