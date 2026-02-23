const CURRENT_TICKET_VERSION = '1.0.0';
const CURRENT_AAR_VERSION = '1.0.0';

export function migrateState(payload) {
  if (!payload || typeof payload !== 'object') return null;

  const ticketVersion = payload.ticket?.schemaVersion;
  const aarVersion = payload.aar?.schemaVersion;

  if (ticketVersion && ticketVersion !== CURRENT_TICKET_VERSION) {
    console.warn(`migrations: ticket schemaVersion ${ticketVersion} does not match current ${CURRENT_TICKET_VERSION} — no migration path defined`);
  }
  if (aarVersion && aarVersion !== CURRENT_AAR_VERSION) {
    console.warn(`migrations: aar schemaVersion ${aarVersion} does not match current ${CURRENT_AAR_VERSION} — no migration path defined`);
  }

  // v1.0.0 → v1.0.0: no transformation needed
  return payload;
}
