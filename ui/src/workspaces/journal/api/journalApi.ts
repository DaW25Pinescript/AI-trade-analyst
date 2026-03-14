// ---------------------------------------------------------------------------
// Journal & Review API layer — PR-UI-6.
//
// Typed fetch for GET /journal/decisions and GET /review/records.
// Uses the shared apiFetch wrapper. Both endpoints use the graceful
// empty/unavailable pattern (UI_CONTRACT §11.4): empty records array
// is valid success, not error.
// ---------------------------------------------------------------------------

import { apiFetch, type ApiResult } from "@shared/api/client";

// ---- Domain types (UI_CONTRACT §9.7, §9.8) ----

/** Immutable stored decision record (UI_CONTRACT §9.7). */
export interface DecisionSnapshot {
  snapshot_id: string;
  instrument: string;
  saved_at: string;
  journey_status: string;
  verdict: string;
  user_decision: string | null;
}

/** Decision record with result linkage (UI_CONTRACT §9.8). Extends DecisionSnapshot. */
export interface ReviewRecord extends DecisionSnapshot {
  has_result: boolean;
}

/** Response shape for GET /journal/decisions. */
export interface JournalDecisionsResponse {
  records: DecisionSnapshot[];
}

/** Response shape for GET /review/records. */
export interface ReviewRecordsResponse {
  records: ReviewRecord[];
}

// ---- API functions ----

/** Fetch frozen decision summaries. */
export function fetchDecisions(): Promise<ApiResult<JournalDecisionsResponse>> {
  return apiFetch<JournalDecisionsResponse>("/journal/decisions");
}

/** Fetch decisions with result linkage. */
export function fetchReviewRecords(): Promise<ApiResult<ReviewRecordsResponse>> {
  return apiFetch<ReviewRecordsResponse>("/review/records");
}
