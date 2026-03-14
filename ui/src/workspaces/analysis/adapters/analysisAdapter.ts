// ---------------------------------------------------------------------------
// Analysis Adapter — translates backend responses to UI view models.
//
// Responsibilities:
//   - normalizeAnalysisResponse() → Analysis view model
//   - normalizeVerdict() → Verdict view model (expert density, all fields)
//   - normalizeUsageSummary() → Usage view model (tolerates empty-but-valid)
//   - normalizeError() → stable error display model with preserved identifiers
//   - derive tab enablement, submission read-only state, usage availability
// ---------------------------------------------------------------------------

import type { ApiErrorDetail } from "@shared/api/client";
import type {
  AnalysisResponse,
  FinalVerdict,
  ApprovedSetup,
  TicketDraft,
  UsageSummary,
} from "../types";
import type { RunLifecycleState, CompletionModifier } from "../state/runLifecycle";

// ---- View models ----

export interface VerdictViewModel {
  finalBias: string;
  decision: string;
  approvedSetups: ApprovedSetup[];
  noTradeConditions: string[];
  overallConfidence: number;
  analystAgreementPct: number;
  arbiterNotes: string;
  riskOverrideApplied: boolean;
  overlayProvided: boolean;
  indicatorDependent: boolean;
  indicatorDependencyNotes: string | null;
}

export interface UsageViewModel {
  available: boolean;
  artifactMissing: boolean;
  loading: boolean;
  totalTokens: number | null;
  totalCost: number | null;
  promptTokens: number | null;
  completionTokens: number | null;
  totalCalls: number | null;
  successfulCalls: number | null;
  failedCalls: number | null;
  modelBreakdown: Record<string, number> | null;
}

export interface ErrorViewModel {
  message: string;
  code: string | null;
  runId: string | null;
  requestId: string | null;
}

export interface AnalysisViewModel {
  runId: string | null;
  verdict: VerdictViewModel | null;
  ticketDraft: TicketDraft | null;
  sourceTicketId: string | null;
}

// ---- Tab enablement ----

export interface TabState {
  submissionEnabled: boolean;
  submissionReadOnly: boolean;
  executionEnabled: boolean;
  verdictEnabled: boolean;
  verdictDisabledReason: string | null;
}

export function deriveTabState(lifecycle: RunLifecycleState): TabState {
  const { state } = lifecycle;

  const isPostSubmit =
    state === "running" ||
    state === "completed" ||
    state === "failed";

  return {
    submissionEnabled: true,
    submissionReadOnly: isPostSubmit || state === "submitting",
    executionEnabled: true,
    verdictEnabled: state === "completed",
    verdictDisabledReason:
      state === "failed"
        ? "No verdict — run failed"
        : state !== "completed"
          ? "Submit to see verdict"
          : null,
  };
}

// ---- Usage availability ----

export type UsageAvailability = "ready" | "loading" | "artifact-missing";

export function deriveUsageAvailability(
  lifecycle: RunLifecycleState,
  usageLoading: boolean,
  usageLoaded: boolean,
): UsageAvailability {
  if (lifecycle.state !== "completed") return "artifact-missing";
  if (usageLoading) return "loading";
  if (!usageLoaded) return "artifact-missing";
  return "ready";
}

// ---- Normalizers ----

export function normalizeAnalysisResponse(
  response: AnalysisResponse,
): AnalysisViewModel {
  return {
    runId: response.run_id,
    verdict: normalizeVerdict(response.verdict),
    ticketDraft: response.ticket_draft ?? null,
    sourceTicketId: response.source_ticket_id ?? null,
  };
}

export function normalizeVerdict(verdict: FinalVerdict): VerdictViewModel {
  return {
    finalBias: verdict.final_bias ?? "unknown",
    decision: verdict.decision ?? "UNKNOWN",
    approvedSetups: verdict.approved_setups ?? [],
    noTradeConditions: verdict.no_trade_conditions ?? [],
    overallConfidence: verdict.overall_confidence ?? 0,
    analystAgreementPct: verdict.analyst_agreement_pct ?? 0,
    arbiterNotes: verdict.arbiter_notes ?? "",
    riskOverrideApplied: verdict.risk_override_applied ?? false,
    overlayProvided: verdict.overlay_was_provided ?? false,
    indicatorDependent: verdict.indicator_dependent ?? false,
    indicatorDependencyNotes: verdict.indicator_dependency_notes ?? null,
  };
}

