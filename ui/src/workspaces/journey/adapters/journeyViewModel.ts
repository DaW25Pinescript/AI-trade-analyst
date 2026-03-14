// ---------------------------------------------------------------------------
// View-model adapter for Journey Studio workspace.
//
// Maps backend bootstrap payloads to journey view models.
// Derives:
//   - workspace condition (loading/ready/empty/unavailable/stale/error)
//   - staged flow state (explore → draft → frozen → result)
//   - right rail panel visibility from field presence
//   - freeze/unfreeze state and Save Result enablement
//   - honest handling for missing/null values
//
// Stages are a UI concept — NOT a backend entity. No stage state is POSTed.
// ---------------------------------------------------------------------------

import type {
  JourneyBootstrapResponse,
  ArbiterDecision,
  AnalystVerdict,
  ApprovedSetup,
} from "@shared/api/journey";

// ---- Workspace condition ----

export type JourneyCondition =
  | "loading"
  | "ready"
  | "empty"
  | "stale"
  | "unavailable"
  | "partial"
  | "error";

// ---- Journey stage (UI-only concept) ----

export type JourneyStage =
  | "explore"    // reading bootstrap, forming thesis
  | "draft"      // thesis captured, can save draft
  | "frozen"     // decision frozen (immutable)
  | "result";    // result captured post-freeze

// ---- Right rail panel visibility ----

export interface RightRailPanels {
  showArbiterSummary: boolean;
  showExplanation: boolean;
  showSetups: boolean;
  showNoTradeWarning: boolean;
  allUnavailable: boolean;
}

// ---- Approved setup view model ----

export interface SetupViewModel {
  type: string;
  entryZone: string;
  stop: string;
  targets: string[];
  rrEstimate: number;
  confidence: number;
}

// ---- Full workspace view model ----

export interface JourneyWorkspaceViewModel {
  condition: JourneyCondition;
  dataState: string | null;
  instrument: string;
  generatedAt: string | null;

  // Bootstrap-derived context
  analystVerdict: string | null;
  analystConfidence: string | null;
  arbiterBias: string | null;
  arbiterDecision: string | null;
  arbiterConfidence: number | null;
  arbiterNotes: string | null;
  analystAgreement: number | null;
  riskOverride: boolean;
  noTradeConditions: string[];
  approvedSetups: SetupViewModel[];
  reasoningSummary: string | null;

  // Right rail
  rightRail: RightRailPanels;

  // Stage flow (UI state, not backend)
  stage: JourneyStage;
  isFrozen: boolean;
  frozenSnapshotId: string | null;
  canSaveDraft: boolean;
  canFreeze: boolean;
  canSaveResult: boolean;

  // Draft form state
  draftJourneyId: string | null;
  thesis: string;
  conviction: string;
  notes: string;
  userDecision: string;
}

// ---- Mapping functions ----

/** Resolve workspace condition from bootstrap data and query state. */
export function resolveJourneyCondition(
  data: JourneyBootstrapResponse | null,
  isLoading: boolean,
  isError: boolean,
): JourneyCondition {
  if (isLoading) return "loading";
  if (isError || !data) return "error";

  const ds = data.data_state?.toLowerCase();

  if (ds === "unavailable") return "unavailable";
  if (ds === "partial") return "partial";
  if (ds === "stale") return "stale";

  // Check if bootstrap has meaningful content
  if (!data.analyst_verdict && !data.arbiter_decision && !data.reasoning_summary) {
    return "empty";
  }

  return "ready";
}

