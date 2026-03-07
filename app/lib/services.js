/**
 * Service Layer — Trade Ideation Journey v1.1
 *
 * Transport pattern: API-first (V1.1).
 * All reads go through FastAPI at port 8000.
 * Demo fallback only when backend is unreachable — sets data_state: "demo".
 *
 * No component should contain raw fetch logic or direct file reads.
 * All backend data flows through this service layer.
 */

import {
  adaptTriageItem,
  adaptTriageList,
  adaptTriageResponse,
  adaptJourneyBootstrap,
  adaptBootstrapResponse,
  adaptSnapshotForSave,
  adaptJournalRecords,
  adaptReviewRecords,
} from './adapters.js';

/** @type {'api'} Declared transport pattern — locked per audit */
export const TRANSPORT_PATTERN = 'api';

// ── Configuration ───────────────────────────────────────────────────────────

const API_BASE = 'http://localhost:8000';

// ── Demo Mode ───────────────────────────────────────────────────────────────

let _demoMode = false;

export function setDemoMode(enabled) { _demoMode = enabled; }
export function isDemoMode() { return _demoMode; }

// ── Triage Service ──────────────────────────────────────────────────────────

/**
 * Fetch triage items for the dashboard.
 * Calls GET /watchlist/triage. Falls back to demo on network failure.
 *
 * @returns {Promise<{items: import('../types/journey.js').TriageItem[], dataState: string}>}
 */
export async function fetchTriage() {
  try {
    const res = await fetch(`${API_BASE}/watchlist/triage`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return adaptTriageResponse(data);
  } catch (e) {
    console.warn('[services] fetchTriage failed, using demo fallback:', e.message);
    return _demoTriageResponse();
  }
}

/**
 * Legacy alias for backward compatibility with DashboardPage.
 * @returns {Promise<import('../types/journey.js').TriageItem[]>}
 */
export async function loadTriageItems() {
  const result = await fetchTriage();
  // Attach dataState to the array for components that need it
  const items = result.items;
  items._dataState = result.dataState;
  return items;
}

export async function runTriage(options = {}) {
  const res = await fetch(`${API_BASE}/triage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: 'manual_trigger', ...options }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.message || detail.detail || `HTTP ${res.status}`);
  }
  const data = await res.json();
  return { success: true, artifactsWritten: data.artifacts_written ?? 0 };
}

// ── Journey Bootstrap Service ───────────────────────────────────────────────

/**
 * Fetch bootstrap data for a specific instrument.
 * Calls GET /journey/{asset}/bootstrap.
 *
 * @param {string} asset - Instrument symbol
 * @returns {Promise<Object>} Adapted journey bootstrap
 */
export async function fetchBootstrap(asset) {
  try {
    const res = await fetch(`${API_BASE}/journey/${encodeURIComponent(asset)}/bootstrap`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return adaptBootstrapResponse(data);
  } catch (e) {
    console.warn(`[services] fetchBootstrap(${asset}) failed, using demo fallback:`, e.message);
    return _demoJourneyBootstrap(asset);
  }
}

/**
 * Legacy alias for backward compatibility with JourneyPage.
 * @param {string} instrument
 * @returns {Promise<Object>}
 */
export async function loadJourneyBootstrap(instrument) {
  return fetchBootstrap(instrument);
}

// ── Persistence Service ─────────────────────────────────────────────────────

/**
 * Save a journey draft to the backend.
 * @param {Object} state - Journey state object
 * @returns {Promise<{success: boolean, journeyId?: string, savedAt?: string, error?: string}>}
 */
export async function saveDraft(state) {
  try {
    const payload = adaptSnapshotForSave(state);
    const res = await fetch(`${API_BASE}/journey/draft`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.success) {
      return { success: false, error: data.error || 'Draft save failed' };
    }
    return {
      success: true,
      journeyId: data.journey_id,
      savedAt: data.saved_at,
    };
  } catch (e) {
    console.error('[services] saveDraft failed:', e);
    return { success: false, error: e.message };
  }
}

/**
 * Save a frozen decision snapshot to the backend.
 * @param {import('../types/journey.js').DecisionSnapshot} snapshot
 * @returns {Promise<{success: boolean, snapshotId?: string, savedAt?: string, error?: string}>}
 */
export async function saveDecision(snapshot) {
  try {
    const payload = adaptSnapshotForSave(snapshot);
    const res = await fetch(`${API_BASE}/journey/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.success) {
      return { success: false, error: data.error || 'Decision save failed' };
    }
    return {
      success: true,
      snapshotId: data.snapshot_id,
      savedAt: data.saved_at,
    };
  } catch (e) {
    console.error('[services] saveDecision failed:', e);
    return { success: false, error: e.message };
  }
}

/**
 * Save a result snapshot to the backend.
 * @param {Object} snapshot
 * @returns {Promise<{success: boolean, snapshotId?: string, savedAt?: string, error?: string}>}
 */
export async function saveResult(snapshot) {
  try {
    const payload = adaptSnapshotForSave(snapshot);
    const res = await fetch(`${API_BASE}/journey/result`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.success) {
      return { success: false, error: data.error || 'Result save failed' };
    }
    return {
      success: true,
      snapshotId: data.snapshot_id,
      savedAt: data.saved_at,
    };
  } catch (e) {
    console.error('[services] saveResult failed:', e);
    return { success: false, error: e.message };
  }
}

/**
 * Legacy alias — now calls saveDecision via backend.
 * @param {import('../types/journey.js').DecisionSnapshot} snapshot
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function saveSnapshot(snapshot) {
  return saveDecision(snapshot);
}

// ── Journal Service ─────────────────────────────────────────────────────────

/**
 * Fetch saved decision records for the journal page.
 * @returns {Promise<Object[]>}
 */
export async function fetchJournalDecisions() {
  try {
    const res = await fetch(`${API_BASE}/journal/decisions`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return adaptJournalRecords(data);
  } catch (e) {
    console.warn('[services] fetchJournalDecisions failed:', e.message);
    return [];
  }
}

/**
 * Legacy alias for JournalPage backward compatibility.
 * @returns {Promise<Object[]>}
 */
export async function loadSnapshotIndex() {
  return fetchJournalDecisions();
}

/**
 * Load a specific snapshot by ID — stub, not needed for V1.1.
 * @param {string} snapshotId
 * @returns {Promise<null>}
 */
export async function loadSnapshot(snapshotId) {
  return null;
}

// ── Review Service ──────────────────────────────────────────────────────────

/**
 * Fetch review records from the backend.
 * @returns {Promise<Object[]>}
 */
export async function fetchReviewRecords() {
  try {
    const res = await fetch(`${API_BASE}/review/records`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return adaptReviewRecords(data);
  } catch (e) {
    console.warn('[services] fetchReviewRecords failed:', e.message);
    return [];
  }
}

/**
 * Legacy alias for ReviewPage.
 * @returns {Promise<Object>}
 */
export async function loadReviewPatterns() {
  const records = await fetchReviewRecords();
  return {
    records,
    overrideFrequency: [],
    gateFailureClusters: [],
    plannedVsActual: [],
  };
}

// ── Demo Data ───────────────────────────────────────────────────────────────

function _demoTriageResponse() {
  return {
    dataState: 'demo',
    items: _demoTriageItems().map(item => ({ ...item, _dataState: 'demo' })),
  };
}

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
      dataState: 'demo',
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
      dataState: 'demo',
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
      dataState: 'demo',
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
      dataState: 'demo',
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

  const bootstrap = adaptJourneyBootstrap(multiOutput, demoExplain, demoMacro);
  bootstrap.dataState = 'demo';
  return bootstrap;
}
