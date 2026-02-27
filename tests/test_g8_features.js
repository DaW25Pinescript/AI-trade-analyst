/**
 * G8 feature tests:
 *   - schema v3.0.0 constants
 *   - validateTicketPayload accepts optional aiEdgeScore / revisedFromId
 *   - buildWeeklyPrompt auto-populates trade data and pre-computed stats
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { TICKET_SCHEMA_VERSION, validateTicketPayload } from '../app/scripts/schema/backup_validation.js';

// ── Schema version ────────────────────────────────────────────────────────────

test('TICKET_SCHEMA_VERSION is 4.0.0 (G8 features remain in current schema)', () => {
  assert.equal(TICKET_SCHEMA_VERSION, '4.0.0');
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeMinimalTicket(overrides = {}) {
  return {
    schemaVersion: '4.0.0',
    ticketId: 'XAUUSD_260224_0930',
    createdAt: '2026-02-24T09:30:00.000Z',
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

// ── validateTicketPayload: optional G8 fields ─────────────────────────────────

test('validateTicketPayload accepts ticket without G8 optional fields', () => {
  const result = validateTicketPayload(makeMinimalTicket());
  assert.ok(result.ok, result.errors.join(', '));
});

test('validateTicketPayload accepts valid aiEdgeScore (0.0–1.0)', () => {
  const result = validateTicketPayload(makeMinimalTicket({ aiEdgeScore: 0.72 }));
  assert.ok(result.ok, result.errors.join(', '));
});

test('validateTicketPayload accepts aiEdgeScore at boundary values 0 and 1', () => {
  assert.ok(validateTicketPayload(makeMinimalTicket({ aiEdgeScore: 0 })).ok);
  assert.ok(validateTicketPayload(makeMinimalTicket({ aiEdgeScore: 1 })).ok);
});

test('validateTicketPayload rejects aiEdgeScore outside 0–1', () => {
  const low  = validateTicketPayload(makeMinimalTicket({ aiEdgeScore: -0.1 }));
  const high = validateTicketPayload(makeMinimalTicket({ aiEdgeScore: 1.5 }));
  assert.ok(!low.ok);
  assert.ok(!high.ok);
  assert.ok(low.errors.some(e => e.includes('aiEdgeScore')));
});

test('validateTicketPayload accepts valid revisedFromId string', () => {
  const result = validateTicketPayload(makeMinimalTicket({ revisedFromId: 'XAUUSD_260224_0930' }));
  assert.ok(result.ok, result.errors.join(', '));
});

test('validateTicketPayload rejects empty revisedFromId string', () => {
  const result = validateTicketPayload(makeMinimalTicket({ revisedFromId: '' }));
  assert.ok(!result.ok);
  assert.ok(result.errors.some(e => e.includes('revisedFromId')));
});

// ── buildWeeklyPrompt: data-driven behaviour ──────────────────────────────────

// Since buildWeeklyPrompt reads from DOM (document.getElementById), we patch it.
// The helper functions are pure, so we test the module-private logic via the exported function
// with a minimal DOM stub.

const { buildWeeklyPrompt } = await import('../app/scripts/generators/prompt_weekly.js');

// Provide a minimal DOM stub so the module can run without a browser
global.document = { getElementById: () => null };

test('buildWeeklyPrompt with no entries returns placeholder row', () => {
  const prompt = buildWeeklyPrompt([]);
  assert.ok(prompt.includes('No trade data loaded'));
  assert.ok(prompt.includes('WEEKLY REVIEW PROMPT'));
});

test('buildWeeklyPrompt with entries includes trade row data', () => {
  const entries = [
    {
      ticket: {
        ticketId: 'XAUUSD_260224_0930',
        decisionMode: 'LONG',
        createdAt: new Date().toISOString(), // today — within 7 days
        checklist: { edgeTag: 'Liquidity grab', confluenceScore: 8 },
        gate: { status: 'PROCEED' }
      },
      aar: { outcomeEnum: 'WIN', rAchieved: 1.5, revisedConfidence: 4, notes: 'Clean sweep and reverse.' }
    }
  ];

  const prompt = buildWeeklyPrompt(entries);
  assert.ok(prompt.includes('XAUUSD_260224_0930'));
  assert.ok(prompt.includes('LONG'));
  assert.ok(prompt.includes('WIN'));
  assert.ok(prompt.includes('+1.50'));
  assert.ok(prompt.includes('Liquidity grab'));
  assert.ok(prompt.includes('PROCEED'));
});

test('buildWeeklyPrompt includes pre-computed stats when closed trades exist', () => {
  const entries = [
    {
      ticket: { ticketId: 'A', decisionMode: 'LONG', createdAt: new Date().toISOString(), checklist: { edgeTag: 'Other', confluenceScore: 7 }, gate: { status: 'PROCEED' } },
      aar: { outcomeEnum: 'WIN', rAchieved: 2, revisedConfidence: 4, notes: 'Win' }
    },
    {
      ticket: { ticketId: 'B', decisionMode: 'SHORT', createdAt: new Date().toISOString(), checklist: { edgeTag: 'Other', confluenceScore: 6 }, gate: { status: 'CAUTION' } },
      aar: { outcomeEnum: 'LOSS', rAchieved: -1, revisedConfidence: 2, notes: 'Loss' }
    }
  ];

  const prompt = buildWeeklyPrompt(entries);
  // Stats block should appear
  assert.ok(prompt.includes('PRE-COMPUTED STATS'));
  assert.ok(prompt.includes('Win rate:'));
  assert.ok(prompt.includes('Avg R:'));
  assert.ok(prompt.includes('Net R:'));
});

test('buildWeeklyPrompt filters out entries older than 7 days', () => {
  const oldDate = new Date(Date.now() - 8 * 24 * 60 * 60 * 1000).toISOString();
  const entries = [
    {
      ticket: { ticketId: 'OLD_TICKET', decisionMode: 'LONG', createdAt: oldDate, checklist: { edgeTag: 'Other', confluenceScore: 5 }, gate: { status: 'WAIT' } },
      aar: { outcomeEnum: 'WIN', rAchieved: 1, revisedConfidence: 3, notes: 'Old' }
    }
  ];

  const prompt = buildWeeklyPrompt(entries);
  assert.ok(!prompt.includes('OLD_TICKET'));
  assert.ok(prompt.includes('No trade data loaded'));
});
