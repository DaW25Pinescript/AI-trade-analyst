/**
 * Regression tests for v2.0.2 fixes: MED-8 (m15Overlay shape validation).
 *
 * MED-8: backup_validation.js previously rejected any non-null m15Overlay with
 * a hard error "must be null until typed overlay metadata is captured in UI".
 * This blocked the G11 overlay feature at the schema validation level.
 *
 * Fix: the guard is replaced with shape validation that accepts a typed overlay
 * metadata object and rejects primitives, empty arrays, or malformed objects.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { validateTicketPayload } from '../app/scripts/schema/backup_validation.js';

// ── Minimal valid ticket helper ───────────────────────────────────────────────

function minimalTicket(overrides = {}) {
  return {
    schemaVersion: '4.0.0',
    ticketId: 'TKT-001',
    createdAt: '2026-01-01T00:00:00Z',
    counterTrendMode: 'Strict HTF-only',
    decisionMode: 'LONG',
    ticketType: 'Zone ticket',
    entryType: 'Limit',
    entryTrigger: 'Pullback to zone',
    confirmationTF: '15m',
    timeInForce: 'This session',
    maxAttempts: 1,
    entry: { zone: 'FVG 2010-2015', priceMin: 2010, priceMax: 2015, notes: '' },
    stop: { price: 1990, logic: 'Below swing low / above swing high', rationale: 'Below swing' },
    targets: [{ label: 'TP1', price: 2050, rationale: 'EQH' }],
    checklist: {
      htfState: 'Trending',
      htfLocation: 'At POI',
      ltfAlignment: 'Aligned',
      liquidityContext: 'Near obvious highs/lows',
      volRisk: 'Normal',
      execQuality: 'Clean',
      conviction: 'High',
      edgeTag: 'Liquidity grab',
      confluenceScore: 7,
    },
    gate: { status: 'PROCEED', waitReasonCode: '', reentryCondition: '', reentryTime: '' },
    edgeScore: 0.72,
    psychologicalLeakR: 0,
    screenshots: {
      cleanCharts: [
        { timeframe: 'H4', lens: 'NONE', evidenceType: 'price_only' },
      ],
      m15Overlay: null,
    },
    ...overrides,
  };
}

// ── MED-8 tests ───────────────────────────────────────────────────────────────

test('validateTicketPayload accepts m15Overlay: null (no overlay used)', () => {
  const result = validateTicketPayload(minimalTicket());
  assert.ok(result.ok, `Expected valid ticket but got errors: ${result.errors.join('; ')}`);
});

test('validateTicketPayload accepts a well-formed m15Overlay metadata object', () => {
  const ticket = minimalTicket({
    screenshots: {
      cleanCharts: [{ timeframe: 'M15', lens: 'NONE', evidenceType: 'price_only' }],
      m15Overlay: {
        timeframe: 'M15',
        lens: 'ICT_CCT',
        evidenceType: 'indicator_overlay',
        indicatorClaims: ['FVG', 'OrderBlock'],
        indicatorSource: 'TradingView',
        settingsLocked: true,
      },
    },
  });
  const result = validateTicketPayload(ticket);
  assert.ok(result.ok, `Expected valid ticket with overlay but got errors: ${result.errors.join('; ')}`);
});

test('validateTicketPayload rejects m15Overlay as a non-object (string)', () => {
  const ticket = minimalTicket({
    screenshots: {
      cleanCharts: [{ timeframe: 'H4', lens: 'NONE', evidenceType: 'price_only' }],
      m15Overlay: 'should-not-be-a-string',
    },
  });
  const result = validateTicketPayload(ticket);
  assert.equal(result.ok, false);
  assert.ok(
    result.errors.some(e => e.includes('m15Overlay') && e.includes('object')),
    `Expected m15Overlay shape error; got: ${result.errors.join('; ')}`
  );
});

test('validateTicketPayload rejects m15Overlay missing required indicatorClaims', () => {
  const ticket = minimalTicket({
    screenshots: {
      cleanCharts: [{ timeframe: 'H4', lens: 'NONE', evidenceType: 'price_only' }],
      m15Overlay: {
        timeframe: 'M15',
        lens: 'ICT_CCT',
        evidenceType: 'indicator_overlay',
        indicatorClaims: [],   // empty — invalid
        indicatorSource: 'TradingView',
        settingsLocked: true,
      },
    },
  });
  const result = validateTicketPayload(ticket);
  assert.equal(result.ok, false);
  assert.ok(
    result.errors.some(e => e.includes('indicatorClaims')),
    `Expected indicatorClaims error; got: ${result.errors.join('; ')}`
  );
});

test('validateTicketPayload rejects m15Overlay with wrong timeframe', () => {
  const ticket = minimalTicket({
    screenshots: {
      cleanCharts: [{ timeframe: 'H4', lens: 'NONE', evidenceType: 'price_only' }],
      m15Overlay: {
        timeframe: 'H4',   // should be M15
        lens: 'ICT_CCT',
        evidenceType: 'indicator_overlay',
        indicatorClaims: ['FVG'],
        indicatorSource: 'TradingView',
        settingsLocked: true,
      },
    },
  });
  const result = validateTicketPayload(ticket);
  assert.equal(result.ok, false);
  assert.ok(
    result.errors.some(e => e.includes('m15Overlay.timeframe') && e.includes('M15')),
    `Expected timeframe error; got: ${result.errors.join('; ')}`
  );
});

test('validateTicketPayload rejects m15Overlay with wrong evidenceType', () => {
  const ticket = minimalTicket({
    screenshots: {
      cleanCharts: [{ timeframe: 'H4', lens: 'NONE', evidenceType: 'price_only' }],
      m15Overlay: {
        timeframe: 'M15',
        lens: 'ICT_CCT',
        evidenceType: 'price_only',  // should be indicator_overlay
        indicatorClaims: ['FVG'],
        indicatorSource: 'TradingView',
        settingsLocked: true,
      },
    },
  });
  const result = validateTicketPayload(ticket);
  assert.equal(result.ok, false);
  assert.ok(
    result.errors.some(e => e.includes('evidenceType') && e.includes('indicator_overlay')),
    `Expected evidenceType error; got: ${result.errors.join('; ')}`
  );
});

test('validateTicketPayload rejects m15Overlay when settingsLocked is not boolean', () => {
  const ticket = minimalTicket({
    screenshots: {
      cleanCharts: [{ timeframe: 'H4', lens: 'NONE', evidenceType: 'price_only' }],
      m15Overlay: {
        timeframe: 'M15',
        lens: 'ICT_CCT',
        evidenceType: 'indicator_overlay',
        indicatorClaims: ['FVG'],
        indicatorSource: 'TradingView',
        settingsLocked: 'yes',  // should be boolean
      },
    },
  });
  const result = validateTicketPayload(ticket);
  assert.equal(result.ok, false);
  assert.ok(
    result.errors.some(e => e.includes('settingsLocked') && e.includes('boolean')),
    `Expected settingsLocked type error; got: ${result.errors.join('; ')}`
  );
});

// Verify old "must be null" guard is gone — non-null overlay no longer produces
// the old blocking error message.
test('validateTicketPayload does not emit the old blocking null-guard error for valid overlay', () => {
  const ticket = minimalTicket({
    screenshots: {
      cleanCharts: [{ timeframe: 'M15', lens: 'NONE', evidenceType: 'price_only' }],
      m15Overlay: {
        timeframe: 'M15',
        lens: 'ICT_CCT',
        evidenceType: 'indicator_overlay',
        indicatorClaims: ['SessionLiquidity'],
        indicatorSource: 'TradingView',
        settingsLocked: false,
      },
    },
  });
  const result = validateTicketPayload(ticket);
  const oldGuardError = result.errors.find(e => e.includes('until typed overlay metadata'));
  assert.ok(!oldGuardError, `Old blocking error should be gone; got: ${oldGuardError}`);
});
