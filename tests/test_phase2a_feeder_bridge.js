import test from 'node:test';
import assert from 'node:assert/strict';

import {
  postFeederPayload,
  getFeederHealth,
} from '../app/scripts/api_bridge.js';
import {
  formatConfidencePct,
  formatPrice,
  renderFinalVerdict,
} from '../app/scripts/verdict_card.js';

// ── postFeederPayload tests ──────────────────────────────────────────────────

test('postFeederPayload throws if serverUrl is empty', async () => {
  await assert.rejects(
    () => postFeederPayload('', { contract_version: '1.0.0' }),
    { message: 'Server URL is required.' }
  );
});

test('postFeederPayload throws if payload is null', async () => {
  await assert.rejects(
    () => postFeederPayload('http://localhost:8000', null),
    { message: 'Feeder payload must be a JSON object.' }
  );
});

test('postFeederPayload sends JSON POST to /feeder/ingest', async () => {
  const payload = { contract_version: '1.0.0', events: [] };
  let capturedUrl = '';
  let capturedOpts = {};

  const mockFetch = async (url, opts) => {
    capturedUrl = url;
    capturedOpts = opts;
    return {
      ok: true,
      json: async () => ({ status: 'ok', macro_context: {}, ingested_at: '2026-03-04T12:00:00Z' }),
    };
  };

  const result = await postFeederPayload('http://localhost:8000', payload, mockFetch);
  assert.equal(capturedUrl, 'http://localhost:8000/feeder/ingest');
  assert.equal(capturedOpts.method, 'POST');
  assert.equal(capturedOpts.headers['Content-Type'], 'application/json');
  assert.equal(capturedOpts.body, JSON.stringify(payload));
  assert.equal(result.status, 'ok');
});

test('postFeederPayload throws on non-ok response', async () => {
  const mockFetch = async () => ({
    ok: false,
    status: 422,
    statusText: 'Unprocessable Entity',
    text: async () => 'bad contract',
  });

  await assert.rejects(
    () => postFeederPayload('http://localhost:8000', { contract_version: '1.0.0' }, mockFetch),
    (err) => err.message.includes('422')
  );
});

// ── getFeederHealth tests ────────────────────────────────────────────────────

test('getFeederHealth throws if serverUrl is empty', async () => {
  await assert.rejects(
    () => getFeederHealth(''),
    { message: 'Server URL is required.' }
  );
});

test('getFeederHealth sends GET to /feeder/health', async () => {
  let capturedUrl = '';
  const mockFetch = async (url) => {
    capturedUrl = url;
    return {
      ok: true,
      json: async () => ({ status: 'no_data', stale: true }),
    };
  };

  const result = await getFeederHealth('http://localhost:8000/', mockFetch);
  assert.equal(capturedUrl, 'http://localhost:8000/feeder/health');
  assert.equal(result.status, 'no_data');
});

test('getFeederHealth throws on non-ok response', async () => {
  const mockFetch = async () => ({
    ok: false,
    status: 500,
    statusText: 'Internal Server Error',
    text: async () => 'server error',
  });

  await assert.rejects(
    () => getFeederHealth('http://localhost:8000', mockFetch),
    (err) => err.message.includes('500')
  );
});

// ── formatConfidencePct tests (float fix) ────────────────────────────────────

test('formatConfidencePct converts 0.0–1.0 float to percentage string', () => {
  assert.equal(formatConfidencePct(0.78), '78%');
  assert.equal(formatConfidencePct(0.0), '0%');
  assert.equal(formatConfidencePct(1.0), '100%');
  assert.equal(formatConfidencePct(0.655), '66%');
});

test('formatConfidencePct passes through 0–100 integer values', () => {
  assert.equal(formatConfidencePct(78), '78%');
  assert.equal(formatConfidencePct(100), '100%');
  assert.equal(formatConfidencePct(50), '50%');
});

test('formatConfidencePct returns N/A for non-numeric values', () => {
  assert.equal(formatConfidencePct(NaN), 'N/A');
  assert.equal(formatConfidencePct('abc'), 'N/A');
  assert.equal(formatConfidencePct(Infinity), 'N/A');
});

// ── formatPrice tests (float fix) ───────────────────────────────────────────

test('formatPrice formats gold prices with 2 decimals', () => {
  assert.equal(formatPrice(1932.5), '1932.50');
  assert.equal(formatPrice(2000), '2000.00');
});

test('formatPrice formats forex prices with 5 decimals', () => {
  assert.equal(formatPrice(1.08234), '1.08234');
  assert.equal(formatPrice(0.95), '0.95000');
});

test('formatPrice returns N/A for non-numeric values', () => {
  assert.equal(formatPrice(NaN), 'N/A');
  assert.equal(formatPrice('abc'), 'N/A');
  assert.equal(formatPrice(Infinity), 'N/A');
});

// ── renderFinalVerdict float display tests ──────────────────────────────────

test('renderFinalVerdict displays confidence as percentage', () => {
  const verdict = {
    decision: 'ENTER_LONG',
    final_bias: 'bullish',
    overall_confidence: 0.78,
    analyst_agreement_pct: 75,
    arbiter_notes: 'Test',
    approved_setups: [{
      type: 'Pullback',
      rr_estimate: 2.1,
      confidence: 0.65,
      entry_zone: '1932–1934',
      stop: '1930',
      targets: ['1937'],
    }],
    no_trade_conditions: [],
  };

  const html = renderFinalVerdict(verdict);

  // Overall confidence should show as percentage
  assert.ok(html.includes('78%'), 'Overall confidence should be displayed as 78%');
  // Setup confidence should show as percentage
  assert.ok(html.includes('65%'), 'Setup confidence should be displayed as 65%');
  // Raw 0.78 / 0.65 should NOT appear as plain decimals
  assert.ok(!html.includes('>0.78<'), 'Raw 0.78 should not appear in output');
  assert.ok(!html.includes('>0.65<'), 'Raw 0.65 should not appear in output');
});

test('renderFinalVerdict returns hint when verdict is null', () => {
  const html = renderFinalVerdict(null);
  assert.ok(html.includes('No verdict available'));
});
