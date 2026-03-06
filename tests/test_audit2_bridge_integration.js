/**
 * test_audit2_bridge_integration.js — Audit 2: G11 Bridge → G12 Integration
 *
 * Integration-style tests validating the full bridge contract:
 *   1. Happy-path: valid envelope → correct field extraction
 *   2. API unreachable: network error → proper error propagation
 *   3. Schema mismatch: malformed/partial envelope → no silent corruption
 *   4. HTTP error codes: 422, 429, 500, 503 → correct handling
 *   5. Response envelope invariants: required keys always present
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildAnalyseFormData,
  postAnalyse,
  analyseViaBridge,
  checkBridgeHealth,
} from '../app/scripts/api_bridge.js';

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Minimal document stub for buildAnalyseFormData. */
function makeDoc(overrides = {}) {
  const map = new Map(Object.entries(overrides));
  return {
    getElementById(id) {
      return map.get(id) || null;
    },
  };
}

/** Standard form doc with charts uploaded. */
function standardDoc() {
  const fakeFile = { name: 'chart.png', size: 2048 };
  return makeDoc({
    asset: { value: 'XAUUSD' },
    session: { value: 'London' },
    accountBalance: { value: '10000' },
    minRR: { value: '2.5' },
    maxStop: { value: '0.75' },
    maxDailyRisk: { value: '2' },
    regime: { value: 'Trending' },
    volRisk: { value: 'Normal' },
    broker: { value: 'TradingView' },
    'upload-htf': { files: [fakeFile] },
    'upload-m15': { files: [fakeFile] },
    'upload-m5': { files: [] },
    'upload-m15overlay': { files: [] },
  });
}

/** A realistic v2.0 response envelope matching AnalysisResponse. */
function validEnvelope() {
  return {
    verdict: {
      decision: 'ENTER_LONG',
      overall_confidence: 0.82,
      analyst_agreement_pct: 75,
      risk_score: 0.35,
      reasoning: 'Strong HTF trend alignment with LTF entry trigger',
      analyst_verdicts: [
        { persona: 'alpha', action: 'ENTER_LONG', confidence: 0.85 },
        { persona: 'beta', action: 'ENTER_LONG', confidence: 0.78 },
      ],
      overlay_delta: null,
      dissent_notes: [],
      key_levels: { support: [2320.5], resistance: [2345.0] },
      warnings: [],
    },
    ticket_draft: {
      decisionMode: 'LONG',
      rawAIReadBias: 'Bullish',
      shadowMode: false,
      counterTrendMode: 'NONE',
    },
    run_id: 'run-integration-test-001',
    source_ticket_id: 'ticket-abc-123',
    usage_summary: {
      total_calls: 3,
      successful_calls: 3,
      failed_calls: 0,
      tokens: { prompt_tokens: 5000, completion_tokens: 1200, total_tokens: 6200 },
      total_cost_usd: 0.0312,
    },
  };
}

// ── 1. Happy-path: valid response envelope ───────────────────────────────────

test('Audit 2 — happy-path: valid envelope returns all required fields', async () => {
  const envelope = validEnvelope();
  const fakeFetch = async (_url, _opts) => ({
    ok: true,
    async json() { return envelope; },
  });

  const response = await postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
    retries: 0,
    timeoutMs: 5000,
  });

  // Verify all top-level keys from AnalysisResponse are present
  assert.ok(response.verdict, 'response must include verdict');
  assert.ok(response.ticket_draft, 'response must include ticket_draft');
  assert.ok(response.run_id, 'response must include run_id');
  assert.ok(response.usage_summary, 'response must include usage_summary');

  // Verify verdict structure
  assert.equal(response.verdict.decision, 'ENTER_LONG');
  assert.equal(typeof response.verdict.overall_confidence, 'number');
  assert.ok(response.verdict.overall_confidence >= 0 && response.verdict.overall_confidence <= 1,
    'confidence must be 0–1');
  assert.equal(typeof response.verdict.analyst_agreement_pct, 'number');

  // Verify ticket_draft fields that the UI depends on
  assert.equal(response.ticket_draft.decisionMode, 'LONG');
  assert.equal(response.ticket_draft.rawAIReadBias, 'Bullish');
  assert.equal(typeof response.ticket_draft.shadowMode, 'boolean');
});

test('Audit 2 — happy-path: source_ticket_id round-trips correctly', async () => {
  const envelope = validEnvelope();
  const fakeFetch = async () => ({ ok: true, async json() { return envelope; } });

  const response = await postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
    retries: 0,
  });
  assert.equal(response.source_ticket_id, 'ticket-abc-123');
});

