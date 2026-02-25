import { TICKET_SCHEMA_VERSION, AAR_SCHEMA_VERSION } from '../schema/backup_validation.js';

export function migrateState(payload) {
  if (!payload || typeof payload !== 'object') return null;

  const ticketVersion = payload.ticket?.schemaVersion;
  const aarVersion = payload.aar?.schemaVersion;

  if (typeof ticketVersion === 'string' && ticketVersion !== TICKET_SCHEMA_VERSION) {
    console.warn(`[migrateState] Unsupported ticket schema version: ${ticketVersion}.`);
  }

  if (typeof aarVersion === 'string' && aarVersion !== AAR_SCHEMA_VERSION) {
    console.warn(`[migrateState] Unsupported AAR schema version: ${aarVersion}.`);
  }

  return payload;
}
