// ---------------------------------------------------------------------------
// Feeder health endpoint client — shapes from UI_CONTRACT.md §9.9.
// ---------------------------------------------------------------------------

import { apiFetch, type ApiResult } from "./client";

// ---- Domain types (§9.9) ----

export interface FeederHealth {
  status: string;
  ingested_at: string;
  age_seconds: number;
  stale: boolean;
  source_health: Record<string, unknown>;
  regime?: string;
  vol_bias?: string;
  confidence?: string;
}

// ---- Endpoint function ----

/** Fetch the current feeder health snapshot. */
export function fetchFeederHealth(): Promise<ApiResult<FeederHealth>> {
  return apiFetch<FeederHealth>("/feeder/health");
}
