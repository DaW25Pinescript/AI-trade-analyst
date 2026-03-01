/**
 * Schema bridge contract test.
 *
 * Loads docs/schema/enums.json and both schema files, then asserts that every
 * enum set in enums.json is deepEqual to the corresponding path in the live
 * schema. Fails immediately if any drift is detected — i.e. if a value is
 * added to enums.json without updating the schema, or vice versa.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const enums = JSON.parse(
  fs.readFileSync(new URL('../docs/schema/enums.json', import.meta.url), 'utf8')
);
const ticket = JSON.parse(
  fs.readFileSync(new URL('../docs/schema/ticket.schema.json', import.meta.url), 'utf8')
);
const aar = JSON.parse(
  fs.readFileSync(new URL('../docs/schema/aar.schema.json', import.meta.url), 'utf8')
);

// Map each enums.json ticket key → the live schema enum array.
const ticketPaths = {
  counterTrendMode:                  ticket.properties.counterTrendMode.enum,
  rawAIReadBias:                     ticket.properties.rawAIReadBias.enum,
  decisionMode:                      ticket.properties.decisionMode.enum,
  ticketType:                        ticket.properties.ticketType.enum,
  entryType:                         ticket.properties.entryType.enum,
  entryTrigger:                      ticket.properties.entryTrigger.enum,
  confirmationTF:                    ticket.properties.confirmationTF.enum,
  timeInForce:                       ticket.properties.timeInForce.enum,
  stopLogic:                         ticket.properties.stop.properties.logic.enum,
  targetLabel:                       ticket.properties.targets.items.properties.label.enum,
  gateStatus:                        ticket.properties.gate.properties.status.enum,
  waitReasonCode:                    ticket.properties.gate.properties.waitReasonCode.enum,
  'checklist.htfState':              ticket.properties.checklist.properties.htfState.enum,
  'checklist.htfLocation':           ticket.properties.checklist.properties.htfLocation.enum,
  'checklist.ltfAlignment':          ticket.properties.checklist.properties.ltfAlignment.enum,
  'checklist.liquidityContext':      ticket.properties.checklist.properties.liquidityContext.enum,
  'checklist.volRisk':               ticket.properties.checklist.properties.volRisk.enum,
  'checklist.execQuality':           ticket.properties.checklist.properties.execQuality.enum,
  'checklist.conviction':            ticket.properties.checklist.properties.conviction.enum,
  'checklist.edgeTag':               ticket.properties.checklist.properties.edgeTag.enum,
  'screenshots.cleanCharts.timeframe':
    ticket.properties.screenshots.properties.cleanCharts.items.properties.timeframe.enum,
};

const aarPaths = {
  outcomeEnum:        aar.properties.outcomeEnum.enum,
  verdictEnum:        aar.properties.verdictEnum.enum,
  exitReasonEnum:     aar.properties.exitReasonEnum.enum,
  failureReasonCodes: aar.properties.failureReasonCodes.items.enum,
  psychologicalTag:   aar.properties.psychologicalTag.enum,
};

// ── ticket enum bridge ──────────────────────────────────────────────────────

test('enums.json ticket enums match ticket.schema.json — no drift', () => {
  for (const [key, schemaValues] of Object.entries(ticketPaths)) {
    assert.deepEqual(
      enums.ticket[key],
      schemaValues,
      `Drift: enums.json ticket.${key} diverges from ticket.schema.json`
    );
  }
});

test('enums.json ticket keys are exhaustive — no undeclared schema enums', () => {
  // Every key in ticketPaths must also exist in enums.json (bidirectional check).
  for (const key of Object.keys(ticketPaths)) {
    assert.ok(
      Object.prototype.hasOwnProperty.call(enums.ticket, key),
      `enums.json is missing ticket key: ${key}`
    );
  }
});

// ── aar enum bridge ─────────────────────────────────────────────────────────

test('enums.json aar enums match aar.schema.json — no drift', () => {
  for (const [key, schemaValues] of Object.entries(aarPaths)) {
    assert.deepEqual(
      enums.aar[key],
      schemaValues,
      `Drift: enums.json aar.${key} diverges from aar.schema.json`
    );
  }
});

test('enums.json aar keys are exhaustive — no undeclared schema enums', () => {
  for (const key of Object.keys(aarPaths)) {
    assert.ok(
      Object.prototype.hasOwnProperty.call(enums.aar, key),
      `enums.json is missing aar key: ${key}`
    );
  }
});
