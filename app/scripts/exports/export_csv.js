import { state } from '../state/model.js';

function csvCell(value) {
  const str = String(value ?? '');
  return str.includes(',') || str.includes('"') || str.includes('\n')
    ? `"${str.replace(/"/g, '""')}"`
    : str;
}

function readGateStatus() {
  const gateEl = document.getElementById('gateStatus');
  if (gateEl?.classList.contains('wait')) return 'WAIT';
  if (gateEl?.classList.contains('caution')) return 'CAUTION';
  if (gateEl?.classList.contains('proceed')) return 'PROCEED';
  return 'INCOMPLETE';
}

export function exportCSV() {
  const get    = id => document.getElementById(id)?.value ?? '';
  const getNum = id => Number.parseFloat(get(id)) || 0;

  const ticketId       = state.ticketID || 'draft';
  const nowISO         = new Date().toISOString();
  const asset          = get('asset') || '';
  const session        = get('session') || '';
  const decisionMode   = get('decisionMode') || 'WAIT';
  const ticketType     = get('ticketType') || 'Zone ticket';
  const entryType      = get('entryType') || 'Limit';
  const entryTrigger   = get('entryTrigger') || 'Pullback to zone';
  const confTF         = get('confTF') || '1H';
  const stopLogic      = get('stopLogic') || 'Below swing low / above swing high';
  const timeInForce    = get('timeInForce') || 'This session';
  const maxAttempts    = get('maxAttempts') || '2';
  const entryPriceMin  = getNum('entryPriceMin');
  const entryPriceMax  = getNum('entryPriceMax');
  const stopPrice      = getNum('stopPrice');
  const tp1Price       = getNum('tp1Price');
  const tp2Price       = getNum('tp2Price');
  const confluenceScore = get('confluenceScore') || '7';
  const gateStatus     = readGateStatus();
  const waitReason     = get('waitReason') || '';
  const ptc            = state.ptcState;

  const headers = [
    'ticketId', 'createdAt', 'asset', 'session',
    'decisionMode', 'ticketType', 'entryType', 'entryTrigger',
    'confirmationTF', 'stopLogic', 'timeInForce', 'maxAttempts',
    'entryPriceMin', 'entryPriceMax', 'stopPrice', 'tp1Price', 'tp2Price',
    'gateStatus', 'waitReasonCode', 'confluenceScore',
    'htfState', 'htfLocation', 'ltfAlignment', 'liquidityContext',
    'volRisk', 'execQuality', 'conviction', 'edgeTag'
  ];

  const row = [
    ticketId, nowISO, asset, session,
    decisionMode, ticketType, entryType, entryTrigger,
    confTF, stopLogic, timeInForce, maxAttempts,
    entryPriceMin, entryPriceMax, stopPrice, tp1Price, tp2Price,
    gateStatus, waitReason, confluenceScore,
    ptc.htfState || '', ptc.htfLocation || '', ptc.ltfAlignment || '', ptc.liquidityContext || '',
    ptc.volRisk || '', ptc.execQuality || '', ptc.conviction || '', ptc.edgeTag || ''
  ].map(csvCell);

  const csv = [headers.join(','), row.join(',')].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `AI_Trade_${ticketId}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
