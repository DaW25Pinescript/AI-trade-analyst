import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const ticketSchema = JSON.parse(fs.readFileSync(new URL('../docs/schema/ticket.schema.json', import.meta.url), 'utf8'));
const aarSchema = JSON.parse(fs.readFileSync(new URL('../docs/schema/aar.schema.json', import.meta.url), 'utf8'));

const expectedTicketEnums = {
  decisionMode: ['LONG', 'SHORT', 'WAIT', 'CONDITIONAL'],
  ticketType: ['Zone ticket', 'Exact ticket'],
  entryType: ['Market', 'Limit', 'Stop'],
  entryTrigger: ['Pullback to zone', 'Break + retest', 'Sweep + reclaim', 'Close above/below level', 'Momentum shift (MSS/BOS)'],
  confirmationTF: ['1m', '5m', '15m', '1H'],
  timeInForce: ['This session', 'Next 1H', '24H', 'Custom'],
  stopLogic: ['Below swing low / above swing high', 'Below zone', 'ATR-based', 'Structure-based + buffer'],
  targetLabel: ['TP1', 'TP2', 'TP3'],
  gateStatus: ['INCOMPLETE', 'PROCEED', 'CAUTION', 'WAIT'],
  waitReasonCode: ['', 'Chop / range noise', 'HTF-LTF conflict', 'No POI / poor R:R', 'News risk / volatility', 'Already moved / late trend']
};

const expectedAarEnums = {
  outcomeEnum: ['WIN', 'LOSS', 'BREAKEVEN', 'MISSED', 'SCRATCH'],
  verdictEnum: ['PLAN_FOLLOWED', 'PLAN_VIOLATION', 'PROCESS_GOOD', 'PROCESS_POOR'],
  exitReasonEnum: ['TP_HIT', 'SL_HIT', 'TIME_EXIT', 'MANUAL_EXIT', 'INVALIDATION', 'NO_FILL'],
  failureReasonCodes: ['LATE_ENTRY', 'OVERSIZED_RISK', 'IGNORED_GATE', 'MISREAD_STRUCTURE', 'NEWS_BLINDSPOT', 'EMOTIONAL_EXECUTION', 'NO_EDGE'],
  psychologicalTag: ['CALM', 'FOMO', 'HESITATION', 'REVENGE', 'OVERCONFIDENCE', 'FATIGUE', 'DISCIPLINED']
};

test('ticket schema enum sets remain unchanged', () => {
  assert.deepEqual(ticketSchema.properties.decisionMode.enum, expectedTicketEnums.decisionMode);
  assert.deepEqual(ticketSchema.properties.ticketType.enum, expectedTicketEnums.ticketType);
  assert.deepEqual(ticketSchema.properties.entryType.enum, expectedTicketEnums.entryType);
  assert.deepEqual(ticketSchema.properties.entryTrigger.enum, expectedTicketEnums.entryTrigger);
  assert.deepEqual(ticketSchema.properties.confirmationTF.enum, expectedTicketEnums.confirmationTF);
  assert.deepEqual(ticketSchema.properties.timeInForce.enum, expectedTicketEnums.timeInForce);
  assert.deepEqual(ticketSchema.properties.stop.properties.logic.enum, expectedTicketEnums.stopLogic);
  assert.deepEqual(ticketSchema.properties.targets.items.properties.label.enum, expectedTicketEnums.targetLabel);
  assert.deepEqual(ticketSchema.properties.gate.properties.status.enum, expectedTicketEnums.gateStatus);
  assert.deepEqual(ticketSchema.properties.gate.properties.waitReasonCode.enum, expectedTicketEnums.waitReasonCode);
});

test('aar schema enum sets remain unchanged', () => {
  assert.deepEqual(aarSchema.properties.outcomeEnum.enum, expectedAarEnums.outcomeEnum);
  assert.deepEqual(aarSchema.properties.verdictEnum.enum, expectedAarEnums.verdictEnum);
  assert.deepEqual(aarSchema.properties.exitReasonEnum.enum, expectedAarEnums.exitReasonEnum);
  assert.deepEqual(aarSchema.properties.failureReasonCodes.items.enum, expectedAarEnums.failureReasonCodes);
  assert.deepEqual(aarSchema.properties.psychologicalTag.enum, expectedAarEnums.psychologicalTag);
});
