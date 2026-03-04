/**
 * C4 — Unified Import
 *
 * Reads a unified export file produced by export_unified.js.
 * Validates ticket + AAR schema, restores bridge verdict state, and returns
 * the migrated payload so the caller can restore form fields and the verdict card.
 */

import { migrateState } from '../state/migrations.js';
import { validateTicketPayload, validateAARPayload } from '../schema/backup_validation.js';
import { state } from '../state/model.js';
import { UNIFIED_EXPORT_VERSION } from './export_unified.js';

/**
 * Validate and process a pre-parsed unified export object.
 * Does not touch the DOM or state — pure validation logic, fully testable.
 *
 * @param {Object} parsed  The parsed JSON object from a unified export file.
 * @returns {{ok:boolean, payload?:Object, errors?:string[]}}
 */
export function parseUnifiedPayload(parsed) {
  if (!parsed || typeof parsed !== 'object') {
    return { ok: false, errors: ['Payload is not a valid object.'] };
  }
  if (parsed.exportFormat !== 'unified') {
    return {
      ok: false,
      errors: ['File is not a unified export. Use "Import JSON Backup" for standard backups.']
    };
  }
  if (typeof parsed.exportVersion !== 'number' || parsed.exportVersion > UNIFIED_EXPORT_VERSION) {
    return {
      ok: false,
      errors: [`Unsupported unified export version: ${parsed.exportVersion}. Expected ≤ ${UNIFIED_EXPORT_VERSION}.`]
    };
  }

  const migrated = migrateState(parsed);
  if (!migrated) {
    return { ok: false, errors: ['Payload migration returned null — format may be unrecognised.'] };
  }

  const ticketValidation = validateTicketPayload(migrated?.ticket);
  const aarValidation = validateAARPayload(migrated?.aar);
  if (!ticketValidation.ok || !aarValidation.ok) {
    return {
      ok: false,
      errors: [...ticketValidation.errors, ...aarValidation.errors]
    };
  }

  return { ok: true, payload: migrated };
}

/**
 * Read a File input, validate it as a unified export, restore verdict state,
 * and return the migrated payload.
 *
 * @param {File|null} file
 * @returns {Promise<Object|null>}  Migrated payload, or null on any failure.
 */
export async function importUnified(file) {
  if (!file) {
    alert('Select a unified export file before import.');
    return null;
  }

  let parsed;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    alert('Unified import failed: invalid JSON file.');
    return null;
  }

  const result = parseUnifiedPayload(parsed);
  if (!result.ok) {
    alert(`Unified import blocked:\n${result.errors.join('\n')}`);
    return null;
  }

  // Restore bridge verdict state so subsequent "Export Unified" includes the verdict.
  if (parsed.verdict && typeof parsed.verdict === 'object') {
    state.bridgeVerdict = parsed.verdict;
  }

  return result.payload;
}
