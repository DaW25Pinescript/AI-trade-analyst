/**
 * G9 feature tests:
 *   - schema v4.0.0 constants
 *   - validateTicketPayload accepts/rejects shadowMode field
 *   - validateTicketPayload accepts/rejects shadowOutcome object
 *   - migrateState upgrades 3.0.0 → 4.0.0 with default shadow fields
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { TICKET_SCHEMA_VERSION, validateTicketPayload } from '../app/scripts/schema/backup_validation.js';
import { migrateState } from '../app/scripts/state/migrations.js';
import { AAR_SCHEMA_VERSION } from '../app/scripts/schema/backup_validation.js';

// ── Schema version ─────────────────────────────────────────────────────────────

test('TICKET_SCHEMA_VERSION is 4.0.0 for G9', () => {
  assert.equal(TICKET_SCHEMA_VERSION, '4.0.0');
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeMinimalTicket(overrides = {}) {
  return {
    schemaVersion: '4.0.0',
    ticketId: 'XAUUSD_260227_1000',
    createdAt: '2026-02-27T10:00:00.000Z',
    counterTrendMode: 'Mixed',
    decisionMode: 'LONG',
    ticketType: 'Zone ticket',
    entryType: 'Limit',
    entryTrigger: 'Pullback to zone',
    confirmationTF: '15m',
    timeInForce: 'This session',
    maxAttempts: 1,
    entry: { zone: '2900-2910', priceMin: 2900, priceMax: 2910, notes: '' },
    stop: { price: 2880, logic: 'Below swing low / above swing high', rationale: 'Swing low' },
    targets: [{ label: 'TP1', price: 2940, rationale: 'Supply zone' }],
    checklist: {
      htfState: 'Trending', htfLocation: 'At POI', ltfAlignment: 'Aligned',
      liquidityContext: 'Equilibrium', volRisk: 'Normal', execQuality: 'Clean',
      conviction: 'High', edgeTag: 'High-probability pullback', confluenceScore: 8
    },
    gate: { status: 'PROCEED', waitReasonCode: '', reentryCondition: '', reentryTime: '' },
    edgeScore: 0.75,
    psychologicalLeakR: 0,
    screenshots: { cleanCharts: [{ timeframe: 'H4', lens: 'NONE', evidenceType: 'price_only' }], m15Overlay: null },
    ...overrides
  };
}

// ── shadowMode field validation ───────────────────────────────────────────────

test('validateTicketPayload accepts ticket without shadowMode (field is optional)', () => {
  const result = validateTicketPayload(makeMinimalTicket());
  assert.ok(result.ok, result.errors.join(', '));
});

test('validateTicketPayload accepts shadowMode: false', () => {
  const result = validateTicketPayload(makeMinimalTicket({ shadowMode: false }));
  assert.ok(result.ok, result.errors.join(', '));
});

test('validateTicketPayload accepts shadowMode: true', () => {
  const result = validateTicketPayload(makeMinimalTicket({ shadowMode: true }));
  assert.ok(result.ok, result.errors.join(', '));
});

test('validateTicketPayload rejects shadowMode as non-boolean (string)', () => {
  const result = validateTicketPayload(makeMinimalTicket({ shadowMode: 'yes' }));
  assert.ok(!result.ok);
  assert.ok(result.errors.some(e => e.includes('shadowMode')));
});

test('validateTicketPayload rejects shadowMode as number', () => {
  const result = validateTicketPayload(makeMinimalTicket({ shadowMode: 1 }));
  assert.ok(!result.ok);
  assert.ok(result.errors.some(e => e.includes('shadowMode')));
});

// ── shadowOutcome null passthrough ────────────────────────────────────────────

test('validateTicketPayload accepts shadowOutcome: null', () => {
  const result = validateTicketPayload(makeMinimalTicket({ shadowMode: true, shadowOutcome: null }));
  assert.ok(result.ok, result.errors.join(', '));
});

// ── shadowOutcome object validation ──────────────────────────────────────────

function makeShadowOutcome(overrides = {}) {
  return {
    captureWindowHours: 24,
    outcomePrice: 2935.50,
    outcomeCapturedAt: '2026-02-28T10:00:00.000Z',
    hitTarget: true,
    hitStop: false,
    pnlR: 1.78,
    ...overrides
  };
}

test('validateTicketPayload accepts valid shadowOutcome with 24h window', () => {
  const result = validateTicketPayload(makeMinimalTicket({
    shadowMode: true,
    shadowOutcome: makeShadowOutcome()
  }));
  assert.ok(result.ok, result.errors.join(', '));
});

test('validateTicketPayload accepts valid shadowOutcome with 48h window', () => {
  const result = validateTicketPayload(makeMinimalTicket({
    shadowMode: true,
    shadowOutcome: makeShadowOutcome({ captureWindowHours: 48 })
  }));
  assert.ok(result.ok, result.errors.join(', '));
});

test('validateTicketPayload accepts shadowOutcome with null fields (outcome not yet recorded)', () => {
  const result = validateTicketPayload(makeMinimalTicket({
    shadowMode: true,
    shadowOutcome: makeShadowOutcome({
      outcomePrice: null,
      outcomeCapturedAt: null,
      hitTarget: null,
      hitStop: null,
      pnlR: null
    })
  }));
  assert.ok(result.ok, result.errors.join(', '));
});

test('validateTicketPayload rejects shadowOutcome with invalid captureWindowHours', () => {
  const result = validateTicketPayload(makeMinimalTicket({
    shadowMode: true,
    shadowOutcome: makeShadowOutcome({ captureWindowHours: 12 })
  }));
  assert.ok(!result.ok);
  assert.ok(result.errors.some(e => e.includes('captureWindowHours')));
});

test('validateTicketPayload rejects shadowOutcome with non-finite outcomePrice', () => {
  const result = validateTicketPayload(makeMinimalTicket({
    shadowMode: true,
    shadowOutcome: makeShadowOutcome({ outcomePrice: 'high' })
  }));
  assert.ok(!result.ok);
  assert.ok(result.errors.some(e => e.includes('outcomePrice')));
});

test('validateTicketPayload rejects shadowOutcome with invalid outcomeCapturedAt', () => {
  const result = validateTicketPayload(makeMinimalTicket({
    shadowMode: true,
    shadowOutcome: makeShadowOutcome({ outcomeCapturedAt: 'yesterday' })
  }));
  assert.ok(!result.ok);
  assert.ok(result.errors.some(e => e.includes('outcomeCapturedAt')));
});

test('validateTicketPayload rejects shadowOutcome.hitTarget as non-boolean non-null', () => {
  const result = validateTicketPayload(makeMinimalTicket({
    shadowMode: true,
    shadowOutcome: makeShadowOutcome({ hitTarget: 'yes' })
  }));
  assert.ok(!result.ok);
  assert.ok(result.errors.some(e => e.includes('hitTarget')));
});

test('validateTicketPayload rejects shadowOutcome.hitStop as non-boolean non-null', () => {
  const result = validateTicketPayload(makeMinimalTicket({
    shadowMode: true,
    shadowOutcome: makeShadowOutcome({ hitStop: 1 })
  }));
  assert.ok(!result.ok);
  assert.ok(result.errors.some(e => e.includes('hitStop')));
});

test('validateTicketPayload rejects shadowOutcome.pnlR as non-finite non-null', () => {
  const result = validateTicketPayload(makeMinimalTicket({
    shadowMode: true,
    shadowOutcome: makeShadowOutcome({ pnlR: NaN })
  }));
  assert.ok(!result.ok);
  assert.ok(result.errors.some(e => e.includes('pnlR')));
});

test('validateTicketPayload rejects shadowOutcome as non-object', () => {
  const result = validateTicketPayload(makeMinimalTicket({
    shadowMode: true,
    shadowOutcome: 'not-an-object'
  }));
  assert.ok(!result.ok);
  assert.ok(result.errors.some(e => e.includes('shadowOutcome')));
});

// ── Migration: 3.0.0 → 4.0.0 ─────────────────────────────────────────────────

test('migrateState upgrades ticket from 3.0.0 to 4.0.0 (G9 migration) adds shadow defaults', () => {
  const payload = {
    ticket: {
      schemaVersion: '3.0.0',
      decisionMode: 'LONG',
      edgeScore: 0.8,
      psychologicalLeakR: 0
    },
    aar: { schemaVersion: AAR_SCHEMA_VERSION }
  };

  const result = migrateState(payload);

  assert.notEqual(result, payload);
  assert.equal(result.ticket.schemaVersion, '4.0.0');
  assert.equal(result.ticket.shadowMode, false);
  assert.equal(result.ticket.shadowOutcome, null);
  // Existing fields preserved
  assert.equal(result.ticket.edgeScore, 0.8);
  assert.equal(result.ticket.decisionMode, 'LONG');
});

test('migrateState preserves existing shadowMode: true when upgrading from 3.0.0', () => {
  const payload = {
    ticket: {
      schemaVersion: '3.0.0',
      shadowMode: true,
      shadowOutcome: { captureWindowHours: 48, outcomePrice: null, outcomeCapturedAt: null, hitTarget: null, hitStop: null, pnlR: null }
    },
    aar: { schemaVersion: AAR_SCHEMA_VERSION }
  };

  const result = migrateState(payload);

  assert.equal(result.ticket.schemaVersion, '4.0.0');
  assert.equal(result.ticket.shadowMode, true);
  assert.equal(result.ticket.shadowOutcome.captureWindowHours, 48);
});

test('migrateState full chain: 1.1.0 → 4.0.0 includes shadow defaults', () => {
  const payload = {
    ticket: { schemaVersion: '1.1.0', decisionMode: 'SHORT' },
    aar: { schemaVersion: AAR_SCHEMA_VERSION }
  };

  const result = migrateState(payload);

  assert.equal(result.ticket.schemaVersion, '4.0.0');
  assert.equal(result.ticket.shadowMode, false);
  assert.equal(result.ticket.shadowOutcome, null);
  assert.equal(result.ticket.decisionMode, 'SHORT');
});
