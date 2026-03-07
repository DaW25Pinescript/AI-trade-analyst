/**
 * Journey Domain Types — Trade Ideation Journey v1
 *
 * These types define the canonical frontend domain model for the staged
 * trade ideation journey. All shapes trace to the interface audit
 * (docs/interface_audit.md) and the v1 contract freeze.
 *
 * This file uses JSDoc typedef annotations for IDE support without
 * requiring a build step. The existing frontend is vanilla JS.
 */

// ── Stage Keys ──────────────────────────────────────────────────────────────

/**
 * Semantic stage keys for the trade ideation journey.
 * Never reduce these to unnamed numbered tabs.
 * @readonly
 * @enum {string}
 */
export const StageKey = Object.freeze({
  MARKET_OVERVIEW: 'market_overview',
  ASSET_CONTEXT: 'asset_context',
  STRUCTURE_LIQUIDITY: 'structure_liquidity',
  MACRO_ALIGNMENT: 'macro_alignment',
  GATE_CHECKS: 'gate_checks',
  VERDICT_PLAN: 'verdict_plan',
  JOURNAL_CAPTURE: 'journal_capture',
});

/** @type {string[]} Ordered stage keys for navigation */
export const STAGE_ORDER = [
  StageKey.MARKET_OVERVIEW,
  StageKey.ASSET_CONTEXT,
  StageKey.STRUCTURE_LIQUIDITY,
  StageKey.MACRO_ALIGNMENT,
  StageKey.GATE_CHECKS,
  StageKey.VERDICT_PLAN,
  StageKey.JOURNAL_CAPTURE,
];

/** @type {Record<string, string>} Human-readable stage labels */
export const STAGE_LABELS = Object.freeze({
  [StageKey.MARKET_OVERVIEW]: 'Market Overview',
  [StageKey.ASSET_CONTEXT]: 'Asset Context',
  [StageKey.STRUCTURE_LIQUIDITY]: 'Structure & Liquidity',
  [StageKey.MACRO_ALIGNMENT]: 'Macro Alignment',
  [StageKey.GATE_CHECKS]: 'Gate Checks',
  [StageKey.VERDICT_PLAN]: 'Verdict & Plan',
  [StageKey.JOURNAL_CAPTURE]: 'Journal Capture',
});

// ── Journey Status ──────────────────────────────────────────────────────────

/**
 * @readonly
 * @enum {string}
 */
export const JourneyStatus = Object.freeze({
  DRAFT: 'draft',
  IN_REVIEW: 'in_review',
  BLOCKED: 'blocked',
  READY: 'ready',
  SAVED: 'saved',
  ARCHIVED: 'archived',
});

// ── Provenance ──────────────────────────────────────────────────────────────

/**
 * Provenance tags for field-level tracking.
 * @readonly
 * @enum {string}
 */
export const Provenance = Object.freeze({
  AI_PREFILL: 'ai_prefill',
  USER_CONFIRM: 'user_confirm',
  USER_OVERRIDE: 'user_override',
  USER_MANUAL: 'user_manual',
});

// ── Triage Status ───────────────────────────────────────────────────────────

/**
 * @readonly
 * @enum {string}
 */
export const TriageStatus = Object.freeze({
  ACTIONABLE: 'actionable',
  CONDITIONAL: 'conditional',
  WATCH: 'watch',
  AVOID: 'avoid',
});

// ── Gate States ─────────────────────────────────────────────────────────────

/**
 * @readonly
 * @enum {string}
 */
export const GateState = Object.freeze({
  PASSED: 'passed',
  CONDITIONAL: 'conditional',
  BLOCKED: 'blocked',
});

// ── Verdict/Confidence ──────────────────────────────────────────────────────

/**
 * @readonly
 * @enum {string}
 */
export const VerdictType = Object.freeze({
  LONG_BIAS: 'long_bias',
  SHORT_BIAS: 'short_bias',
  NO_TRADE: 'no_trade',
  CONDITIONAL: 'conditional',
  NO_DATA: 'no_data',
});

/**
 * @readonly
 * @enum {string}
 */
export const ConfidenceLevel = Object.freeze({
  HIGH: 'high',
  MODERATE: 'moderate',
  LOW: 'low',
  NONE: 'none',
});

// ── JSDoc Type Definitions ──────────────────────────────────────────────────

/**
 * @typedef {Object} ProvenanceField
 * @property {*} value - The field value
 * @property {string} provenance - One of Provenance enum values
 * @property {string} [updatedAt] - ISO timestamp of last update
 */

/**
 * @typedef {Object} TriageItem
 * @property {string} symbol - Instrument symbol (e.g. "EURUSD")
 * @property {string} triageStatus - One of TriageStatus values
 * @property {string} biasHint - Directional bias ("bullish"|"bearish"|"neutral"|"none")
 * @property {string[]} whyInterestingTags - Derived from structure supports + caution flags
 * @property {string} rationaleSummary - From ArbiterDecision.winning_rationale_summary
 * @property {string} confidence - One of ConfidenceLevel values
 * @property {string} consensusState - From ArbiterDecision.consensus_state
 * @property {string} verdict - One of VerdictType values
 * @property {boolean} noTradeEnforced - From ArbiterDecision.no_trade_enforced
 * @property {string} asOfUtc - Timestamp of analysis
 * @property {string|null} miniChartRef - Placeholder, null in v1
 */