/** Derive which right rail panels should render from field presence. */
export function deriveRightRailPanels(
  data: JourneyBootstrapResponse | null,
): RightRailPanels {
  if (!data) {
    return {
      showArbiterSummary: false,
      showExplanation: false,
      showSetups: false,
      showNoTradeWarning: false,
      allUnavailable: true,
    };
  }

  const hasArbiter =
    data.arbiter_decision !== null &&
    data.arbiter_decision !== undefined &&
    typeof data.arbiter_decision === "object" &&
    Object.keys(data.arbiter_decision).length > 0;

  const hasExplanation =
    (data.explanation !== null &&
      data.explanation !== undefined &&
      typeof data.explanation === "object" &&
      Object.keys(data.explanation).length > 0) ||
    (data.reasoning_summary !== null && data.reasoning_summary !== undefined && data.reasoning_summary !== "");

  const hasSetups =
    hasArbiter &&
    Array.isArray(data.arbiter_decision?.approved_setups) &&
    data.arbiter_decision.approved_setups.length > 0;

  const hasNoTrade =
    hasArbiter &&
    Array.isArray(data.arbiter_decision?.no_trade_conditions) &&
    data.arbiter_decision.no_trade_conditions.length > 0;

  const allUnavailable = !hasArbiter && !hasExplanation && !hasSetups && !hasNoTrade;

  return {
    showArbiterSummary: hasArbiter,
    showExplanation: hasExplanation,
    showSetups: hasSetups,
    showNoTradeWarning: hasNoTrade,
    allUnavailable,
  };
}

/** Map raw approved setups to view models. */
export function mapSetups(setups: ApprovedSetup[] | undefined): SetupViewModel[] {
  if (!setups || !Array.isArray(setups)) return [];
  return setups.map((s) => ({
    type: s.type ?? "unknown",
    entryZone: s.entry_zone ?? "—",
    stop: s.stop ?? "—",
    targets: s.targets ?? [],
    rrEstimate: s.rr_estimate ?? 0,
    confidence: s.confidence ?? 0,
  }));
}

/** Safe accessor for nested arbiter fields. */
function safeArbiter(data: JourneyBootstrapResponse | null): ArbiterDecision {
  if (!data?.arbiter_decision || typeof data.arbiter_decision !== "object") {
    return {};
  }
  return data.arbiter_decision;
}

/** Safe accessor for analyst verdict fields. */
function safeVerdict(data: JourneyBootstrapResponse | null): AnalystVerdict {
  if (!data?.analyst_verdict || typeof data.analyst_verdict !== "object") {
    return { verdict: "", confidence: "" };
  }
  return data.analyst_verdict;
}

/** Build the full journey workspace view model. */
export function buildJourneyWorkspaceViewModel(
  data: JourneyBootstrapResponse | null,
  isLoading: boolean,
  isError: boolean,
  stageOverride?: JourneyStage,
  frozenSnapshotId?: string | null,
  draftJourneyId?: string | null,
  formState?: { thesis: string; conviction: string; notes: string; userDecision: string },
): JourneyWorkspaceViewModel {
  const condition = resolveJourneyCondition(data, isLoading, isError);
  const rightRail = deriveRightRailPanels(data);
  const arbiter = safeArbiter(data);
  const verdict = safeVerdict(data);
  const setups = mapSetups(arbiter.approved_setups);

  const isFrozen = stageOverride === "frozen" || stageOverride === "result";
  const stage = stageOverride ?? "explore";

  const isContentReady = condition === "ready" || condition === "stale" || condition === "partial";

  return {
    condition,
    dataState: data?.data_state ?? null,
    instrument: data?.instrument ?? "",
    generatedAt: data?.generated_at ?? null,

    analystVerdict: verdict.verdict || null,
    analystConfidence: verdict.confidence || null,
    arbiterBias: arbiter.final_bias ?? null,
    arbiterDecision: arbiter.decision ?? null,
    arbiterConfidence: arbiter.overall_confidence ?? null,
    arbiterNotes: arbiter.arbiter_notes ?? null,
    analystAgreement: arbiter.analyst_agreement_pct ?? null,
    riskOverride: arbiter.risk_override_applied ?? false,
    noTradeConditions: arbiter.no_trade_conditions ?? [],
    approvedSetups: setups,
    reasoningSummary: data?.reasoning_summary ?? null,

    rightRail,

    stage,
    isFrozen,
    frozenSnapshotId: frozenSnapshotId ?? null,
    canSaveDraft: isContentReady && !isFrozen,
    canFreeze: isContentReady && stage === "draft" && !isFrozen,
    canSaveResult: isFrozen && stage === "frozen",

    draftJourneyId: draftJourneyId ?? null,
    thesis: formState?.thesis ?? "",
    conviction: formState?.conviction ?? "",
    notes: formState?.notes ?? "",
    userDecision: formState?.userDecision ?? "",
  };
}
