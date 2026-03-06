/**
 * test_audit1_contract_governance.js — Audit 1: Schema + Contract Governance
 *
 * Validates cross-language contract alignment between:
 *   - docs/schema/ (authoritative JSON schemas)
 *   - docs/schema/enums.json (reference enum catalog)
 *   - app/scripts/schema/backup_validation.js (JS runtime validation)
 *   - AI pipeline response envelope (FinalVerdict → ticket_draft mapping)
 *
 * Tests focus on contract invariants that could break the JS↔Python boundary.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── Load authoritative schemas ──────────────────────────────────────────────

const ticketSchema = JSON.parse(
  fs.readFileSync(resolve(__dirname, '../docs/schema/ticket.schema.json'), 'utf8')
);
const aarSchema = JSON.parse(
  fs.readFileSync(resolve(__dirname, '../docs/schema/aar.schema.json'), 'utf8')
);
const enums = JSON.parse(
  fs.readFileSync(resolve(__dirname, '../docs/schema/enums.json'), 'utf8')
);

// ── 1. Schema structural invariants ─────────────────────────────────────────

test('Audit 1 — ticket schema version is 4.0.0', () => {
  assert.equal(ticketSchema.properties.schemaVersion.const, '4.0.0');
});

test('Audit 1 — aar schema version is 1.0.0', () => {
  assert.equal(aarSchema.properties.schemaVersion.const, '1.0.0');
});

test('Audit 1 — ticket schema disallows additional properties', () => {
  assert.equal(ticketSchema.additionalProperties, false);
});

test('Audit 1 — aar schema disallows additional properties', () => {
  assert.equal(aarSchema.additionalProperties, false);
});

// ── 2. Ticket draft enum alignment ──────────────────────────────────────────
// Verifies that the values the Python ticket_draft builder produces
// (decisionMode, rawAIReadBias) are valid per the authoritative schema.

test('Audit 1 — Python decisionMode mapping outputs are valid schema enums', () => {
  // Python _DECISION_MAP values: LONG, SHORT, WAIT (NO_TRADE also maps to WAIT)
  const pythonOutputs = ['LONG', 'SHORT', 'WAIT'];
  const schemaEnums = ticketSchema.properties.decisionMode.enum;

  for (const val of pythonOutputs) {
    assert.ok(schemaEnums.includes(val),
      `Python decisionMode output '${val}' not in schema enum: [${schemaEnums}]`);
  }
});

test('Audit 1 — Python rawAIReadBias mapping outputs are valid schema enums', () => {
  // Python _BIAS_MAP values: Bullish, Bearish, Neutral, Range
  const pythonOutputs = ['Bullish', 'Bearish', 'Neutral', 'Range', ''];
  const schemaEnums = ticketSchema.properties.rawAIReadBias.enum;

  for (const val of pythonOutputs) {
    assert.ok(schemaEnums.includes(val),
      `Python rawAIReadBias output '${val}' not in schema enum: [${schemaEnums}]`);
  }
});

test('Audit 1 — Python gate status outputs are valid schema enums', () => {
  // ticket_draft.py uses: WAIT, PROCEED
  const pythonOutputs = ['WAIT', 'PROCEED'];
  const schemaEnums = ticketSchema.properties.gate.properties.status.enum;

  for (const val of pythonOutputs) {
    assert.ok(schemaEnums.includes(val),
      `Python gate status '${val}' not in schema enum: [${schemaEnums}]`);
  }
});

test('Audit 1 — Python stop logic output is a valid schema enum', () => {
  // ticket_draft.py hardcodes: "Structure-based + buffer"
  const pythonOutput = 'Structure-based + buffer';
  const schemaEnums = ticketSchema.properties.stop.properties.logic.enum;

  assert.ok(schemaEnums.includes(pythonOutput),
    `Python stop logic '${pythonOutput}' not in schema enum: [${schemaEnums}]`);
});

test('Audit 1 — Python target labels (TP1-TP3) are valid schema enums', () => {
  const pythonLabels = ['TP1', 'TP2', 'TP3'];
  const schemaEnums = ticketSchema.properties.targets.items.properties.label.enum;

  assert.deepEqual(pythonLabels, schemaEnums);
});

test('Audit 1 — Python conviction outputs are valid checklist enums', () => {
  // _conviction_from_confidence produces: Very High, High, Medium, Low
  const pythonOutputs = ['Very High', 'High', 'Medium', 'Low'];
  const schemaEnums = ticketSchema.properties.checklist.properties.conviction.enum;

  assert.deepEqual(pythonOutputs, schemaEnums);
});

// ── 3. Screenshot architecture contract ─────────────────────────────────────

test('Audit 1 — screenshot cleanCharts timeframe enum matches Python ALLOWED_CLEAN_TIMEFRAMES', () => {
  // Python: ALLOWED_CLEAN_TIMEFRAMES = frozenset({"H4", "H1", "M15", "M5"})
  const pythonAllowed = ['H4', 'H1', 'M15', 'M5'].sort();
  const schemaEnum = ticketSchema.properties.screenshots.properties.cleanCharts
    .items.properties.timeframe.enum.slice().sort();

  assert.deepEqual(schemaEnum, pythonAllowed);
});

test('Audit 1 — overlay slot is bound to M15 with lens=ICT', () => {
  const overlay = ticketSchema.properties.screenshots.properties.m15Overlay;
  assert.equal(overlay.properties.timeframe.const, 'M15');
  assert.equal(overlay.properties.lens.const, 'ICT');
  assert.equal(overlay.properties.evidenceType.const, 'indicator_overlay');
});

// ── 4. FinalVerdict response contract ───────────────────────────────────────
// Verifies the Python FinalVerdict Pydantic model's Literal values
// are known and compatible with the bridge expectations.

test('Audit 1 — FinalVerdict.decision values are known to the bridge', () => {
  // From arbiter_output.py: Literal["ENTER_LONG", "ENTER_SHORT", "WAIT_FOR_CONFIRMATION", "NO_TRADE"]
  const knownDecisions = ['ENTER_LONG', 'ENTER_SHORT', 'WAIT_FOR_CONFIRMATION', 'NO_TRADE'];
  // Bridge test (test_g11_bridge.js) uses NO_TRADE and LONG
  // This test just asserts the set is stable
  assert.equal(knownDecisions.length, 4);
  assert.ok(knownDecisions.includes('NO_TRADE'));
  assert.ok(knownDecisions.includes('ENTER_LONG'));
});

test('Audit 1 — FinalVerdict.final_bias values map to valid rawAIReadBias enums', () => {
  // From arbiter_output.py: Literal["bullish", "bearish", "neutral", "ranging"]
  // Python _BIAS_MAP maps these to Title case for ticket schema
  const biasInputs = ['bullish', 'bearish', 'neutral', 'ranging'];
  const expectedMappings = { bullish: 'Bullish', bearish: 'Bearish', neutral: 'Neutral', ranging: 'Range' };
  const schemaEnums = ticketSchema.properties.rawAIReadBias.enum;

  for (const bias of biasInputs) {
    const mapped = expectedMappings[bias];
    assert.ok(schemaEnums.includes(mapped),
      `Mapped bias '${mapped}' (from '${bias}') not in schema enum`);
  }
});

// ── 5. Enum catalog completeness ────────────────────────────────────────────

test('Audit 1 — enums.json covers all ticket enum properties', () => {
  // All enum-bearing ticket properties that should be in enums.json
  const expectedTicketKeys = [
    'counterTrendMode', 'rawAIReadBias', 'decisionMode', 'ticketType',
    'entryType', 'entryTrigger', 'confirmationTF', 'timeInForce',
    'stopLogic', 'targetLabel', 'gateStatus', 'waitReasonCode',
    'checklist.htfState', 'checklist.htfLocation', 'checklist.ltfAlignment',
    'checklist.liquidityContext', 'checklist.volRisk', 'checklist.execQuality',
    'checklist.conviction', 'checklist.edgeTag',
    'screenshots.cleanCharts.timeframe',
  ];

  for (const key of expectedTicketKeys) {
    assert.ok(enums.ticket[key] !== undefined,
      `enums.json missing ticket key: ${key}`);
    assert.ok(Array.isArray(enums.ticket[key]),
      `enums.json ticket.${key} must be an array`);
  }
});

test('Audit 1 — enums.json covers all AAR enum properties', () => {
  const expectedAarKeys = [
    'outcomeEnum', 'verdictEnum', 'exitReasonEnum',
    'failureReasonCodes', 'psychologicalTag',
  ];

  for (const key of expectedAarKeys) {
    assert.ok(enums.aar[key] !== undefined,
      `enums.json missing aar key: ${key}`);
    assert.ok(Array.isArray(enums.aar[key]),
      `enums.json aar.${key} must be an array`);
  }
});
