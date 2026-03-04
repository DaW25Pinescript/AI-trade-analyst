import test from 'node:test';
import assert from 'node:assert/strict';

import { hydrateMacroState } from '../app/scripts/state/macro_state.js';

test('hydrateMacroState maps feeder payload into shared macro state stubs', () => {
  const payload = {
    contract_version: '1.0.0',
    generated_at: '2026-03-04T00:00:00Z',
    status: 'ok',
    warnings: [],
    events: [{ event_id: '1', title: 'US CPI m/m' }],
    source_health: { finnhub: { status: 'ok' } },
    macro_context: { regime: 'risk_on', vol_bias: 'contracting' }
  };

  const result = hydrateMacroState(payload);

  assert.equal(result.context.regime, 'risk_on');
  assert.equal(result.eventBatch.contractVersion, '1.0.0');
  assert.equal(result.eventBatch.events.length, 1);
  assert.equal(result.sourceHealth.finnhub.status, 'ok');
  assert.equal(result.observability.feederStatus, 'ok');
});

test('hydrateMacroState is robust to missing optional fields', () => {
  const result = hydrateMacroState({});

  assert.equal(result.context, null);
  assert.equal(Array.isArray(result.eventBatch.events), true);
  assert.equal(result.observability.warningCount, 0);
  assert.equal(result.observability.feederStatus, 'unknown');
});