/**
 * @typedef {Object} GateCheckItem
 * @property {string} id - Gate identifier
 * @property {string} label - Human-readable gate label
 * @property {string} state - One of GateState values
 * @property {string} [justification] - Required when state is conditional or blocked
 * @property {string} source - "system"|"user"
 * @property {string} [detail] - Additional detail from causal chain
 */

/**
 * @typedef {Object} SystemVerdict
 * @property {string} verdict - One of VerdictType values
 * @property {string} confidence - One of ConfidenceLevel values
 * @property {string} directionalBias - "bullish"|"bearish"|"neutral"|"none"
 * @property {string} consensusState - From ArbiterDecision
 * @property {boolean} noTradeEnforced
 * @property {string} synthesisNotes - From ArbiterDecision
 * @property {string} winningSummary - From ArbiterDecision
 * @property {Object} signalRanking - From ExplainabilityBlock
 * @property {Object} personaDominance - From ExplainabilityBlock
 * @property {Object} confidenceProvenance - From ExplainabilityBlock
 */

/**
 * @typedef {Object} UserDecision
 * @property {string|null} action - "take_trade"|"pass"|"watch"|"conditional_entry"|null
 * @property {string} [rationale] - User's reasoning
 * @property {string} provenance - Always "user_manual"
 * @property {string} [decidedAt] - ISO timestamp
 */

/**
 * @typedef {Object} ExecutionPlan
 * @property {string|null} direction - "long"|"short"|null
 * @property {number|null} entryPrice
 * @property {number|null} stopLoss
 * @property {number|null} takeProfit
 * @property {number|null} positionSize
 * @property {string|null} entryType - "market"|"limit"|"stop"|null
 * @property {string} [notes]
 * @property {string} provenance
 */

/**
 * @typedef {Object} DecisionSnapshot
 * @property {string} snapshotId
 * @property {string} instrument
 * @property {string} frozenAt - ISO timestamp
 * @property {string} journeyStatus
 * @property {SystemVerdict} systemVerdict
 * @property {UserDecision} userDecision
 * @property {ExecutionPlan} executionPlan
 * @property {GateCheckItem[]} gateStates
 * @property {Object} stageData - Frozen per-stage data
 * @property {Object} digest - StructureDigest at freeze time
 * @property {Object} [macroContext] - Macro snapshot at freeze time
 * @property {string[]} evidenceRefs
 * @property {string} [journalNotes]
 */

/**
 * @typedef {Object} JourneyState
 * @property {string} currentStage - One of StageKey values
 * @property {string} journeyStatus - One of JourneyStatus values
 * @property {string|null} selectedAsset - Instrument symbol
 * @property {TriageItem[]} triageItems - Loaded triage board items
 * @property {Object} stageData - Per-stage data keyed by StageKey
 * @property {GateCheckItem[]} gateStates - Current gate check states
 * @property {SystemVerdict|null} systemVerdict
 * @property {UserDecision|null} userDecision
 * @property {ExecutionPlan|null} executionPlan
 * @property {DecisionSnapshot|null} decisionSnapshot
 * @property {Object|null} resultSnapshot - Post-trade comparison (Phase 2+)
 * @property {string[]} evidenceRefs
 * @property {string} [journalNotes]
 */

/**
 * Creates a fresh empty journey state.
 * @returns {JourneyState}
 */
export function createEmptyJourneyState() {
  return {
    currentStage: StageKey.MARKET_OVERVIEW,
    journeyStatus: JourneyStatus.DRAFT,
    selectedAsset: null,
    triageItems: [],
    stageData: {
      [StageKey.MARKET_OVERVIEW]: null,
      [StageKey.ASSET_CONTEXT]: null,
      [StageKey.STRUCTURE_LIQUIDITY]: null,
      [StageKey.MACRO_ALIGNMENT]: null,
      [StageKey.GATE_CHECKS]: null,
      [StageKey.VERDICT_PLAN]: null,
      [StageKey.JOURNAL_CAPTURE]: null,
    },
    gateStates: [],
    systemVerdict: null,
    userDecision: null,
    executionPlan: null,
    decisionSnapshot: null,
    resultSnapshot: null,
    evidenceRefs: [],
    journalNotes: '',
  };
}

/**
 * Creates a default UserDecision.
 * @returns {UserDecision}
 */
export function createEmptyUserDecision() {
  return {
    action: null,
    rationale: '',
    provenance: Provenance.USER_MANUAL,
    decidedAt: null,
  };
}

/**
 * Creates a default ExecutionPlan.
 * @returns {ExecutionPlan}
 */
export function createEmptyExecutionPlan() {
  return {
    direction: null,
    entryPrice: null,
    stopLoss: null,
    takeProfit: null,
    positionSize: null,
    entryType: null,
    notes: '',
    provenance: Provenance.USER_MANUAL,
  };
}
