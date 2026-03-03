import test from 'node:test';
import assert from 'node:assert/strict';

import { renderUsageSummary } from '../app/scripts/verdict_card.js';

test('renderUsageSummary prints compact usage fields with fallbacks', () => {
  const html = renderUsageSummary({ run_id: 'run-42', calls: 3, total_tokens: 1200, input_tokens: 800, output_tokens: 400, models: ['gpt-4o', 'claude-3-5-sonnet'] });

  assert.match(html, /USAGE SUMMARY/);
  assert.match(html, /Run ID:<\/strong> run-42/);
  assert.match(html, /Total calls:<\/strong> 3/);
  assert.match(html, /Total tokens:<\/strong> 1,200/);
  assert.match(html, /Input tokens:<\/strong> 800/);
  assert.match(html, /Output tokens:<\/strong> 400/);
  assert.match(html, /gpt-4o, claude-3-5-sonnet/);
});

test('renderUsageSummary supports nested token payloads', () => {
  const html = renderUsageSummary({
    totals: { calls: 6, total_tokens: 1900, input_tokens: 1000, output_tokens: 900 },
    models_used: 'model-a, model-b',
  }, 'run-nested');

  assert.match(html, /Run ID:<\/strong> run-nested/);
  assert.match(html, /Total calls:<\/strong> 6/);
  assert.match(html, /Total tokens:<\/strong> 1,900/);
  assert.match(html, /model-a, model-b/);
});
