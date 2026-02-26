import { migrateState } from '../state/migrations.js';
import { validateAARPayload, validateTicketPayload } from '../schema/backup_validation.js';

export async function importJSONBackup(file) {
  if (!file) {
    alert('Select a backup file before import.');
    return null;
  }

  let parsed;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    alert('Backup import failed: invalid JSON file.');
    return null;
  }

  const migrated = migrateState(parsed);
  if (!migrated) {
    alert('Backup import failed: payload migration returned null.');
    return null;
  }

  const ticketValidation = validateTicketPayload(migrated?.ticket);
  const aarValidation = validateAARPayload(migrated?.aar);

  if (!ticketValidation.ok || !aarValidation.ok) {
    const message = [...ticketValidation.errors, ...aarValidation.errors].join('\n');
    alert(`Backup import blocked by schema validation:\n${message}`);
    return null;
  }

  return migrated;
}
