const TICKET_SCHEMA_VERSION = '1.1.0';
const AAR_SCHEMA_VERSION = '1.0.0';

const enums = {
  decisionMode: ['LONG', 'SHORT', 'WAIT', 'CONDITIONAL'],
  ticketType: ['Zone ticket', 'Exact ticket'],
  entryType: ['Market', 'Limit', 'Stop'],
  entryTrigger: ['Pullback to zone', 'Break + retest', 'Sweep + reclaim', 'Close above/below level', 'Momentum shift (MSS/BOS)'],
  confirmationTF: ['1m', '5m', '15m', '1H'],
  timeInForce: ['This session', 'Next 1H', '24H', 'Custom'],
  stopLogic: ['Below swing low / above swing high', 'Below zone', 'ATR-based', 'Structure-based + buffer'],
  targetLabel: ['TP1', 'TP2', 'TP3'],
  gateStatus: ['INCOMPLETE', 'PROCEED', 'CAUTION', 'WAIT'],
  waitReasonCode: ['', 'Chop / range noise', 'HTF-LTF conflict', 'No POI / poor R:R', 'News risk / volatility', 'Already moved / late trend'],
  htfState: ['Trending', 'Ranging', 'Transition'],
  htfLocation: ['At POI', 'Mid-range', 'At extremes'],
  ltfAlignment: ['Aligned', 'Counter-trend', 'Mixed'],
  liquidityContext: ['Near obvious highs/lows', 'Equilibrium', 'None identified'],
  volRisk: ['Normal', 'Elevated'],
  execQuality: ['Clean', 'Messy', 'Chop'],
  conviction: ['Very High', 'High', 'Medium', 'Low'],
  edgeTag: ['High-probability pullback', 'Liquidity grab', 'FVG reclaim', 'Structure BOS', 'Range boundary', 'Other'],
  outcomeEnum: ['WIN', 'LOSS', 'BREAKEVEN', 'MISSED', 'SCRATCH'],
  verdictEnum: ['PLAN_FOLLOWED', 'PLAN_VIOLATION', 'PROCESS_GOOD', 'PROCESS_POOR'],
  exitReasonEnum: ['TP_HIT', 'SL_HIT', 'TIME_EXIT', 'MANUAL_EXIT', 'INVALIDATION', 'NO_FILL'],
  failureReasonCodes: ['LATE_ENTRY', 'OVERSIZED_RISK', 'IGNORED_GATE', 'MISREAD_STRUCTURE', 'NEWS_BLINDSPOT', 'EMOTIONAL_EXECUTION', 'NO_EDGE'],
  psychologicalTag: ['CALM', 'FOMO', 'HESITATION', 'REVENGE', 'OVERCONFIDENCE', 'FATIGUE', 'DISCIPLINED']
};

function isFiniteNumber(v) {
  return typeof v === 'number' && Number.isFinite(v);
}

