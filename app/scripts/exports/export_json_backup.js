import { state } from '../state/model.js';
import { TICKET_SCHEMA_VERSION, AAR_SCHEMA_VERSION, validateTicketPayload, validateAARPayload } from '../schema/backup_validation.js';

function readTextInput(id, fallback = '') {
  const el = document.getElementById(id);
  return (el?.value || fallback).toString();
}

function readNumberInput(id, fallback = 0) {
  const el = document.getElementById(id);
  return Number.parseFloat(el?.value || '') || fallback;
}

function readGateStatus() {
  const gateEl = document.getElementById('gateStatus');
  if (gateEl?.classList.contains('wait')) return 'WAIT';
  if (gateEl?.classList.contains('caution')) return 'CAUTION';
  if (gateEl?.classList.contains('proceed')) return 'PROCEED';
  return 'INCOMPLETE';
}

function readSelectInput(id, fallback = '') {
  const el = document.getElementById(id);
  return el?.value || fallback;
}

function readIntSelectInput(id) {
  const value = Number.parseInt(readSelectInput(id), 10);
  return Number.isInteger(value) ? value : NaN;
}

function buildTicketSnapshot() {
  const nowISO = new Date().toISOString();
  const edgeScore = readNumberInput('edgeScoreDisplay', 0);

  // G8: AI edge score (optional — only include if the user recorded a valid 0–1 value)
  const aiEdgeScoreEl = document.getElementById('aiEdgeScore');
  const aiEdgeScoreRaw = Number.parseFloat(aiEdgeScoreEl?.value || '');
  const aiEdgeScore = Number.isFinite(aiEdgeScoreRaw) && aiEdgeScoreRaw >= 0 && aiEdgeScoreRaw <= 1
    ? aiEdgeScoreRaw : undefined;

  const cleanCharts = [
    { key: 'htf', timeframe: 'H4' },
    { key: 'm15', timeframe: 'M15' },
    { key: 'm5', timeframe: 'M5' }
  ]
    .filter(({ key }) => Boolean(state.uploads[key] && state.imgSrcs[key]))
    .map(({ timeframe }) => ({
      timeframe,
      lens: 'NONE',
      evidenceType: 'price_only'
    }));

  if (cleanCharts.length === 0) {
    cleanCharts.push({ timeframe: 'H4', lens: 'NONE', evidenceType: 'price_only' });
  }

  return {
    schemaVersion: TICKET_SCHEMA_VERSION,
    ticketId: state.ticketID || 'draft',
    createdAt: nowISO,
    counterTrendMode: readSelectInput('counterTrendMode', 'Mixed'),
    rawAIReadBias: readSelectInput('rawAIReadBias', ''),
    decisionMode: readSelectInput('decisionMode'),
    ticketType: readSelectInput('ticketType'),
    entryType: readSelectInput('entryType'),
    entryTrigger: readSelectInput('entryTrigger'),
    confirmationTF: readSelectInput('confTF'),
    timeInForce: readSelectInput('timeInForce'),
    maxAttempts: readIntSelectInput('maxAttempts'),
    entry: {
      zone: readTextInput('levels', 'User-defined zone'),
      priceMin: readNumberInput('entryPriceMin'),
      priceMax: readNumberInput('entryPriceMax'),
      notes: readTextInput('entryNotes')
    },
    stop: {
      price: readNumberInput('stopPrice'),
      logic: readSelectInput('stopLogic'),
      rationale: readTextInput('stopRationale', 'User-defined stop')
    },
    targets: [
      { label: 'TP1', price: readNumberInput('tp1Price'), rationale: readTextInput('tp1Rationale', 'Primary reaction level') },
      { label: 'TP2', price: readNumberInput('tp2Price'), rationale: readTextInput('tp2Rationale', 'Extended move objective') }
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
    },
    edgeScore,
    psychologicalLeakR: 0,
    screenshots: {
      cleanCharts,
      m15Overlay: null
    },
    // G8 optional fields — only included when set
    ...(aiEdgeScore !== undefined ? { aiEdgeScore } : {}),
    ...(state.revisedFromId ? { revisedFromId: state.revisedFromId } : {}),
    // G9: shadow mode — always include when active; shadowOutcome only when recorded
    ...(state.shadowMode ? { shadowMode: true } : {}),
    ...(state.shadowOutcome ? { shadowOutcome: state.shadowOutcome } : {})
  };
}

