export function migrateState(payload) {
  if (!payload || typeof payload !== 'object') return null;

  const ticketVersion = payload.ticket?.schemaVersion;
  const aarVersion = payload.aar?.schemaVersion;

  if (typeof ticketVersion === 'string' && ticketVersion !== '1.0.0') {
    console.warn(`[migrateState] Unsupported ticket schema version: ${ticketVersion}.`);
  }

  if (typeof aarVersion === 'string' && aarVersion !== '1.0.0') {
    console.warn(`[migrateState] Unsupported AAR schema version: ${aarVersion}.`);
  }

  return payload;
}