function isObject(v) {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function expectEnum(errors, path, value, allowed) {
  if (!allowed.includes(value)) errors.push(`${path} must be one of: ${allowed.join(', ')}`);
}

function expectString(errors, path, value, minLength = 0) {
  if (typeof value !== 'string' || value.length < minLength) errors.push(`${path} must be a string${minLength ? ` (min length ${minLength})` : ''}`);
}

function expectInteger(errors, path, value, min, max) {
  if (!Number.isInteger(value) || value < min || value > max) errors.push(`${path} must be an integer between ${min} and ${max}`);
}

function expectBoolean(errors, path, value) {
  if (typeof value !== 'boolean') errors.push(`${path} must be a boolean`);
}

export function validateTicketPayload(payload) {
  const errors = [];
  if (!isObject(payload)) return { ok: false, errors: ['ticket payload must be an object'] };

  expectString(errors, 'ticket.schemaVersion', payload.schemaVersion, 1);
  if (payload.schemaVersion !== TICKET_SCHEMA_VERSION) errors.push(`ticket.schemaVersion must equal ${TICKET_SCHEMA_VERSION}`);
  expectString(errors, 'ticket.ticketId', payload.ticketId, 1);
  expectString(errors, 'ticket.createdAt', payload.createdAt, 1);
  expectEnum(errors, 'ticket.decisionMode', payload.decisionMode, enums.decisionMode);
  expectEnum(errors, 'ticket.ticketType', payload.ticketType, enums.ticketType);
  expectEnum(errors, 'ticket.entryType', payload.entryType, enums.entryType);
  expectEnum(errors, 'ticket.entryTrigger', payload.entryTrigger, enums.entryTrigger);
  expectEnum(errors, 'ticket.confirmationTF', payload.confirmationTF, enums.confirmationTF);
  expectEnum(errors, 'ticket.timeInForce', payload.timeInForce, enums.timeInForce);
  expectInteger(errors, 'ticket.maxAttempts', payload.maxAttempts, 1, 3);

  if (!isObject(payload.entry)) errors.push('ticket.entry must be an object');
  else {
    expectString(errors, 'ticket.entry.zone', payload.entry.zone, 1);
    if (!isFiniteNumber(payload.entry.priceMin)) errors.push('ticket.entry.priceMin must be a number');
    if (!isFiniteNumber(payload.entry.priceMax)) errors.push('ticket.entry.priceMax must be a number');
    expectString(errors, 'ticket.entry.notes', payload.entry.notes);
  }

  if (!isObject(payload.stop)) errors.push('ticket.stop must be an object');
  else {
    if (!isFiniteNumber(payload.stop.price)) errors.push('ticket.stop.price must be a number');
    expectEnum(errors, 'ticket.stop.logic', payload.stop.logic, enums.stopLogic);
    expectString(errors, 'ticket.stop.rationale', payload.stop.rationale, 1);
  }

  if (!Array.isArray(payload.targets) || payload.targets.length === 0) errors.push('ticket.targets must be a non-empty array');
  else {
    payload.targets.forEach((t, idx) => {
      if (!isObject(t)) {
        errors.push(`ticket.targets[${idx}] must be an object`);
        return;
      }
      expectEnum(errors, `ticket.targets[${idx}].label`, t.label, enums.targetLabel);
      if (!isFiniteNumber(t.price)) errors.push(`ticket.targets[${idx}].price must be a number`);
      expectString(errors, `ticket.targets[${idx}].rationale`, t.rationale, 1);
    });
  }

  const c = payload.checklist;
  if (!isObject(c)) errors.push('ticket.checklist must be an object');
  else {
    expectEnum(errors, 'ticket.checklist.htfState', c.htfState, enums.htfState);
    expectEnum(errors, 'ticket.checklist.htfLocation', c.htfLocation, enums.htfLocation);
    expectEnum(errors, 'ticket.checklist.ltfAlignment', c.ltfAlignment, enums.ltfAlignment);
    expectEnum(errors, 'ticket.checklist.liquidityContext', c.liquidityContext, enums.liquidityContext);
    expectEnum(errors, 'ticket.checklist.volRisk', c.volRisk, enums.volRisk);
    expectEnum(errors, 'ticket.checklist.execQuality', c.execQuality, enums.execQuality);
    expectEnum(errors, 'ticket.checklist.conviction', c.conviction, enums.conviction);
    expectEnum(errors, 'ticket.checklist.edgeTag', c.edgeTag, enums.edgeTag);
    expectInteger(errors, 'ticket.checklist.confluenceScore', c.confluenceScore, 1, 10);
  }

  const g = payload.gate;
  if (!isObject(g)) errors.push('ticket.gate must be an object');
  else {
    expectEnum(errors, 'ticket.gate.status', g.status, enums.gateStatus);
    expectEnum(errors, 'ticket.gate.waitReasonCode', g.waitReasonCode, enums.waitReasonCode);
    expectString(errors, 'ticket.gate.reentryCondition', g.reentryCondition);
    expectString(errors, 'ticket.gate.reentryTime', g.reentryTime);
  }

  return { ok: errors.length === 0, errors };
}

export function validateAARPayload(payload) {
  const errors = [];
  if (!isObject(payload)) return { ok: false, errors: ['aar payload must be an object'] };

  expectString(errors, 'aar.schemaVersion', payload.schemaVersion, 1);
  if (payload.schemaVersion !== AAR_SCHEMA_VERSION) errors.push(`aar.schemaVersion must equal ${AAR_SCHEMA_VERSION}`);
  expectString(errors, 'aar.ticketId', payload.ticketId, 1);
  expectString(errors, 'aar.reviewedAt', payload.reviewedAt, 1);
  expectEnum(errors, 'aar.outcomeEnum', payload.outcomeEnum, enums.outcomeEnum);
  expectEnum(errors, 'aar.verdictEnum', payload.verdictEnum, enums.verdictEnum);
  expectBoolean(errors, 'aar.firstTouch', payload.firstTouch);
  expectBoolean(errors, 'aar.wouldHaveWon', payload.wouldHaveWon);
  if (!isFiniteNumber(payload.actualEntry)) errors.push('aar.actualEntry must be a number');
  if (!isFiniteNumber(payload.actualExit)) errors.push('aar.actualExit must be a number');
  if (!isFiniteNumber(payload.rAchieved)) errors.push('aar.rAchieved must be a number');
  expectEnum(errors, 'aar.exitReasonEnum', payload.exitReasonEnum, enums.exitReasonEnum);
  expectBoolean(errors, 'aar.killSwitchTriggered', payload.killSwitchTriggered);

  if (!Array.isArray(payload.failureReasonCodes)) errors.push('aar.failureReasonCodes must be an array');
  else {
    payload.failureReasonCodes.forEach((code, idx) => expectEnum(errors, `aar.failureReasonCodes[${idx}]`, code, enums.failureReasonCodes));
  }

  expectEnum(errors, 'aar.psychologicalTag', payload.psychologicalTag, enums.psychologicalTag);
  expectInteger(errors, 'aar.revisedConfidence', payload.revisedConfidence, 1, 5);

  if (!isObject(payload.checklistDelta)) errors.push('aar.checklistDelta must be an object');
  else {
    expectString(errors, 'aar.checklistDelta.htfState', payload.checklistDelta.htfState);
    expectString(errors, 'aar.checklistDelta.ltfAlignment', payload.checklistDelta.ltfAlignment);
    expectString(errors, 'aar.checklistDelta.volRisk', payload.checklistDelta.volRisk);
    expectString(errors, 'aar.checklistDelta.execQuality', payload.checklistDelta.execQuality);
    expectString(errors, 'aar.checklistDelta.notes', payload.checklistDelta.notes);
  }

  expectString(errors, 'aar.notes', payload.notes, 1);

  return { ok: errors.length === 0, errors };
}

export { TICKET_SCHEMA_VERSION, AAR_SCHEMA_VERSION };
