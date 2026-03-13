// ---------------------------------------------------------------------------
// Typed triage endpoint clients — shapes from UI_CONTRACT.md §9.5.
// These functions are compiled and exported for use in PR-UI-2.
// They are NOT consumed in the UI yet.
// ---------------------------------------------------------------------------

import { apiFetch, type ApiResult } from "./client";

// ---- Domain types (§9.5) ----

export interface TriageItem {
  symbol: string;
  triage_status?: string;
  bias?: string;
  confidence?: number;
  why_interesting?: string;
  rationale?: string;
  verdict_at?: string;
}

export interface WatchlistTriageResponse {
  data_state: string;
  generated_at?: string;
  items: TriageItem[];
}

export interface TriggerTriageResponse {
  status: string;
  artifacts_written?: number;
  symbols_processed?: number;
  output_dir?: string;
}

// ---- Endpoint functions ----

/** Fetch the current watchlist triage results. */
export function fetchWatchlistTriage(): Promise<
  ApiResult<WatchlistTriageResponse>
> {
  return apiFetch<WatchlistTriageResponse>("/watchlist/triage");
}

/** Trigger a new triage run, optionally for specific symbols. */
export function triggerTriage(
  symbols?: string[],
): Promise<ApiResult<TriggerTriageResponse>> {
  return apiFetch<TriggerTriageResponse>("/triage", {
    method: "POST",
    body: symbols ? JSON.stringify({ symbols }) : undefined,
  });
}