test('Audit 2 — happy-path: analyseViaBridge end-to-end with doc stub', async () => {
  const envelope = validEnvelope();
  const fakeFetch = async (url, opts) => {
    // Verify the URL is correctly constructed
    assert.equal(url, 'http://localhost:8000/analyse');
    assert.equal(opts.method, 'POST');
    assert.ok(opts.body instanceof FormData, 'body must be FormData');
    // Verify required form fields
    assert.equal(opts.body.get('instrument'), 'XAUUSD');
    assert.equal(opts.body.get('session'), 'London');
    return { ok: true, async json() { return envelope; } };
  };

  const result = await analyseViaBridge('http://localhost:8000', standardDoc(), fakeFetch);
  assert.equal(result.verdict.decision, 'ENTER_LONG');
  assert.equal(result.run_id, 'run-integration-test-001');
});

// ── 2. API unreachable: network error ────────────────────────────────────────

test('Audit 2 — API unreachable: fetch throws network error → propagated', async () => {
  const fakeFetch = async () => {
    throw new TypeError('Failed to fetch');
  };

  await assert.rejects(
    () => postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
      retries: 0,
      timeoutMs: 1000,
    }),
    (err) => {
      assert.ok(err instanceof TypeError || err instanceof Error);
      return true;
    },
    'network error must propagate to caller'
  );
});

test('Audit 2 — API unreachable: timeout triggers abort error', async () => {
  const fakeFetch = (_url, opts) => new Promise((_resolve, reject) => {
    opts.signal.addEventListener('abort', () =>
      reject(Object.assign(new Error('aborted'), { name: 'AbortError' }))
    );
  });

  await assert.rejects(
    () => postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
      retries: 0,
      timeoutMs: 50,
    }),
    /timed out/i,
    'must report timeout'
  );
});

test('Audit 2 — API unreachable: retries exhausted then throws last error', async () => {
  let attempts = 0;
  const fakeFetch = async () => {
    attempts++;
    return { ok: false, status: 503, statusText: 'Unavailable', async text() { return 'down'; } };
  };

  await assert.rejects(
    () => postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
      retries: 2,
      retryDelayMs: 0,
    }),
    /503/,
    'final error must reference 503'
  );
  assert.equal(attempts, 3, 'must attempt initial + 2 retries = 3 total');
});

// ── 3. Schema mismatch: malformed / partial envelope ─────────────────────────

test('Audit 2 — schema mismatch: missing verdict key → response still returned (no crash)', async () => {
  // Backend returns an envelope without the verdict key
  const badEnvelope = {
    ticket_draft: { decisionMode: 'WAIT' },
    run_id: 'run-partial',
    source_ticket_id: null,
    usage_summary: {},
  };
  const fakeFetch = async () => ({
    ok: true,
    async json() { return badEnvelope; },
  });

  // The bridge passes through the raw JSON — it does not crash
  const response = await postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
    retries: 0,
  });
  // verdict will be undefined — callers must handle this gracefully
  assert.equal(response.verdict, undefined);
  assert.equal(response.run_id, 'run-partial');
});

test('Audit 2 — schema mismatch: empty object response → no crash', async () => {
  const fakeFetch = async () => ({
    ok: true,
    async json() { return {}; },
  });

  const response = await postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
    retries: 0,
  });
  assert.equal(response.verdict, undefined);
  assert.equal(response.run_id, undefined);
});

test('Audit 2 — schema mismatch: verdict with unexpected shape → passes through', async () => {
  // Backend returns verdict with wrong inner structure
  const weirdEnvelope = {
    verdict: { unexpected_field: 'surprise', decision: null },
    ticket_draft: {},
    run_id: 'run-weird',
    usage_summary: {},
  };
  const fakeFetch = async () => ({
    ok: true,
    async json() { return weirdEnvelope; },
  });

  const response = await postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
    retries: 0,
  });
  // Bridge passes through — it's the UI's responsibility to validate
  assert.equal(response.verdict.decision, null);
  assert.equal(response.verdict.unexpected_field, 'surprise');
});

// ── 4. HTTP error codes ──────────────────────────────────────────────────────

test('Audit 2 — HTTP 422: validation error → throws with detail', async () => {
  // AUDIT FINDING: The bridge retries 422 because the thrown error is caught
  // by the generic catch block which retries all errors regardless of status.
  // isRetriableStatus correctly excludes 422, but the throw falls through to
  // the catch block. This is low-risk (422 will fail identically on retry)
  // but wastes roundtrips. Documented; fix deferred to avoid scope creep.
  let attempts = 0;
  const fakeFetch = async () => {
    attempts++;
    return {
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      async text() { return 'Ground Truth Packet validation failed: missing instrument'; },
    };
  };

  await assert.rejects(
    () => postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
      retries: 2,
      retryDelayMs: 0,
    }),
    /422/,
  );
  // Current behavior: 422 IS retried (3 attempts). See audit finding above.
  assert.equal(attempts, 3, '422 currently retried — see audit finding');
});

