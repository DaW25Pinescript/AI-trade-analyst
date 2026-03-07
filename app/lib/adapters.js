/**
 * Adapters — Trade Ideation Journey v1
 *
 * These adapters transform raw backend JSON artifacts into UI-consumable
 * typed shapes. Each adapter is traced to the interface audit
 * (docs/interface_audit.md) and consumes only frozen contract fields.
 *
 * Transport pattern: File-based (Pattern A).
 * The service layer reads saved JSON from analyst/output/ and app/data/.
 */

import { TriageStatus, GateState, VerdictType, ConfidenceLevel } from '../types/journey.js';

// ── Triage Adapter ──────────────────────────────────────────────────────────

/**
 * Maps a MultiAnalystOutput JSON dict to a TriageItem.
 *
 * Source: analyst/output/{instrument}_multi_analyst_output.json
 * Contract: MultiAnalystOutput.to_dict()
 *
 * @param {Object} raw - Raw MultiAnalystOutput JSON
 * @returns {import('../types/journey.js').TriageItem}
 */
export function adaptTriageItem(raw) {
  const arbiter = raw.arbiter_decision || {};
  const digest = raw.digest || {};
  const finalVerdict = raw.final_verdict || {};

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
    miniChartRef: null, // TODO: missing — no chart data source in v1
  };
}

/**
 * Maps multiple MultiAnalystOutput JSON files to TriageItem[].
 * @param {Object[]} rawOutputs
 * @returns {import('../types/journey.js').TriageItem[]}
 */
export function adaptTriageList(rawOutputs) {
  return rawOutputs.map(adaptTriageItem);
}

// ── Journey Bootstrap Adapter ───────────────────────────────────────────────

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
  const digest = multiOutput.digest || {};
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
        // TODO: requires_adapter — MarketPacketV2 not persisted as standalone JSON
        marketFeatures: null,
      },
      asset_context: {
        digest: digest,
        personas: personas,
        finalVerdict: finalVerdict,
        signalRanking: explainBlock?.signal_ranking || null,
      },
      structure_liquidity: {
        digest: digest,
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
      gate_checks: null, // Seeded by gatesSeedAdapter
      verdict_plan: null,
      journal_capture: null,
    },
    gateStates: adaptGateSeed(digest, explainBlock?.causal_chain || null),
    systemVerdict: _buildSystemVerdict(arbiter, explainBlock),
  };
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

/**
 * Builds a SystemVerdict from arbiter decision and explainability block.
 * @param {Object} arbiter - ArbiterDecision dict
 * @param {Object|null} explain - ExplainabilityBlock dict
 * @returns {import('../types/journey.js').SystemVerdict}
 */
function _buildSystemVerdict(arbiter, explain) {
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

function _deriveTriageStatus(arbiter) {
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
  if (digest.structure_supports) {
    tags.push(...digest.structure_supports.slice(0, 3));
  }
  if (digest.caution_flags && digest.caution_flags.length > 0) {
    tags.push(...digest.caution_flags.slice(0, 2).map(f => `caution: ${f}`));
  }
  if (arbiter.consensus_state) {
    tags.push(arbiter.consensus_state);
  }
  return tags;
}

function _mapStructureGate(gate) {
  if (gate === 'pass') return GateState.PASSED;
  if (gate === 'fail') return GateState.BLOCKED;
  if (gate === 'mixed') return GateState.CONDITIONAL;
  return GateState.CONDITIONAL; // no_data → treat as conditional
}

function _mapAlignmentGate(alignment) {
  if (alignment === 'aligned') return GateState.PASSED;
  if (alignment === 'conflicted') return GateState.BLOCKED;
  return GateState.CONDITIONAL; // incomplete or unknown
}
