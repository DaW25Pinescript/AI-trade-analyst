import test from 'node:test';
import assert from 'node:assert/strict';

import { UNIFIED_EXPORT_VERSION } from '../app/scripts/exports/export_unified.js';
import { parseUnifiedPayload } from '../app/scripts/exports/import_unified.js';

// ---------------------------------------------------------------------------
// Minimal valid ticket / AAR fixtures (schema v4.0.0 / v1.0.0)
// ---------------------------------------------------------------------------
const VALID_TICKET = {
  schemaVersion: '4.0.0',
  ticketId: 'XAUUSD_260304_1200',
  createdAt: '2026-03-04T12:00:00.000Z',
  counterTrendMode: 'Mixed',
  decisionMode: 'LONG',
  ticketType: 'Zone ticket',
  entryType: 'Limit',
  entryTrigger: 'Pullback to zone',
  confirmationTF: '15m',
  timeInForce: 'This session',
  maxAttempts: 1,
  entry: { zone: '2640–2644', priceMin: 2640, priceMax: 2644, notes: '' },
  stop: { price: 2631, logic: 'Below swing low / above swing high', rationale: 'Below swing low' },
  targets: [
    { label: 'TP1', price: 2660, rationale: 'Prior reaction level' },
    { label: 'TP2', price: 2678, rationale: 'HTF resistance' }
  ],
  checklist: {
    htfState: 'Trending',
    htfLocation: 'At POI',
    ltfAlignment: 'Aligned',
    liquidityContext: 'Near obvious highs/lows',
    volRisk: 'Normal',
    execQuality: 'Clean',
    conviction: 'High',
    edgeTag: 'High-probability pullback',
    confluenceScore: 8
  },
  gate: { status: 'PROCEED', waitReasonCode: '', reentryCondition: '', reentryTime: '' },
  edgeScore: 72,
  psychologicalLeakR: 0,
  screenshots: {
    cleanCharts: [{ timeframe: 'H4', lens: 'NONE', evidenceType: 'price_only' }],
    m15Overlay: null
  },
  shadowMode: false,
  shadowOutcome: null
};

const VALID_AAR = {
  schemaVersion: '1.0.0',
  ticketId: 'XAUUSD_260304_1200',
  reviewedAt: '2026-03-04T16:00:00.000Z',
  outcomeEnum: 'WIN',
  verdictEnum: 'PLAN_FOLLOWED',
  firstTouch: false,
  wouldHaveWon: false,
  actualEntry: 2641,
  actualExit: 2660,
  rAchieved: 2.1,
  exitReasonEnum: 'TP_HIT',
  killSwitchTriggered: false,
  failureReasonCodes: [],
  psychologicalTag: 'CALM',
  revisedConfidence: 4,
  checklistDelta: { htfState: '', ltfAlignment: '', volRisk: '', execQuality: '', notes: '' },
  revisedTicket: {},
  notes: 'Clean trade, held to TP1.'
};

function makeValidUnified(overrides = {}) {
  return {
    exportVersion: UNIFIED_EXPORT_VERSION,
    exportFormat: 'unified',
    exportedAt: '2026-03-04T17:00:00.000Z',
    ticket: VALID_TICKET,
    aar: VALID_AAR,
    verdict: null,
    dashboardCharts: null,
    ...overrides
  };
}

// ---------------------------------------------------------------------------
// UNIFIED_EXPORT_VERSION
// ---------------------------------------------------------------------------

test('UNIFIED_EXPORT_VERSION is a positive integer', () => {
  assert.ok(Number.isInteger(UNIFIED_EXPORT_VERSION), 'UNIFIED_EXPORT_VERSION must be an integer');
  assert.ok(UNIFIED_EXPORT_VERSION >= 1, 'UNIFIED_EXPORT_VERSION must be >= 1');
});

// ---------------------------------------------------------------------------
// parseUnifiedPayload — rejection cases
// ---------------------------------------------------------------------------

test('parseUnifiedPayload rejects null', () => {
  const result = parseUnifiedPayload(null);
  assert.equal(result.ok, false);
  assert.ok(result.errors.length > 0, 'should return at least one error');
});

test('parseUnifiedPayload rejects a plain string', () => {
  const result = parseUnifiedPayload('not-an-object');
  assert.equal(result.ok, false);
});

