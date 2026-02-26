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

test('migrateState upgrades ticket from 1.1.0 to 1.2.0 with defaults', () => {
  const payload = {
    ticket: { schemaVersion: '1.1.0', decisionMode: 'LONG' },
    aar: { schemaVersion: AAR_SCHEMA_VERSION }
  };

  const result = migrateState(payload);

  assert.notEqual(result, payload);
  assert.equal(result.ticket.schemaVersion, '1.2.0');
  assert.equal(result.ticket.counterTrendMode, 'Mixed');
  assert.equal(result.ticket.rawAIReadBias, '');
  assert.equal(result.ticket.decisionMode, 'LONG');
});

test('migrateState preserves existing counterTrendMode/rawAIReadBias when upgrading 1.1.0', () => {
  const payload = {
    ticket: {
      schemaVersion: '1.1.0',
      counterTrendMode: 'Strict HTF-only',
      rawAIReadBias: 'Bullish'
    },
    aar: { schemaVersion: AAR_SCHEMA_VERSION }
  };

  const result = migrateState(payload);
  assert.equal(result.ticket.counterTrendMode, 'Strict HTF-only');
  assert.equal(result.ticket.rawAIReadBias, 'Bullish');
});
