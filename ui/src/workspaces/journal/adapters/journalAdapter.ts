// ---------------------------------------------------------------------------
// Journal & Review view-model adapter — PR-UI-6.
//
// Maps backend responses to view models. ReviewRecord extends
// DecisionSnapshot (shared type with has_result added, not a separate
// incompatible model). Derives empty vs populated state, header
// summaries, and per-record result indicators.
// ---------------------------------------------------------------------------

import type {
  DecisionSnapshot,
  ReviewRecord,
  JournalDecisionsResponse,
  ReviewRecordsResponse,
} from "../api/journalApi";

// Re-export domain types for adapter consumers
export type { DecisionSnapshot, ReviewRecord };

// ---- View condition ----

export type JournalCondition =
  | "loading"
  | "ready"
  | "empty"
  | "error";

// ---- View models ----

export interface DecisionRowViewModel {
  snapshotId: string;
  instrument: string;
  savedAt: string;
  journeyStatus: string;
  verdict: string;
  userDecision: string | null;
  journeyLink: string;
}

export interface ReviewRowViewModel extends DecisionRowViewModel {
  hasResult: boolean;
  resultIndicator: "has-result" | "needs-follow-up";
}

export interface JournalHeaderSummary {
  text: string;
}

export interface JournalViewModel {
  condition: JournalCondition;
  rows: DecisionRowViewModel[];
  header: JournalHeaderSummary;
}

export interface ReviewViewModel {
  condition: JournalCondition;
  rows: ReviewRowViewModel[];
  header: JournalHeaderSummary;
  outcomeCoverage: OutcomeCoverage;
}

export interface OutcomeCoverage {
  withResults: number;
  total: number;
  text: string;
}

// ---- Mapping functions ----

/** Map a DecisionSnapshot to a row view model. */
export function mapDecisionRow(record: DecisionSnapshot): DecisionRowViewModel {
  return {
    snapshotId: record.snapshot_id,
    instrument: record.instrument,
    savedAt: record.saved_at,
    journeyStatus: record.journey_status ?? "unknown",
    verdict: record.verdict ?? "",
    userDecision: record.user_decision ?? null,
    journeyLink: `/journey/${encodeURIComponent(record.instrument)}`,
  };
}

/** Map a ReviewRecord to a review row view model. */
export function mapReviewRow(record: ReviewRecord): ReviewRowViewModel {
  return {
    ...mapDecisionRow(record),
    hasResult: record.has_result,
    resultIndicator: record.has_result ? "has-result" : "needs-follow-up",
  };
}

/** Derive the journal header summary. */
export function deriveJournalHeader(count: number): JournalHeaderSummary {
  if (count === 0) return { text: "No frozen decisions" };
  if (count === 1) return { text: "1 frozen decision" };
  return { text: `${count} frozen decisions` };
}

/** Derive outcome coverage from review records. */
export function deriveOutcomeCoverage(records: ReviewRecord[]): OutcomeCoverage {
  const total = records.length;
  const withResults = records.filter((r) => r.has_result).length;
  const text =
    total === 0
      ? "No decisions to review"
      : `${withResults} of ${total} decisions have results`;
  return { withResults, total, text };
}

/** Derive the review header summary from outcome coverage. */
export function deriveReviewHeader(coverage: OutcomeCoverage): JournalHeaderSummary {
  return { text: coverage.text };
}

// ---- Builder functions ----

/** Build the Journal view model from API response + query state. */
export function buildJournalViewModel(
  data: JournalDecisionsResponse | null,
  isLoading: boolean,
  isError: boolean,
): JournalViewModel {
  if (isLoading) {
    return {
      condition: "loading",
      rows: [],
      header: { text: "" },
    };
  }

  if (isError || !data) {
    return {
      condition: "error",
      rows: [],
      header: { text: "" },
    };
  }

  const rows = data.records.map(mapDecisionRow);

  return {
    condition: rows.length === 0 ? "empty" : "ready",
    rows,
    header: deriveJournalHeader(rows.length),
  };
}

/** Build the Review view model from API response + query state. */
export function buildReviewViewModel(
  data: ReviewRecordsResponse | null,
  isLoading: boolean,
  isError: boolean,
): ReviewViewModel {
  if (isLoading) {
    return {
      condition: "loading",
      rows: [],
      header: { text: "" },
      outcomeCoverage: { withResults: 0, total: 0, text: "" },
    };
  }

  if (isError || !data) {
    return {
      condition: "error",
      rows: [],
      header: { text: "" },
      outcomeCoverage: { withResults: 0, total: 0, text: "" },
    };
  }

  const rows = data.records.map(mapReviewRow);
  const outcomeCoverage = deriveOutcomeCoverage(data.records);

  return {
    condition: rows.length === 0 ? "empty" : "ready",
    rows,
    header: deriveReviewHeader(outcomeCoverage),
    outcomeCoverage,
  };
}
