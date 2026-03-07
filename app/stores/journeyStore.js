/**
 * Journey Store — Trade Ideation Journey v1
 *
 * Centralized state management for the trade ideation journey.
 * Separated from presentation. Components read from and dispatch to this store.
 *
 * Uses a simple pub/sub pattern suitable for vanilla JS.
 */

import {
  StageKey,
  STAGE_ORDER,
  JourneyStatus,
  GateState,
  Provenance,
  createEmptyJourneyState,
  createEmptyUserDecision,
  createEmptyExecutionPlan,
} from '../types/journey.js';

/** @type {import('../types/journey.js').JourneyState} */
let _state = createEmptyJourneyState();

/** @type {Set<Function>} */
const _listeners = new Set();

// ── Public API ──────────────────────────────────────────────────────────────

/** Subscribe to state changes. Returns unsubscribe function. */
export function subscribe(listener) {
  _listeners.add(listener);
  return () => _listeners.delete(listener);
}

/** Get current state (read-only copy). */
export function getState() {
  return { ..._state };
}

/** Get current stage key. */
export function getCurrentStage() {
  return _state.currentStage;
}

/** Get journey status. */
export function getJourneyStatus() {
  return _state.journeyStatus;
}

// ── Stage Navigation ────────────────────────────────────────────────────────

/** Set current stage by key. */
export function setStage(stageKey) {
  if (!STAGE_ORDER.includes(stageKey)) {
    console.warn(`[journeyStore] Unknown stage key: ${stageKey}`);
    return;
  }
  _state.currentStage = stageKey;
  _notify();
}

/** Advance to next stage. Respects gate policy. */
export function nextStage() {
  const idx = STAGE_ORDER.indexOf(_state.currentStage);
  if (idx < 0 || idx >= STAGE_ORDER.length - 1) return false;

  // Gate check enforcement: cannot advance past gate_checks if any gate is blocked
  if (_state.currentStage === StageKey.GATE_CHECKS) {
    if (hasBlockedGate()) {
      console.warn('[journeyStore] Forward progression blocked: gate check has blocked state.');
      return false;
    }
  }

  _state.currentStage = STAGE_ORDER[idx + 1];
  _notify();
  return true;
}

/** Go to previous stage. */
export function prevStage() {
  const idx = STAGE_ORDER.indexOf(_state.currentStage);
  if (idx <= 0) return false;
  _state.currentStage = STAGE_ORDER[idx - 1];
  _notify();
  return true;
}

// ── Asset Selection ─────────────────────────────────────────────────────────

/** Select an asset to begin a journey. */
export function selectAsset(symbol) {
  _state.selectedAsset = symbol;
  _state.journeyStatus = JourneyStatus.DRAFT;
  _notify();
}

// ── Triage ──────────────────────────────────────────────────────────────────

/** Set triage items (loaded from service layer). */
export function setTriageItems(items) {
  _state.triageItems = items;
  _notify();
}

// ── Stage Data ──────────────────────────────────────────────────────────────

/** Update data for a specific stage. */
export function setStageData(stageKey, data) {
  if (!STAGE_ORDER.includes(stageKey)) return;
  _state.stageData[stageKey] = data;
  _notify();
}

/** Get data for a specific stage. */
export function getStageData(stageKey) {
  return _state.stageData[stageKey];
}

// ── Notes and Evidence ──────────────────────────────────────────────────────

/** Set journal notes. */
export function setJournalNotes(notes) {
  _state.journalNotes = notes;
  _notify();
}

/** Add an evidence reference. */
export function addEvidence(ref) {
  _state.evidenceRefs = [..._state.evidenceRefs, ref];
  _notify();
}

/** Remove an evidence reference. */
export function removeEvidence(ref) {
  _state.evidenceRefs = _state.evidenceRefs.filter(r => r !== ref);
  _notify();
}

// ── Gate Checks ─────────────────────────────────────────────────────────────

/** Set gate check items (from adapter or user interaction). */
export function setGateStates(gates) {
  _state.gateStates = gates;
  _updateJourneyStatusFromGates();
  _notify();
}

/** Update a single gate check state. */
export function updateGateState(gateId, newState, justification) {
  _state.gateStates = _state.gateStates.map(g => {
    if (g.id !== gateId) return g;
    return {
      ...g,
      state: newState,
      justification: newState !== GateState.PASSED ? (justification || g.justification) : undefined,
    };
  });
  _updateJourneyStatusFromGates();
  _notify();
}

