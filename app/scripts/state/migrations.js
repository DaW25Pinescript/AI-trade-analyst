export function migrateState(payload) {
  if (!payload || typeof payload !== 'object') return null;
  return payload;
}
