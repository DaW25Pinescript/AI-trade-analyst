import { state } from '../state/model.js';
import { TICKET_SCHEMA_VERSION, AAR_SCHEMA_VERSION, validateTicketPayload, validateAARPayload } from '../schema/backup_validation.js';

function readTextInput(id, fallback = '') {
  const el = document.getElementById(id);
  return (el?.value || fallback).toString();
}

function readGateStatus() {
  const gateEl = document.getElementById('gateStatus');
  if (gateEl?.classList.contains('wait')) return 'WAIT';
  if (gateEl?.classList.contains('caution')) return 'CAUTION';
  if (gateEl?.classList.contains('proceed')) return 'PROCEED';
  return 'INCOMPLETE';
}

function buildTicketSnapshot() {
  const nowISO = new Date().toISOString();
  const minPrice = Number.parseFloat(readTextInput('priceNow', '0')) || 0;

  return {
    schemaVersion: TICKET_SCHEMA_VERSION,
    ticketId: state.ticketID || 'draft',
    createdAt: nowISO,
    decisionMode: readTextInput('waitReason') ? 'WAIT' : 'CONDITIONAL',
    ticketType: 'Zone ticket',
    entryType: 'Limit',
    entryTrigger: 'Pullback to zone',
    confirmationTF: '15m',
    timeInForce: 'This session',
    maxAttempts: 2,
    entry: {
      zone: readTextInput('levels', 'User-defined zone'),
      priceMin: minPrice,
      priceMax: minPrice,
      notes: readTextInput('position')
    },
    stop: {
      price: minPrice,
      logic: 'Below swing low / above swing high',
      rationale: readTextInput('maxStop', 'User-defined stop constraint')
    },
    targets: [
      { label: 'TP1', price: minPrice, rationale: 'Primary reaction level' },
      { label: 'TP2', price: minPrice, rationale: 'Extended move objective' }
    ],
    checklist: {
      htfState: state.ptcState.htfState || 'Transition',
      htfLocation: state.ptcState.htfLocation || 'Mid-range',
      ltfAlignment: state.ptcState.ltfAlignment || 'Mixed',
      liquidityContext: state.ptcState.liquidityContext || 'None identified',
      volRisk: state.ptcState.volRisk || 'Normal',
      execQuality: state.ptcState.execQuality || 'Messy',
      conviction: state.ptcState.conviction || 'Medium',
      edgeTag: state.ptcState.edgeTag || 'Other',
      confluenceScore: Number.parseInt(readTextInput('confluenceScore', '7'), 10) || 7
    },
    gate: {
      status: readGateStatus(),
      waitReasonCode: readTextInput('waitReason'),
      reentryCondition: readTextInput('reentryCondition'),
      reentryTime: readTextInput('reentryTime')
    }
  };
}

function buildAARStub(ticketId) {
  return {
    schemaVersion: AAR_SCHEMA_VERSION,
    ticketId,
    reviewedAt: new Date().toISOString(),
    outcomeEnum: 'MISSED',
    verdictEnum: 'PROCESS_GOOD',
    firstTouch: false,
    wouldHaveWon: false,
    actualEntry: 0,
    actualExit: 0,
    rAchieved: 0,
    exitReasonEnum: 'NO_FILL',
    killSwitchTriggered: false,
    failureReasonCodes: [],
    psychologicalTag: 'CALM',
    revisedConfidence: 3,
    checklistDelta: {
      htfState: '',
      ltfAlignment: '',
      volRisk: '',
      execQuality: '',
      notes: ''
    },
    revisedTicket: {},
    notes: 'AAR not completed yet.'
  };
}

export function exportJSONBackup() {
  const ticket = buildTicketSnapshot();
  const aar = buildAARStub(ticket.ticketId);
  const ticketValidation = validateTicketPayload(ticket);
  const aarValidation = validateAARPayload(aar);

  if (!ticketValidation.ok || !aarValidation.ok) {
    const message = [...ticketValidation.errors, ...aarValidation.errors].join('\n');
    alert(`Backup export blocked by schema validation:\n${message}`);
    return;
  }

  const payload = {
    exportVersion: 1,
    exportedAt: new Date().toISOString(),
    ticket,
    aar
  };

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `AI_Trade_Backup_${state.ticketID || 'draft'}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
