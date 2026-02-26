import { TICKET_SCHEMA_VERSION, AAR_SCHEMA_VERSION } from '../schema/backup_validation.js';

/**
 * Upgrade a v1.1.0 ticket to v1.2.0.
 * Adds G4 counterTrendMode (default: 'Mixed') and G5 rawAIReadBias (default: '').
 */
function migrateTicket_1_1_to_1_2(ticket) {
  return {
    ...ticket,
    schemaVersion: '1.2.0',
    counterTrendMode: ticket.counterTrendMode ?? 'Mixed',
    rawAIReadBias: ticket.rawAIReadBias ?? '',
  };
}

export function migrateState(payload) {
  if (!payload || typeof payload !== 'object') return null;

  let ticket = payload.ticket;
  const aarVersion = payload.aar?.schemaVersion;
  let ticketMigrated = false;

  // Apply ticket migrations in version order
  if (ticket?.schemaVersion === '1.1.0') {
    ticket = migrateTicket_1_1_to_1_2(ticket);
    ticketMigrated = true;
    console.info('[migrateState] Migrated ticket from 1.1.0 → 1.2.0.');
  }

  if (typeof ticket?.schemaVersion === 'string' && ticket.schemaVersion !== TICKET_SCHEMA_VERSION) {
    console.warn(`[migrateState] Unsupported ticket schema version after migration: ${ticket.schemaVersion}.`);
  }

  if (typeof aarVersion === 'string' && aarVersion !== AAR_SCHEMA_VERSION) {
    console.warn(`[migrateState] Unsupported AAR schema version: ${aarVersion}.`);
  }

  // Return the original reference when no migration was applied
  return ticketMigrated ? { ...payload, ticket } : payload;
}