export function normalizeUsageSummary(
  summary: UsageSummary | null | undefined,
  loading: boolean = false,
): UsageViewModel {
  if (!summary) {
    return {
      available: false,
      artifactMissing: !loading,
      loading,
      totalTokens: null,
      totalCost: null,
      promptTokens: null,
      completionTokens: null,
      totalCalls: null,
      successfulCalls: null,
      failedCalls: null,
      modelBreakdown: null,
    };
  }

  return {
    available: true,
    artifactMissing: false,
    loading: false,
    totalTokens: summary.tokens?.total_tokens ?? null,
    totalCost: summary.total_cost_usd ?? null,
    promptTokens: summary.tokens?.prompt_tokens ?? null,
    completionTokens: summary.tokens?.completion_tokens ?? null,
    totalCalls: summary.total_calls ?? null,
    successfulCalls: summary.successful_calls ?? null,
    failedCalls: summary.failed_calls ?? null,
    modelBreakdown: summary.calls_by_model ?? null,
  };
}

/**
 * Normalize mixed detail error shapes (UI_CONTRACT §11.1).
 * Handles both string detail and structured object detail.
 * Preserves run_id / request_id from error payloads.
 */
export function normalizeError(
  detail: string | ApiErrorDetail,
): ErrorViewModel {
  if (typeof detail === "string") {
    return {
      message: detail,
      code: null,
      runId: null,
      requestId: null,
    };
  }

  return {
    message: detail.message ?? "Analysis failed",
    code: detail.code ?? null,
    runId: detail.run_id ?? null,
    requestId: detail.request_id ?? null,
  };
}

// ---- Form data builder ----

/**
 * Build a FormData object for POST /analyse from the submission model.
 * Uses exact field names from the backend FastAPI route.
 */
export function buildFormData(submission: {
  instrument: string;
  session: string;
  timeframes: string[];
  account_balance: number;
  min_rr: number;
  max_risk_per_trade: number;
  max_daily_risk: number;
  no_trade_windows: string[];
  market_regime: string;
  news_risk: string;
  open_positions: string[];
  lens_ict_icc: boolean;
  lens_market_structure: boolean;
  lens_orderflow: boolean;
  lens_trendlines: boolean;
  lens_classical: boolean;
  lens_harmonic: boolean;
  lens_smt: boolean;
  lens_volume_profile: boolean;
  charts: Record<string, File>;
  source_ticket_id?: string;
  enable_deliberation: boolean;
  triage_mode: boolean;
  smoke_mode: boolean;
}): FormData {
  const fd = new FormData();

  // Market identity
  fd.append("instrument", submission.instrument);
  fd.append("session", submission.session);
  fd.append("timeframes", JSON.stringify(submission.timeframes));

  // Account / risk
  fd.append("account_balance", String(submission.account_balance));
  fd.append("min_rr", String(submission.min_rr));
  fd.append("max_risk_per_trade", String(submission.max_risk_per_trade));
  fd.append("max_daily_risk", String(submission.max_daily_risk));
  fd.append("no_trade_windows", JSON.stringify(submission.no_trade_windows));

  // Market context
  fd.append("market_regime", submission.market_regime);
  fd.append("news_risk", submission.news_risk);
  fd.append("open_positions", JSON.stringify(submission.open_positions));

  // Lens flags
  fd.append("lens_ict_icc", String(submission.lens_ict_icc));
  fd.append("lens_market_structure", String(submission.lens_market_structure));
  fd.append("lens_orderflow", String(submission.lens_orderflow));
  fd.append("lens_trendlines", String(submission.lens_trendlines));
  fd.append("lens_classical", String(submission.lens_classical));
  fd.append("lens_harmonic", String(submission.lens_harmonic));
  fd.append("lens_smt", String(submission.lens_smt));
  fd.append("lens_volume_profile", String(submission.lens_volume_profile));

  // Chart files — exact field names: chart_h4, chart_h1, chart_m15, chart_m5
  for (const [key, file] of Object.entries(submission.charts)) {
    fd.append(key, file);
  }

  // Optional flags
  if (submission.source_ticket_id) {
    fd.append("source_ticket_id", submission.source_ticket_id);
  }
  fd.append("enable_deliberation", String(submission.enable_deliberation));
  fd.append("triage_mode", String(submission.triage_mode));
  fd.append("smoke_mode", String(submission.smoke_mode));

  return fd;
}

// ---- Modifier derivation ----

export function deriveModifier(
  usageAvailability: UsageAvailability,
): CompletionModifier {
  if (usageAvailability === "artifact-missing") return "artifact-missing";
  return null;
}
