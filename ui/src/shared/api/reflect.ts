// ---------------------------------------------------------------------------
// Reflect endpoint clients — shapes from PR_REFLECT_2_SPEC.md.
// Three read-only endpoints consuming PR-REFLECT-1 backend.
// ---------------------------------------------------------------------------

import { apiFetch, type ApiResult } from "./client";
import type { ResponseMeta } from "./ops";

// ---- Persona Performance types ----

export type PersonaStats = {
  persona: string;
  participation_count: number;
  skip_count: number;
  fail_count: number;
  participation_rate: number;
  override_count: number;
  override_rate: number | null;
  stance_alignment: number | null;
  avg_confidence: number | null;
  flagged: boolean;
};

export type ScanBounds = {
  max_runs: number;
  inspected_dirs: number;
  valid_runs: number;
  skipped_runs: number;
};

export type PersonaPerformanceResponse = ResponseMeta & {
  threshold: number;
  threshold_met: boolean;
  scan_bounds: ScanBounds;
  stats: PersonaStats[];
};

// ---- Pattern Summary types ----

export type VerdictCount = {
  verdict: string;
  count: number;
};

export type PatternBucket = {
  instrument: string;
  session: string;
  run_count: number;
  threshold_met: boolean;
  verdict_distribution: VerdictCount[];
  no_trade_rate: number | null;
  flagged: boolean;
};

export type PatternSummaryResponse = ResponseMeta & {
  threshold: number;
  scan_bounds: ScanBounds;
  buckets: PatternBucket[];
};

// ---- Run Bundle types ----

export type ArtifactState = "present" | "missing" | "malformed";

export type ArtifactStatus = {
  run_record: ArtifactState;
  usage_jsonl: ArtifactState;
  usage_json: ArtifactState;
};

export type RunBundleResponse = ResponseMeta & {
  run_id: string;
  artifact_status: ArtifactStatus;
  run_record: Record<string, unknown>;
  usage_summary: Record<string, unknown> | null;
  usage_jsonl: Record<string, unknown>[];
};

// ---- Fetch params ----

export type FetchPersonaPerformanceParams = {
  maxRuns?: number;
};

export type FetchPatternSummaryParams = {
  maxRuns?: number;
};

// ---- Endpoint functions ----

export function fetchPersonaPerformance(
  params: FetchPersonaPerformanceParams = {},
): Promise<ApiResult<PersonaPerformanceResponse>> {
  const searchParams = new URLSearchParams();
  if (params.maxRuns != null)
    searchParams.set("max_runs", String(params.maxRuns));
  const query = searchParams.toString();
  const path = query
    ? `/reflect/persona-performance?${query}`
    : "/reflect/persona-performance";
  return apiFetch<PersonaPerformanceResponse>(path);
}

export function fetchPatternSummary(
  params: FetchPatternSummaryParams = {},
): Promise<ApiResult<PatternSummaryResponse>> {
  const searchParams = new URLSearchParams();
  if (params.maxRuns != null)
    searchParams.set("max_runs", String(params.maxRuns));
  const query = searchParams.toString();
  const path = query
    ? `/reflect/pattern-summary?${query}`
    : "/reflect/pattern-summary";
  return apiFetch<PatternSummaryResponse>(path);
}

export function fetchRunBundle(
  runId: string,
): Promise<ApiResult<RunBundleResponse>> {
  return apiFetch<RunBundleResponse>(`/reflect/run/${encodeURIComponent(runId)}`);
}
