import test from 'node:test';
import assert from 'node:assert/strict';

import { migrateState } from '../app/scripts/state/migrations.js';
import { TICKET_SCHEMA_VERSION, AAR_SCHEMA_VERSION } from '../app/scripts/schema/backup_validation.js';

test('migrateState returns null for non-object payloads', () => {
  assert.equal(migrateState(null), null);
  assert.equal(migrateState(undefined), null);
  assert.equal(migrateState('not-an-object'), null);
});

test('migrateState returns payload unchanged for current schema versions', () => {
  const payload = {
    ticket: { schemaVersion: TICKET_SCHEMA_VERSION },
    aar: { schemaVersion: AAR_SCHEMA_VERSION }
  };

  assert.equal(migrateState(payload), payload);
});

test('migrateState warns for unsupported schema versions but still returns payload', () => {
  const warnings = [];
  const originalWarn = console.warn;
  console.warn = (message) => warnings.push(message);

  const payload = {
    ticket: { schemaVersion: '2.0.0' },
    aar: { schemaVersion: '3.0.0' }
  };

  try {
    const result = migrateState(payload);
    assert.equal(result, payload);
  } finally {
    console.warn = originalWarn;
  }

  assert.equal(warnings.length, 2);
  assert.match(warnings[0], /Unsupported ticket schema version/);
  assert.match(warnings[1], /Unsupported AAR schema version/);
});
