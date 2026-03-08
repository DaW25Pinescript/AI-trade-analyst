/**
 * Adapters — Trade Ideation Journey v1.1
 *
 * These adapters transform raw backend JSON artifacts into UI-consumable
 * typed shapes. V1.1 adds API-response adapters that handle snake_case → camelCase
 * conversion and data_state passthrough.
 *
 * Adapters are the ONLY place that knows about snake_case field names.
 * Components consume camelCase shapes exclusively.
 */

import { TriageStatus, GateState, VerdictType, ConfidenceLevel } from '../types/journey.js';

// ── Generic snake_case ↔ camelCase helpers ──────────────────────────────────

/**
 * Convert a snake_case string to camelCase.
 * @param {string} s
 * @returns {string}
 */
function snakeToCamel(s) {
  return s.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

/**
 * Convert a camelCase string to snake_case.
 * @param {string} s
 * @returns {string}
 */
function camelToSnake(s) {
  return s.replace(/[A-Z]/g, c => `_${c.toLowerCase()}`);
}

/**
 * Deep-convert all keys in an object from snake_case to camelCase.
 * @param {*} obj
 * @returns {*}
 */
function deepSnakeToCamel(obj) {
  if (obj === null || obj === undefined || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(deepSnakeToCamel);
  const result = {};
  for (const [key, value] of Object.entries(obj)) {
    result[snakeToCamel(key)] = deepSnakeToCamel(value);
  }
  return result;
}

/**
 * Deep-convert all keys in an object from camelCase to snake_case.
 * @param {*} obj
 * @returns {*}
 */
function deepCamelToSnake(obj) {
  if (obj === null || obj === undefined || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(deepCamelToSnake);
  const result = {};
  for (const [key, value] of Object.entries(obj)) {
    result[camelToSnake(key)] = deepCamelToSnake(value);
  }
  return result;
}

// ── Triage Adapters ─────────────────────────────────────────────────────────

/**
 * Adapt a GET /watchlist/triage API response to a UI-consumable shape.
 * Handles snake_case → camelCase and passes data_state through.
 *
 * @param {Object} raw - Raw API response
 * @returns {{items: Object[], dataState: string}}
 */
export function adaptTriageResponse(raw) {
  if (!raw) return { items: [], dataState: 'error' };

  const dataState = raw.data_state || 'unavailable';

  if (!raw.items || raw.items.length === 0) {
    return { items: [], dataState };
  }

  const items = raw.items.map(item => ({
    symbol: item.symbol || 'UNKNOWN',
    triageStatus: _mapTriageStatus(item.triage_status),
    biasHint: item.bias === 'neutral' ? 'neutral' : item.bias || 'none',
    whyInterestingTags: item.why_interesting || [],
    rationaleSummary: item.rationale || '',
    confidence: item.confidence || ConfidenceLevel.NONE,
    consensusState: '',
    verdict: item.bias === 'long' ? 'long_bias' : item.bias === 'short' ? 'short_bias' : 'no_data',
    noTradeEnforced: item.triage_status === 'blocked',
    asOfUtc: item.verdict_at || '',
    miniChartRef: null,
    dataState: dataState,
  }));

  return { items, dataState };
}

/**
 * Maps a MultiAnalystOutput JSON dict to a TriageItem.
 * Kept for backward compatibility with file-based reads.
 *
 * @param {Object} raw - Raw MultiAnalystOutput JSON
 * @returns {import('../types/journey.js').TriageItem}
 */
export function adaptTriageItem(raw) {
  if (!raw) return _emptyTriageItem();

  const arbiter = raw.arbiter_decision || {};
  const digest = raw.digest || {};

  return {
    symbol: raw.instrument || 'UNKNOWN',
    triageStatus: _deriveTriageStatus(arbiter),
    biasHint: arbiter.final_directional_bias || 'none',
    whyInterestingTags: _deriveWhyInterestingTags(digest, arbiter),
    rationaleSummary: arbiter.winning_rationale_summary || '',
    confidence: arbiter.final_confidence || ConfidenceLevel.NONE,
    consensusState: arbiter.consensus_state || '',
    verdict: arbiter.final_verdict || VerdictType.NO_DATA,
    noTradeEnforced: !!arbiter.no_trade_enforced,
    asOfUtc: raw.as_of_utc || '',
    miniChartRef: null,
  };
}

/**
 * Maps multiple MultiAnalystOutput JSON files to TriageItem[].
 * @param {Object[]} rawOutputs
 * @returns {import('../types/journey.js').TriageItem[]}
 */
export function adaptTriageList(rawOutputs) {
  if (!rawOutputs || !Array.isArray(rawOutputs)) return [];
  return rawOutputs.filter(Boolean).map(adaptTriageItem);
}

// ── Journey Bootstrap Adapters ──────────────────────────────────────────────

/**
 * Adapt a GET /journey/{asset}/bootstrap API response.
 * Handles snake_case → camelCase and data_state passthrough.
 *
 * @param {Object} raw - Raw API response
 * @returns {Object} Journey bootstrap data with dataState
 */
export function adaptBootstrapResponse(raw) {
  if (!raw) return { dataState: 'error', instrument: 'UNKNOWN' };

  const dataState = raw.data_state || 'unavailable';

  if (dataState === 'unavailable') {
    return {
      dataState,
      instrument: raw.instrument || 'UNKNOWN',
      stageData: {},
      gateStates: [],
      systemVerdict: null,
    };
  }

  const digest = raw.structure_digest || {};
  const arbiter = raw.arbiter_decision || {};
  const explain = raw.explanation || {};

  // Build the bootstrap using the same shape as adaptJourneyBootstrap
  // but sourced from the API response instead of raw files
  const multiOutput = {
    instrument: raw.instrument,
    as_of_utc: raw.generated_at,
    digest: digest,
    persona_outputs: [],
    arbiter_decision: arbiter,
    final_verdict: {
      verdict: (raw.analyst_verdict || {}).verdict || 'no_data',
      confidence: (raw.analyst_verdict || {}).confidence || 'none',
    },
  };

  const explainBlock = Object.keys(explain).length > 0 ? explain : null;

  const bootstrap = adaptJourneyBootstrap(multiOutput, explainBlock, null);
  bootstrap.dataState = dataState;
  return bootstrap;
}

/**
 * Maps MultiAnalystOutput + ExplainabilityBlock + MacroSnapshot into
 * a journey bootstrap object.
 *
 * @param {Object} multiOutput - Raw MultiAnalystOutput JSON
 * @param {Object|null} explainBlock - Raw ExplainabilityBlock JSON (may be null)
 * @param {Object|null} macroSnapshot - Raw macro_snapshot.json
 * @returns {Object} Journey bootstrap data
 */
export function adaptJourneyBootstrap(multiOutput, explainBlock, macroSnapshot) {
  if (!multiOutput) {
    return {
      instrument: 'UNKNOWN',
      dataState: 'unavailable',
      stageData: {},
      gateStates: [],
      systemVerdict: null,
    };
  }

  const digest = multiOutput.digest || {};
  const camelDigest = deepSnakeToCamel(digest);
  const arbiter = multiOutput.arbiter_decision || {};
  const personas = multiOutput.persona_outputs || [];
  const finalVerdict = multiOutput.final_verdict || {};

  return {
    instrument: multiOutput.instrument,
    stageData: {
      market_overview: {
        instrument: multiOutput.instrument,
        asOfUtc: multiOutput.as_of_utc,
        biasHint: arbiter.final_directional_bias,
        confidence: arbiter.final_confidence,
        consensusState: arbiter.consensus_state,
        marketFeatures: null,
      },
      asset_context: {
        digest: camelDigest,
        personas: personas,
        finalVerdict: finalVerdict,
        signalRanking: explainBlock?.signal_ranking || null,
      },
      structure_liquidity: {
        digest: camelDigest,
        htfBias: digest.htf_bias,
        lastBos: digest.last_bos,
        lastMss: digest.last_mss,
        bosMssAlignment: digest.bos_mss_alignment,
        liquidityBias: digest.liquidity_bias,
        activeFvgContext: digest.active_fvg_context,
        recentSweepSignal: digest.recent_sweep_signal,
        structureSupports: digest.structure_supports || [],
        structureConflicts: digest.structure_conflicts || [],
        nearestLiquidityAbove: digest.nearest_liquidity_above,
        nearestLiquidityBelow: digest.nearest_liquidity_below,
      },
      macro_alignment: macroSnapshot?.macro_context ? {
        regime: macroSnapshot.macro_context.regime,
        volBias: macroSnapshot.macro_context.vol_bias,
        directionalPressure: macroSnapshot.macro_context.directional_pressure,
        confidence: macroSnapshot.macro_context.confidence,
        conflictScore: macroSnapshot.macro_context.conflict_score,
        topDrivers: macroSnapshot.macro_context.top_drivers || [],
        explanation: macroSnapshot.macro_context.explanation || [],
        events: macroSnapshot.events || [],
        sourceHealth: macroSnapshot.source_health || {},
      } : null,
      gate_checks: null,
      verdict_plan: null,
      journal_capture: null,
    },
    gateStates: adaptGateSeed(digest, explainBlock?.causal_chain || null),
    systemVerdict: _buildSystemVerdict(arbiter, explainBlock),
  };
}

// ── Save Adapter (camelCase → snake_case) ───────────────────────────────────

/**
 * Convert a frontend snapshot object to snake_case for backend POST.
 * @param {Object} snapshot - camelCase snapshot from the store
 * @returns {Object} snake_case payload for the backend
 */
export function adaptSnapshotForSave(snapshot) {
  if (!snapshot) return {};
  return deepCamelToSnake(snapshot);
}

// ── Journal/Review Adapters (snake_case → camelCase) ────────────────────────

/**
 * Adapt GET /journal/decisions response to camelCase UI records.
 * @param {Object} raw - { records: [...] }
 * @returns {Object[]}
 */
export function adaptJournalRecords(raw) {
  if (!raw || !raw.records) return [];
  return raw.records.map(r => ({
    snapshotId: r.snapshot_id || '',
    instrument: r.instrument || '',
    savedAt: r.saved_at || '',
    frozenAt: r.saved_at || '', // alias for backward compat
    journeyStatus: r.journey_status || '',
    verdict: r.verdict || '',
    userDecision: r.user_decision || null,
  }));
}

/**
 * Adapt GET /review/records response to camelCase UI records.
 * @param {Object} raw - { records: [...] }
 * @returns {Object[]}
 */
export function adaptReviewRecords(raw) {
  if (!raw || !raw.records) return [];
  return raw.records.map(r => ({
    snapshotId: r.snapshot_id || '',
    instrument: r.instrument || '',
    savedAt: r.saved_at || '',
    journeyStatus: r.journey_status || '',
    verdict: r.verdict || '',
    userDecision: r.user_decision || null,
    hasResult: !!r.has_result,
  }));
}

// ── Gates Seed Adapter ──────────────────────────────────────────────────────

/**
 * Derives initial gate states from StructureDigest and CausalChain.
 *
 * @param {Object} digest - StructureDigest dict
 * @param {Object|null} causalChain - CausalChain dict
 * @returns {import('../types/journey.js').GateCheckItem[]}
 */
export function adaptGateSeed(digest, causalChain) {
  if (!digest) return [];

  const gates = [];

  // Gate 1: Structure Gate
  gates.push({
    id: 'structure_gate',
    label: 'Structure Gate',
    state: _mapStructureGate(digest.structure_gate),
    source: 'system',
    detail: digest.gate_reason || null,
  });

  // Gate 2: No-Trade Flags
  const noTradeFlags = digest.no_trade_flags || [];
  gates.push({
    id: 'no_trade_flags',
    label: 'No-Trade Flags',
    state: noTradeFlags.length > 0 ? GateState.BLOCKED : GateState.PASSED,
    source: 'system',
    detail: noTradeFlags.length > 0 ? noTradeFlags.join('; ') : null,
  });

  // Gate 3: Caution Flags
  const cautionFlags = digest.caution_flags || [];
  gates.push({
    id: 'caution_flags',
    label: 'Caution Flags',
    state: cautionFlags.length > 0 ? GateState.CONDITIONAL : GateState.PASSED,
    source: 'system',
    detail: cautionFlags.length > 0 ? cautionFlags.join('; ') : null,
  });

  // Gate 4: Hard Block (from causal chain)
  if (causalChain) {
    const hasHardBlock = causalChain.has_hard_block;
    const noTradeDrivers = causalChain.no_trade_drivers || [];
    gates.push({
      id: 'hard_block',
      label: 'Hard Block Check',
      state: hasHardBlock ? GateState.BLOCKED : GateState.PASSED,
      source: 'system',
      detail: noTradeDrivers.length > 0
        ? noTradeDrivers.map(d => `${d.flag}: ${d.effect}`).join('; ')
        : null,
    });
  }

  // Gate 5: BOS/MSS Alignment
  gates.push({
    id: 'bos_mss_alignment',
    label: 'BOS/MSS Alignment',
    state: _mapAlignmentGate(digest.bos_mss_alignment),
    source: 'system',
    detail: digest.bos_mss_alignment || null,
  });

  return gates;
}

// ── System Verdict Builder ──────────────────────────────────────────────────

function _buildSystemVerdict(arbiter, explain) {
  if (!arbiter || Object.keys(arbiter).length === 0) return null;

  return {
    verdict: arbiter.final_verdict || VerdictType.NO_DATA,
    confidence: arbiter.final_confidence || ConfidenceLevel.NONE,
    directionalBias: arbiter.final_directional_bias || 'none',
    consensusState: arbiter.consensus_state || '',
    noTradeEnforced: !!arbiter.no_trade_enforced,
    synthesisNotes: arbiter.synthesis_notes || '',
    winningSummary: arbiter.winning_rationale_summary || '',
    signalRanking: explain?.signal_ranking || null,
    personaDominance: explain?.persona_dominance || null,
    confidenceProvenance: explain?.confidence_provenance || null,
  };
}

// ── Internal Helpers ────────────────────────────────────────────────────────

function _emptyTriageItem() {
  return {
    symbol: 'UNKNOWN',
    triageStatus: TriageStatus.AVOID,
    biasHint: 'none',
    whyInterestingTags: [],
    rationaleSummary: '',
    confidence: ConfidenceLevel.NONE,
    consensusState: '',
    verdict: VerdictType.NO_DATA,
    noTradeEnforced: false,
    asOfUtc: '',
    miniChartRef: null,
  };
}

function _mapTriageStatus(status) {
  const map = {
    active: TriageStatus.ACTIONABLE,
    watch: TriageStatus.WATCH,
    blocked: TriageStatus.AVOID,
    no_data: TriageStatus.AVOID,
  };
  return map[status] || TriageStatus.WATCH;
}

function _deriveTriageStatus(arbiter) {
  if (!arbiter) return TriageStatus.WATCH;
  if (arbiter.no_trade_enforced) return TriageStatus.AVOID;
  const v = arbiter.final_verdict;
  const c = arbiter.final_confidence;
  if ((v === 'long_bias' || v === 'short_bias') && (c === 'high' || c === 'moderate')) {
    return TriageStatus.ACTIONABLE;
  }
  if (v === 'conditional') return TriageStatus.CONDITIONAL;
  if (v === 'no_trade' || v === 'no_data') return TriageStatus.AVOID;
  return TriageStatus.WATCH;
}

function _deriveWhyInterestingTags(digest, arbiter) {
  const tags = [];
  if (digest && digest.structure_supports) {
    tags.push(...digest.structure_supports.slice(0, 3));
  }
  if (digest && digest.caution_flags && digest.caution_flags.length > 0) {
    tags.push(...digest.caution_flags.slice(0, 2).map(f => `caution: ${f}`));
  }
  if (arbiter && arbiter.consensus_state) {
    tags.push(arbiter.consensus_state);
  }
  return tags;
}

function _mapStructureGate(gate) {
  if (gate === 'pass') return GateState.PASSED;
  if (gate === 'fail') return GateState.BLOCKED;
  if (gate === 'mixed') return GateState.CONDITIONAL;
  return GateState.CONDITIONAL;
}

function _mapAlignmentGate(alignment) {
  if (alignment === 'aligned') return GateState.PASSED;
  if (alignment === 'conflicted') return GateState.BLOCKED;
  return GateState.CONDITIONAL;
}