function readAARSelect(id, fallback) {
  return document.getElementById(id)?.value || fallback;
}

function readAARNumber(id) {
  return Number.parseFloat(document.getElementById(id)?.value || '') || 0;
}

function readAARBool(stateVal, fallback = false) {
  if (stateVal === null || stateVal === undefined) return fallback;
  return stateVal === 'true' || stateVal === true;
}

function readAARFailureCodes() {
  const container = document.getElementById('aarFailureCodes');
  if (!container) return [];
  return Array.from(container.querySelectorAll('.checkbox-item.checked input[data-code]'))
    .map(el => el.dataset.code)
    .filter(Boolean);
}

function buildAARPayload(ticketId) {
  const notes = document.getElementById('aarNotes')?.value || '';
  return {
    schemaVersion: AAR_SCHEMA_VERSION,
    ticketId,
    reviewedAt: new Date().toISOString(),
    outcomeEnum: readAARSelect('aarOutcome', 'MISSED'),
    verdictEnum: readAARSelect('aarVerdict', 'PROCESS_GOOD'),
    firstTouch: readAARBool(state.aarState.firstTouch, false),
    wouldHaveWon: readAARBool(state.aarState.wouldHaveWon, false),
    actualEntry: readAARNumber('aarActualEntry'),
    actualExit: readAARNumber('aarActualExit'),
    rAchieved: readAARNumber('aarRachieved'),
    exitReasonEnum: readAARSelect('aarExitReason', 'NO_FILL'),
    killSwitchTriggered: readAARBool(state.aarState.killSwitch, false),
    failureReasonCodes: readAARFailureCodes(),
    psychologicalTag: readAARSelect('aarPsychTag', 'CALM'),
    revisedConfidence: Number.parseInt(document.getElementById('aarConfidence')?.value || '3', 10) || 3,
    checklistDelta: {
      htfState: document.getElementById('aarDeltaHtfState')?.value || '',
      ltfAlignment: document.getElementById('aarDeltaLtfAlignment')?.value || '',
      volRisk: document.getElementById('aarDeltaVolRisk')?.value || '',
      execQuality: document.getElementById('aarDeltaExecQuality')?.value || '',
      notes: document.getElementById('aarDeltaNotes')?.value || ''
    },
    revisedTicket: {},
    notes: notes.trim().length > 0 ? notes : 'AAR not completed yet.'
  };
}

function buildBackupPayload() {
  const ticket = buildTicketSnapshot();
  const aar = buildAARPayload(ticket.ticketId);

  // Psychological leak is measured only after outcome data exists.
  if (aar.psychologicalTag !== 'CALM' && aar.psychologicalTag !== 'DISCIPLINED' && aar.rAchieved < 0) {
    ticket.psychologicalLeakR = Math.abs(aar.rAchieved);
  }

  const ticketValidation = validateTicketPayload(ticket);
  const aarValidation = validateAARPayload(aar);

  if (!ticketValidation.ok || !aarValidation.ok) {
    return {
      ok: false,
      errors: [...ticketValidation.errors, ...aarValidation.errors]
    };
  }

  return {
    ok: true,
    payload: {
    exportVersion: 1,
    exportedAt: new Date().toISOString(),
    ticket,
    aar
    }
  };
}

export function exportJSONBackup({ silent = false, filenamePrefix = 'AI_Trade_Backup' } = {}) {
  const result = buildBackupPayload();
  if (!result.ok) {
    const message = result.errors.join('\n');
    if (!silent) alert(`Backup export blocked by schema validation:\n${message}`);
    return null;
  }

  const payload = result.payload;

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filenamePrefix}_${state.ticketID || 'draft'}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);

  return payload;
}
