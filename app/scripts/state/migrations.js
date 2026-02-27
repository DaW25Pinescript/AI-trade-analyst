import { TICKET_SCHEMA_VERSION, AAR_SCHEMA_VERSION } from '../schema/backup_validation.js';

function migrateTicket_1_1_to_1_2(ticket) {
  return {
    ...ticket,
    schemaVersion: '1.2.0',
    counterTrendMode: ticket.counterTrendMode ?? 'Mixed',
    rawAIReadBias: ticket.rawAIReadBias ?? ''
  };
}

function migrateTicket_1_2_to_2_0(ticket) {
  return {
    ...ticket,
    schemaVersion: '2.0.0',
    edgeScore: Number.isFinite(ticket.edgeScore) ? ticket.edgeScore : 0,
    psychologicalLeakR: Number.isFinite(ticket.psychologicalLeakR) ? ticket.psychologicalLeakR : 0,
    screenshots: ticket.screenshots ?? {
      cleanCharts: [{ timeframe: 'H4', lens: 'NONE', evidenceType: 'price_only' }],
      m15Overlay: null
    }
  };
}

function migrateTicket_2_0_to_3_0(ticket) {
  // G8: aiEdgeScore and revisedFromId are new optional fields — no defaults needed.
  return { ...ticket, schemaVersion: '3.0.0' };
}

function migrateTicket_3_0_to_4_0(ticket) {
  // G9: shadowMode defaults to false; shadowOutcome defaults to null.
  return {
    ...ticket,
    schemaVersion: '4.0.0',
    shadowMode: ticket.shadowMode ?? false,
    shadowOutcome: ticket.shadowOutcome ?? null
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

  if (ticket?.schemaVersion === '1.2.0') {
    ticket = migrateTicket_1_2_to_2_0(ticket);
    ticketMigrated = true;
    console.info('[migrateState] Migrated ticket from 1.2.0 → 2.0.0.');
  }

  if (ticket?.schemaVersion === '2.0.0') {
    ticket = migrateTicket_2_0_to_3_0(ticket);
    ticketMigrated = true;
    console.info('[migrateState] Migrated ticket from 2.0.0 → 3.0.0.');
  }

  if (ticket?.schemaVersion === '3.0.0') {
    ticket = migrateTicket_3_0_to_4_0(ticket);
    ticketMigrated = true;
    console.info('[migrateState] Migrated ticket from 3.0.0 → 4.0.0.');
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