test('parseUnifiedPayload rejects wrong exportFormat', () => {
  const payload = makeValidUnified({ exportFormat: 'backup' });
  const result = parseUnifiedPayload(payload);
  assert.equal(result.ok, false);
  assert.ok(result.errors.some(e => e.includes('unified')), 'error should mention "unified"');
});

test('parseUnifiedPayload rejects missing exportFormat', () => {
  const { exportFormat: _drop, ...payload } = makeValidUnified();
  const result = parseUnifiedPayload(payload);
  assert.equal(result.ok, false);
});

test('parseUnifiedPayload rejects a future exportVersion', () => {
  const payload = makeValidUnified({ exportVersion: UNIFIED_EXPORT_VERSION + 10 });
  const result = parseUnifiedPayload(payload);
  assert.equal(result.ok, false);
  assert.ok(result.errors.some(e => e.includes('version')), 'error should mention version');
});

test('parseUnifiedPayload rejects invalid ticket (bad schemaVersion)', () => {
  const payload = makeValidUnified({
    ticket: { ...VALID_TICKET, schemaVersion: '1.0.0' }
  });
  const result = parseUnifiedPayload(payload);
  assert.equal(result.ok, false);
  assert.ok(result.errors.some(e => e.includes('schemaVersion') || e.includes('4.0.0')));
});

test('parseUnifiedPayload rejects invalid AAR (bad outcomeEnum)', () => {
  const payload = makeValidUnified({
    aar: { ...VALID_AAR, outcomeEnum: 'INVALID_OUTCOME' }
  });
  const result = parseUnifiedPayload(payload);
  assert.equal(result.ok, false);
  assert.ok(result.errors.some(e => e.includes('outcomeEnum')));
});

// ---------------------------------------------------------------------------
// parseUnifiedPayload — acceptance cases
// ---------------------------------------------------------------------------

test('parseUnifiedPayload accepts a minimal valid unified payload (no verdict)', () => {
  const result = parseUnifiedPayload(makeValidUnified());
  assert.equal(result.ok, true, `Expected ok but got errors: ${result.errors?.join(', ')}`);
  assert.ok(result.payload, 'payload should be present');
  assert.equal(result.payload.ticket.ticketId, 'XAUUSD_260304_1200');
});

test('parseUnifiedPayload accepts a unified payload with verdict data', () => {
  const verdict = {
    run_id: 'run-abc-123',
    analysedAt: '2026-03-04T12:05:00.000Z',
    source_ticket_id: 'XAUUSD_260304_1200',
    verdict: { decision: 'ENTER_LONG', overall_confidence: 0.82 },
    usage: { total_cost_usd: 0.04 }
  };
  const result = parseUnifiedPayload(makeValidUnified({ verdict }));
  assert.equal(result.ok, true);
  // verdict is pass-through — validation doesn't enforce its internal schema
});

test('parseUnifiedPayload accepts a unified payload with dashboardCharts', () => {
  const dashboardCharts = {
    dashboardHeatmap: 'data:image/png;base64,abc123',
    dashboardEquityCurve: 'data:image/png;base64,def456'
  };
  const result = parseUnifiedPayload(makeValidUnified({ dashboardCharts }));
  assert.equal(result.ok, true);
});

test('parseUnifiedPayload migrates an older ticket (v3.0.0 → v4.0.0)', () => {
  const oldTicket = { ...VALID_TICKET, schemaVersion: '3.0.0' };
  delete oldTicket.shadowMode;
  delete oldTicket.shadowOutcome;

  const payload = makeValidUnified({ ticket: oldTicket });
  const result = parseUnifiedPayload(payload);
  // After migration the ticket should be at v4.0.0
  assert.equal(result.ok, true, `Migration failed: ${result.errors?.join(', ')}`);
  assert.equal(result.payload.ticket.schemaVersion, '4.0.0');
  assert.equal(result.payload.ticket.shadowMode, false);
  assert.equal(result.payload.ticket.shadowOutcome, null);
});

// ---------------------------------------------------------------------------
// export shape / version constant contract
// ---------------------------------------------------------------------------

test('UNIFIED_EXPORT_VERSION is exactly 1 (current schema rev)', () => {
  assert.equal(UNIFIED_EXPORT_VERSION, 1);
});
