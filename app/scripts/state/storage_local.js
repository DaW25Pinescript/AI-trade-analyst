import { validateAARPayload, validateTicketPayload } from '../schema/backup_validation.js';

const KEY = 'ai_trade_analyst_v3_state';

export function saveLocalState(payload) {
  const ticketValidation = validateTicketPayload(payload?.ticket);
  const aarValidation = validateAARPayload(payload?.aar);

  if (!ticketValidation.ok || !aarValidation.ok) {
    throw new Error(`Refused to save invalid state:\n${[...ticketValidation.errors, ...aarValidation.errors].join('\n')}`);
  }

  localStorage.setItem(KEY, JSON.stringify(payload));
}

export function loadLocalState() {
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;

  const payload = JSON.parse(raw);
  const ticketValidation = validateTicketPayload(payload?.ticket);
  const aarValidation = validateAARPayload(payload?.aar);

  if (!ticketValidation.ok || !aarValidation.ok) {
    throw new Error(`Stored state failed schema validation:\n${[...ticketValidation.errors, ...aarValidation.errors].join('\n')}`);
  }

  return payload;
}
