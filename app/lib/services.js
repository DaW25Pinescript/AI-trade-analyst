/**
 * Service Layer — Trade Ideation Journey v1
 *
 * Transport pattern: File-based (Pattern A).
 * Reads saved JSON artifacts from analyst/output/ and app/data/.
 *
 * No component should contain raw fetch logic or direct file reads.
 * All backend data flows through this service layer.
 *
 * In production, these functions read real JSON files.
 * In development/demo mode, they return typed mock data.
 */

import { adaptTriageItem, adaptTriageList, adaptJourneyBootstrap } from './adapters.js';

/** @type {'file' | 'api'} Declared transport pattern — locked per audit */
export const TRANSPORT_PATTERN = 'file';

// ── Configuration ───────────────────────────────────────────────────────────

/**
 * Base path for analyst output artifacts.
 * In file-based mode, this is the directory containing JSON outputs.
 */
let _outputBasePath = '../analyst/output';
let _dataBasePath = './data';

/** Set the base path for analyst outputs (for testing/configuration). */
export function setOutputBasePath(path) { _outputBasePath = path; }
export function setDataBasePath(path) { _dataBasePath = path; }

// ── Demo Mode ───────────────────────────────────────────────────────────────

let _demoMode = true; // Default to demo mode until real artifacts exist

export function setDemoMode(enabled) { _demoMode = enabled; }
export function isDemoMode() { return _demoMode; }

// ── Triage Service ──────────────────────────────────────────────────────────

/**
 * Load triage items for the dashboard.
 * In file mode: scans analyst/output/ for *_multi_analyst_output.json files.
 * In demo mode: returns typed mock data.
 *
 * @returns {Promise<import('../types/journey.js').TriageItem[]>}
 */
export async function loadTriageItems() {
  if (_demoMode) return _demoTriageItems();

  try {
    // In file-based mode, we need to know which instruments have outputs.
    // This would typically be provided by a manifest or directory listing.
    // For now, attempt to load a known instrument list.
    const manifest = await _fetchJSON(`${_outputBasePath}/manifest.json`).catch(() => null);
    if (!manifest || !manifest.instruments) {
      console.warn('[services] No manifest found. Falling back to demo data.');
      return _demoTriageItems();
    }

    const outputs = await Promise.all(
      manifest.instruments.map(inst =>
        _fetchJSON(`${_outputBasePath}/${inst}_multi_analyst_output.json`).catch(() => null)
      )
    );

    return adaptTriageList(outputs.filter(Boolean));
  } catch (e) {
    console.error('[services] Failed to load triage items:', e);
    return _demoTriageItems();
  }
}

// ── Journey Bootstrap Service ───────────────────────────────────────────────

/**
 * Load journey bootstrap data for a specific instrument.
 *
 * @param {string} instrument - e.g. "EURUSD"
 * @returns {Promise<Object>} Journey bootstrap from adaptJourneyBootstrap
 */
export async function loadJourneyBootstrap(instrument) {
  if (_demoMode) return _demoJourneyBootstrap(instrument);

  try {
    const [multiOutput, explainBlock, macroSnapshot] = await Promise.all([
      _fetchJSON(`${_outputBasePath}/${instrument}_multi_analyst_output.json`),
      _fetchJSON(`${_outputBasePath}/${instrument}_multi_analyst_explainability.json`).catch(() => null),
      _fetchJSON(`${_dataBasePath}/macro_snapshot.json`).catch(() => null),
    ]);

    return adaptJourneyBootstrap(multiOutput, explainBlock, macroSnapshot);
  } catch (e) {
    console.error(`[services] Failed to load journey bootstrap for ${instrument}:`, e);
    return _demoJourneyBootstrap(instrument);
  }
}

// ── Persistence Service ─────────────────────────────────────────────────────

/**
 * Save a decision snapshot to local storage.
 * In v1, persistence is browser-local (localStorage/IndexedDB).
 *
 * @param {import('../types/journey.js').DecisionSnapshot} snapshot
 * @returns {Promise<boolean>}
 */
export async function saveSnapshot(snapshot) {
  try {
    const key = `journey_snapshot_${snapshot.snapshotId}`;
    localStorage.setItem(key, JSON.stringify(snapshot));

    // Also update the snapshot index
    const indexKey = 'journey_snapshot_index';
    const existing = JSON.parse(localStorage.getItem(indexKey) || '[]');
    existing.push({
      snapshotId: snapshot.snapshotId,
      instrument: snapshot.instrument,
      frozenAt: snapshot.frozenAt,
      journeyStatus: snapshot.journeyStatus,
    });
    localStorage.setItem(indexKey, JSON.stringify(existing));

    return true;
  } catch (e) {
    console.error('[services] Failed to save snapshot:', e);
    return false;
  }
}

