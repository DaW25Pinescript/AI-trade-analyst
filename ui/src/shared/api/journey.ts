// ---------------------------------------------------------------------------
// Typed journey endpoint clients — shapes from UI_CONTRACT.md §9.6, §10.3.
//
// Endpoints used:
//   GET  /journey/{asset}/bootstrap — preloaded evidence/context
//   POST /journey/draft             — mutable draft save
//   POST /journey/decision          — immutable freeze (409 on duplicate)
//   POST /journey/result            — result linked to decision
// ---------------------------------------------------------------------------

import { apiFetch, type ApiResult } from "./client";

// ---- Bootstrap types (§9.6) ----

export interface AnalystVerdict {
  verdict: string;
  confidence: string;
}

export interface ArbiterDecision {
  final_bias?: string;
  decision?: string;
  overall_confidence?: number;
  analyst_agreement_pct?: number;
  risk_override_applied?: boolean;
  arbiter_notes?: string;
  no_trade_conditions?: string[];
  approved_setups?: ApprovedSetup[];
}

export interface ApprovedSetup {
  type: string;
  entry_zone: string;
  stop: string;
  targets: string[];
  rr_estimate: number;
  confidence: number;
}

export interface BootstrapExplanation {
  [key: string]: unknown;
}

export interface StructureDigest {
  [key: string]: unknown;
}

export interface JourneyBootstrapResponse {
  data_state: "live" | "stale" | "unavailable" | "partial" | string;
  instrument: string;
  generated_at: string | null;
  structure_digest: StructureDigest;
  analyst_verdict: AnalystVerdict;
  arbiter_decision: ArbiterDecision;
  explanation: BootstrapExplanation;
  reasoning_summary: string | null;
}

// ---- Write envelope types (§11.2) ----

export interface JourneyWriteSuccess {
  success: true;
  journey_id?: string;
  snapshot_id?: string;
  saved_at: string;
  path: string;
}

export interface JourneyWriteError {
  success: false;
  error: string;
}

// ---- Draft types ----

export interface JourneyDraftPayload {
  journey_id?: string;
  instrument: string;
  stage: string;
  notes: string;
  thesis: string;
  conviction: string;
  [key: string]: unknown;
}

// ---- Decision types ----

export interface JourneyDecisionPayload {
  snapshot_id: string;
  instrument: string;
  decision: string;
  thesis: string;
  conviction: string;
  notes: string;
  bootstrap_summary: Record<string, unknown>;
}

// ---- Result types ----

export interface JourneyResultPayload {
  snapshot_id: string;
  instrument: string;
  outcome: string;
  notes: string;
  [key: string]: unknown;
}

// ---- Endpoint functions ----

/** Fetch bootstrap context for a journey asset. */
export function fetchJourneyBootstrap(
  asset: string,
): Promise<ApiResult<JourneyBootstrapResponse>> {
  return apiFetch<JourneyBootstrapResponse>(
    `/journey/${encodeURIComponent(asset)}/bootstrap`,
  );
}

/** Save a mutable journey draft. */
export function saveJourneyDraft(
  payload: JourneyDraftPayload,
): Promise<ApiResult<JourneyWriteSuccess>> {
  return apiFetch<JourneyWriteSuccess>("/journey/draft", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Freeze an immutable decision snapshot. Returns 409 on duplicate. */
export function saveJourneyDecision(
  payload: JourneyDecisionPayload,
): Promise<ApiResult<JourneyWriteSuccess>> {
  return apiFetch<JourneyWriteSuccess>("/journey/decision", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Save a result linked to a frozen decision snapshot. */
export function saveJourneyResult(
  payload: JourneyResultPayload,
): Promise<ApiResult<JourneyWriteSuccess>> {
  return apiFetch<JourneyWriteSuccess>("/journey/result", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