test('Audit 2 — HTTP 429: rate limit → retried', async () => {
  let attempts = 0;
  const fakeFetch = async () => {
    attempts++;
    if (attempts === 1) {
      return {
        ok: false,
        status: 429,
        statusText: 'Too Many Requests',
        async text() { return 'Rate limit exceeded'; },
      };
    }
    return { ok: true, async json() { return validEnvelope(); } };
  };

  const response = await postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
    retries: 1,
    retryDelayMs: 0,
  });
  assert.equal(attempts, 2, '429 must trigger retry');
  assert.equal(response.verdict.decision, 'ENTER_LONG');
});

test('Audit 2 — HTTP 500: server error → retried', async () => {
  let attempts = 0;
  const fakeFetch = async () => {
    attempts++;
    return {
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      async text() { return 'Internal pipeline error'; },
    };
  };

  await assert.rejects(
    () => postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
      retries: 1,
      retryDelayMs: 0,
    }),
    /500/,
  );
  assert.equal(attempts, 2, '500 must trigger retry');
});

// ── 5. Response envelope invariants ──────────────────────────────────────────

test('Audit 2 — envelope invariant: usage_summary always present in v2.0+', async () => {
  const envelope = validEnvelope();
  const fakeFetch = async () => ({ ok: true, async json() { return envelope; } });

  const response = await postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
    retries: 0,
  });
  assert.ok(response.usage_summary !== undefined, 'usage_summary must be present');
  assert.equal(typeof response.usage_summary.total_calls, 'number');
  assert.equal(typeof response.usage_summary.total_cost_usd, 'number');
});

test('Audit 2 — envelope invariant: run_id is a non-empty string', async () => {
  const envelope = validEnvelope();
  const fakeFetch = async () => ({ ok: true, async json() { return envelope; } });

  const response = await postAnalyse('http://localhost:8000', new FormData(), fakeFetch, {
    retries: 0,
  });
  assert.equal(typeof response.run_id, 'string');
  assert.ok(response.run_id.length > 0, 'run_id must be non-empty');
});

// ── 6. Health check integration ──────────────────────────────────────────────

test('Audit 2 — health check: unreachable server → throws', async () => {
  const fakeFetch = async () => { throw new TypeError('Failed to fetch'); };

  await assert.rejects(
    () => checkBridgeHealth('http://localhost:8000', fakeFetch),
    (err) => err instanceof Error,
  );
});

test('Audit 2 — health check: degraded (non-200) → throws with status', async () => {
  const fakeFetch = async () => ({
    ok: false,
    status: 503,
    statusText: 'Service Unavailable',
    async text() { return 'shutting down'; },
  });

  await assert.rejects(
    () => checkBridgeHealth('http://localhost:8000', fakeFetch),
    /503/,
  );
});

// ── 7. FormData contract alignment with API ──────────────────────────────────

test('Audit 2 — form contract: all required API fields present in FormData', () => {
  const fd = buildAnalyseFormData(standardDoc());

  // Required fields from FastAPI /analyse endpoint
  const requiredFields = [
    'instrument', 'session', 'timeframes',
    'account_balance', 'min_rr', 'max_risk_per_trade',
    'market_regime', 'news_risk',
  ];

  for (const field of requiredFields) {
    const value = fd.get(field);
    assert.ok(value !== null && value !== undefined,
      `FormData must include required API field: ${field}`);
    assert.ok(String(value).length > 0,
      `FormData field ${field} must be non-empty`);
  }
});

test('Audit 2 — form contract: lens fields are valid boolean strings', () => {
  const fd = buildAnalyseFormData(standardDoc());

  const lensFields = [
    'lens_ict_icc', 'lens_market_structure', 'lens_orderflow',
    'lens_trendlines', 'lens_classical', 'lens_harmonic',
    'lens_smt', 'lens_volume_profile',
  ];

  for (const field of lensFields) {
    const value = fd.get(field);
    assert.ok(value === 'true' || value === 'false',
      `Lens field ${field} must be 'true' or 'false', got: ${value}`);
  }
});

test('Audit 2 — form contract: timeframes is valid JSON array', () => {
  const fd = buildAnalyseFormData(standardDoc());
  const raw = fd.get('timeframes');

  let parsed;
  assert.doesNotThrow(() => { parsed = JSON.parse(raw); }, 'timeframes must be valid JSON');
  assert.ok(Array.isArray(parsed), 'timeframes must be an array');
  for (const tf of parsed) {
    assert.ok(['H4', 'H1', 'M15', 'M5'].includes(tf),
      `timeframe ${tf} must be one of H4/H1/M15/M5`);
  }
});