/** Check if any gate is blocked. */
export function hasBlockedGate() {
  return _state.gateStates.some(g => g.state === GateState.BLOCKED);
}

/** Check if all gates are passed. */
export function allGatesPassed() {
  return _state.gateStates.length > 0 && _state.gateStates.every(g => g.state === GateState.PASSED);
}

// ── Verdict and Decision ────────────────────────────────────────────────────

/** Set system verdict (from backend data — read-only AI content). */
export function setSystemVerdict(verdict) {
  _state.systemVerdict = verdict;
  _notify();
}

/** Set user decision (human commitment — always user-owned). */
export function setUserDecision(decision) {
  _state.userDecision = {
    ...decision,
    provenance: Provenance.USER_MANUAL,
    decidedAt: new Date().toISOString(),
  };
  _notify();
}

/** Set execution plan (human commitment). */
export function setExecutionPlan(plan) {
  _state.executionPlan = {
    ...plan,
    provenance: Provenance.USER_MANUAL,
  };
  _notify();
}

// ── Snapshot ────────────────────────────────────────────────────────────────

/**
 * Freeze the current journey state into an immutable decision snapshot.
 * This is called at save time. The snapshot is not reconstructed later.
 * @returns {import('../types/journey.js').DecisionSnapshot}
 */
export function createSnapshot() {
  const snapshot = {
    snapshotId: _generateId(),
    instrument: _state.selectedAsset,
    frozenAt: new Date().toISOString(),
    journeyStatus: _state.journeyStatus,
    systemVerdict: _state.systemVerdict ? { ..._state.systemVerdict } : null,
    userDecision: _state.userDecision ? { ..._state.userDecision } : null,
    executionPlan: _state.executionPlan ? { ..._state.executionPlan } : null,
    gateStates: _state.gateStates.map(g => ({ ...g })),
    stageData: JSON.parse(JSON.stringify(_state.stageData)),
    digest: _state.stageData[StageKey.STRUCTURE_LIQUIDITY]?.digest || null,
    macroContext: _state.stageData[StageKey.MACRO_ALIGNMENT] || null,
    evidenceRefs: [..._state.evidenceRefs],
    journalNotes: _state.journalNotes || '',
  };

  _state.decisionSnapshot = snapshot;
  _state.journeyStatus = JourneyStatus.SAVED;
  _notify();
  return snapshot;
}

/** Get current snapshot preview (without freezing). */
export function getSnapshotPreview() {
  return {
    instrument: _state.selectedAsset,
    journeyStatus: _state.journeyStatus,
    systemVerdict: _state.systemVerdict,
    userDecision: _state.userDecision,
    executionPlan: _state.executionPlan,
    gateStates: _state.gateStates,
    evidenceCount: _state.evidenceRefs.length,
    hasNotes: !!_state.journalNotes,
  };
}

// ── Journey Lifecycle ───────────────────────────────────────────────────────

/** Set journey status explicitly. */
export function setJourneyStatus(status) {
  _state.journeyStatus = status;
  _notify();
}

/** Reset the journey to a fresh state. */
export function resetJourney() {
  _state = createEmptyJourneyState();
  _notify();
}

/**
 * Bootstrap a journey with data from the service layer.
 * @param {Object} bootstrap - Pre-loaded data from journeyBootstrapAdapter
 */
export function bootstrapJourney(bootstrap) {
  _state.selectedAsset = bootstrap.instrument;
  _state.journeyStatus = JourneyStatus.DRAFT;
  _state.currentStage = StageKey.MARKET_OVERVIEW;

  if (bootstrap.stageData) {
    Object.entries(bootstrap.stageData).forEach(([key, data]) => {
      if (STAGE_ORDER.includes(key)) {
        _state.stageData[key] = data;
      }
    });
  }

  if (bootstrap.gateStates) {
    _state.gateStates = bootstrap.gateStates;
  }

  if (bootstrap.systemVerdict) {
    _state.systemVerdict = bootstrap.systemVerdict;
  }

  _notify();
}

// ── Internal Helpers ────────────────────────────────────────────────────────

function _notify() {
  _listeners.forEach(fn => {
    try { fn(_state); } catch (e) { console.error('[journeyStore] Listener error:', e); }
  });
}

function _updateJourneyStatusFromGates() {
  if (hasBlockedGate()) {
    _state.journeyStatus = JourneyStatus.BLOCKED;
  } else if (_state.journeyStatus === JourneyStatus.BLOCKED) {
    _state.journeyStatus = JourneyStatus.DRAFT;
  }
}

function _generateId() {
  return `snap_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}