/**
 * Load saved snapshots index.
 * @returns {Promise<Object[]>}
 */
export async function loadSnapshotIndex() {
  try {
    return JSON.parse(localStorage.getItem('journey_snapshot_index') || '[]');
  } catch {
    return [];
  }
}

/**
 * Load a specific snapshot by ID.
 * @param {string} snapshotId
 * @returns {Promise<import('../types/journey.js').DecisionSnapshot|null>}
 */
export async function loadSnapshot(snapshotId) {
  try {
    const raw = localStorage.getItem(`journey_snapshot_${snapshotId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// ── Review Service ──────────────────────────────────────────────────────────

/**
 * Load review patterns. Stub — not yet produced by backend.
 * @returns {Promise<Object>}
 */
export async function loadReviewPatterns() {
  // TODO: missing — review patterns not yet produced by backend
  return {
    _stub: true,
    _note: 'Review patterns not yet available. Stub per interface audit.',
    overrideFrequency: [],
    gateFailureClusters: [],
    plannedVsActual: [],
  };
}

// ── Internal Helpers ────────────────────────────────────────────────────────

async function _fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
  return res.json();
}

// ── Demo Data ───────────────────────────────────────────────────────────────
// Typed mock data for development. Clearly marked as demo, not real backend.

function _demoTriageItems() {
  return [
    {
      symbol: 'EURUSD',
      triageStatus: 'actionable',
      biasHint: 'bearish',
      whyInterestingTags: ['htf_bearish_regime', 'bos_mss_aligned', 'discount_fvg_active'],
      rationaleSummary: 'HTF bearish bias confirmed with aligned BOS/MSS. Discount FVG provides potential entry zone.',
      confidence: 'high',
      consensusState: 'full_agreement',
      verdict: 'short_bias',
      noTradeEnforced: false,
      asOfUtc: '2026-03-07T10:00:00Z',
      miniChartRef: null,
    },
    {
      symbol: 'XAUUSD',
      triageStatus: 'conditional',
      biasHint: 'bullish',
      whyInterestingTags: ['sweep_reclaim_bullish', 'caution: elevated_volatility', 'partial_agreement'],
      rationaleSummary: 'Bullish sweep reclaim but elevated volatility warrants conditional approach.',
      confidence: 'moderate',
      consensusState: 'partial_agreement',
      verdict: 'conditional',
      noTradeEnforced: false,
      asOfUtc: '2026-03-07T10:00:00Z',
      miniChartRef: null,
    },
    {
      symbol: 'GBPUSD',
      triageStatus: 'watch',
      biasHint: 'neutral',
      whyInterestingTags: ['mixed_signals', 'incomplete_structure'],
      rationaleSummary: 'Structure signals are mixed. Watching for clearer directional confirmation.',
      confidence: 'low',
      consensusState: 'direction_conflict',
      verdict: 'conditional',
      noTradeEnforced: false,
      asOfUtc: '2026-03-07T10:00:00Z',
      miniChartRef: null,
    },
    {
      symbol: 'USDJPY',
      triageStatus: 'avoid',
      biasHint: 'none',
      whyInterestingTags: ['no_trade: spread_too_wide', 'no_data_structure'],
      rationaleSummary: 'No-trade enforced due to spread conditions and missing structure data.',
      confidence: 'none',
      consensusState: 'no_trade_enforced',
      verdict: 'no_trade',
      noTradeEnforced: true,
      asOfUtc: '2026-03-07T10:00:00Z',
      miniChartRef: null,
    },
  ];
}

function _demoJourneyBootstrap(instrument) {
  const demoDigest = {
    instrument,
    as_of_utc: '2026-03-07T10:00:00Z',
    structure_available: true,
    structure_gate: 'pass',
    gate_reason: null,
    htf_bias: 'bearish',
    htf_source_timeframe: '4H',
    last_bos: 'bearish',
    last_mss: 'bearish',
    bos_mss_alignment: 'aligned',
    liquidity_bias: 'below_closer',
    active_fvg_context: 'discount_bullish',
    active_fvg_count: 2,
    recent_sweep_signal: 'bearish_reclaim',
    structure_supports: ['htf_bearish_regime', 'bos_mss_aligned', 'liquidity_below_closer'],
    structure_conflicts: [],
    no_trade_flags: [],
    caution_flags: [],
    nearest_liquidity_above: { type: 'prior_day_high', price: 1.0890, scope: 'external_liquidity', status: 'active' },
    nearest_liquidity_below: { type: 'prior_day_low', price: 1.0820, scope: 'external_liquidity', status: 'active' },
  };

  const demoCausalChain = {
    no_trade_drivers: [],
    caution_drivers: [],
    has_hard_block: false,
  };

  const demoExplain = {
    instrument,
    as_of_utc: '2026-03-07T10:00:00Z',
    source_verdict: 'short_bias',
    source_confidence: 'high',
    signal_ranking: {
      dominant_signal: 'htf_regime',
      primary_conflict: null,
      signals: [
        { signal: 'htf_regime', value: 'bearish', influence: 'dominant', direction: 'bearish', note: 'HTF regime confirms bearish bias' },
        { signal: 'bos_mss', value: 'aligned', influence: 'supporting', direction: 'bearish', note: 'BOS/MSS alignment supports bearish direction' },
        { signal: 'fvg_context', value: 'discount_bullish', influence: 'supporting', direction: 'bearish', note: 'Discount FVG provides entry zone' },
        { signal: 'sweep_reclaim', value: 'bearish_reclaim', influence: 'supporting', direction: 'bearish', note: 'Recent sweep reclaim confirms sell-side intent' },
      ],
    },
    persona_dominance: {
      direction_driver: 'technical_structure',
      confidence_driver: 'technical_structure',
      confidence_effect: 'held',
      stricter_persona: null,
      python_override_active: false,
      note: 'Technical structure persona drove direction and confidence. Full agreement.',
    },
    confidence_provenance: {
      steps: [
        { step: 1, label: 'Technical Structure Analyst', value: 'high', rule: 'direct_assessment' },
        { step: 2, label: 'Execution Timing Analyst', value: 'high', rule: 'direct_assessment' },
        { step: 3, label: 'Arbiter Consensus', value: 'high', rule: 'aligned_confidence' },
      ],
      final_confidence: 'high',
      python_override: false,
      override_reason: null,
    },
    causal_chain: demoCausalChain,
    audit_summary: 'Demo: Bearish short bias with high confidence. All structure signals aligned.',
  };

  const demoMacro = {
    macro_context: {
      regime: 'risk_off',
      vol_bias: 'expanding',
      directional_pressure: 'defensive',
      confidence: '72%',
      conflict_score: -0.34,
      top_drivers: ['Hot CPI surprise', 'GDELT geopolitical stress tone'],
      explanation: [
        'Inflation surprise remains above forecast and supports hawkish repricing.',
        'Geopolitical stress is elevating cross-asset risk aversion.',
      ],
    },
    events: [
      { event_id: 'demo-cpi', source: 'finnhub', title: 'US CPI m/m', category: 'inflation', timestamp: '2026-03-07T13:30:00Z', importance: 'high' },
    ],
    source_health: {
      finnhub: { status: 'ok', record_count: 12, latency_ms: 340 },
    },
  };

  const demoArbiter = {
    instrument,
    as_of_utc: '2026-03-07T10:00:00Z',
    consensus_state: 'full_agreement',
    final_verdict: 'short_bias',
    final_confidence: 'high',
    final_directional_bias: 'bearish',
    no_trade_enforced: false,
    personas_agree_direction: true,
    personas_agree_confidence: true,
    confidence_spread: 'aligned',
    synthesis_notes: 'Both personas agree on bearish direction with high confidence.',
    winning_rationale_summary: 'HTF bearish bias confirmed with aligned BOS/MSS and supportive liquidity structure.',
  };

  const multiOutput = {
    instrument,
    as_of_utc: '2026-03-07T10:00:00Z',
    digest: demoDigest,
    persona_outputs: [],
    arbiter_decision: demoArbiter,
    final_verdict: {
      instrument,
      as_of_utc: '2026-03-07T10:00:00Z',
      verdict: 'short_bias',
      confidence: 'high',
      structure_gate: 'pass',
      htf_bias: 'bearish',
      ltf_structure_alignment: 'aligned',
      active_fvg_context: 'discount_bullish',
      recent_sweep_signal: 'bearish_reclaim',
      structure_supports: ['htf_bearish_regime', 'bos_mss_aligned'],
      structure_conflicts: [],
      no_trade_flags: [],
      caution_flags: [],
    },
  };

  return adaptJourneyBootstrap(multiOutput, demoExplain, demoMacro);
}
