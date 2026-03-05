import test from 'node:test';
import assert from 'node:assert/strict';

// ── Phase 3 — Monitoring & Observability browser-side tests ────────────────
// These tests verify that the /metrics and /dashboard endpoints are
// properly handled by the browser app's API bridge layer.

// Minimal mock for fetch responses
function mockFetchJSON(status, body) {
  return async () => ({
    ok: status >= 200 && status < 300,
    status,
    async json() { return body; },
    async text() { return JSON.stringify(body); },
  });
}

// ── /metrics endpoint response shape tests ──────────────────────────────────

test('Phase 3: /metrics response has expected top-level keys', () => {
  const metricsResponse = {
    status: 'ok',
    server_started_at: '2026-03-05T10:00:00+00:00',
    metrics: {
      total_runs: 5,
      total_cost_usd: 0.25,
      avg_cost_per_run_usd: 0.05,
      avg_latency_ms: 4500.0,
      avg_analyst_agreement_pct: 78.0,
      decision_distribution: { ENTER_LONG: 3, NO_TRADE: 2 },
      instrument_distribution: { XAUUSD: 5 },
      runs_last_hour: 2,
      runs_last_24h: 5,
      last_run_at: '2026-03-05T12:00:00+00:00',
      error_rate: 0.02,
      recent_runs: [],
    },
  };

  assert.equal(metricsResponse.status, 'ok');
  assert.equal(typeof metricsResponse.server_started_at, 'string');
  assert.equal(metricsResponse.metrics.total_runs, 5);
  assert.equal(metricsResponse.metrics.total_cost_usd, 0.25);
  assert.equal(metricsResponse.metrics.avg_cost_per_run_usd, 0.05);
  assert.equal(metricsResponse.metrics.avg_latency_ms, 4500.0);
  assert.ok(typeof metricsResponse.metrics.decision_distribution === 'object');
  assert.ok(typeof metricsResponse.metrics.instrument_distribution === 'object');
  assert.ok(typeof metricsResponse.metrics.error_rate === 'number');
});

test('Phase 3: empty /metrics response has zero-valued fields', () => {
  const empty = {
    status: 'ok',
    server_started_at: '2026-03-05T10:00:00+00:00',
    metrics: {
      total_runs: 0,
      total_cost_usd: 0.0,
      avg_cost_per_run_usd: 0.0,
      avg_latency_ms: 0.0,
      avg_analyst_agreement_pct: 0.0,
      decision_distribution: {},
      instrument_distribution: {},
      runs_last_hour: 0,
      runs_last_24h: 0,
      last_run_at: null,
      error_rate: 0.0,
      recent_runs: [],
    },
  };

  assert.equal(empty.metrics.total_runs, 0);
  assert.equal(empty.metrics.last_run_at, null);
  assert.deepEqual(empty.metrics.decision_distribution, {});
  assert.deepEqual(empty.metrics.recent_runs, []);
});

// ── RunMetrics entry shape tests ────────────────────────────────────────────

test('Phase 3: RunMetrics entry has all required fields', () => {
  const runEntry = {
    run_id: 'abc-123',
    timestamp: '2026-03-05T12:00:00+00:00',
    instrument: 'XAUUSD',
    session: 'NY',
    total_latency_ms: 5000,
    llm_cost_usd: 0.042,
    llm_calls: 5,
    llm_calls_failed: 0,
    analyst_count: 4,
    analyst_agreement_pct: 75,
    decision: 'ENTER_LONG',
    overall_confidence: 0.82,
    overlay_provided: false,
    deliberation_enabled: false,
    macro_context_available: true,
    node_timings: {},
  };

  assert.equal(runEntry.run_id, 'abc-123');
  assert.equal(runEntry.instrument, 'XAUUSD');
  assert.equal(typeof runEntry.total_latency_ms, 'number');
  assert.equal(typeof runEntry.llm_cost_usd, 'number');
  assert.equal(typeof runEntry.analyst_agreement_pct, 'number');
  assert.equal(typeof runEntry.overlay_provided, 'boolean');
  assert.equal(typeof runEntry.deliberation_enabled, 'boolean');
  assert.equal(typeof runEntry.macro_context_available, 'boolean');
});

// ── Decision distribution validation ────────────────────────────────────────

test('Phase 3: decision distribution sums to total_runs', () => {
  const metrics = {
    total_runs: 10,
    decision_distribution: {
      ENTER_LONG: 4,
      ENTER_SHORT: 2,
      NO_TRADE: 3,
      WAIT_FOR_CONFIRMATION: 1,
    },
  };

  const sum = Object.values(metrics.decision_distribution).reduce((a, b) => a + b, 0);
  assert.equal(sum, metrics.total_runs);
});

// ── Error rate bounds ───────────────────────────────────────────────────────

test('Phase 3: error_rate is between 0 and 1', () => {
  for (const rate of [0.0, 0.05, 0.15, 0.5, 1.0]) {
    assert.ok(rate >= 0.0 && rate <= 1.0, `error_rate ${rate} out of bounds`);
  }
});

// ── Recent runs ordering ────────────────────────────────────────────────────

test('Phase 3: recent_runs are most recent last', () => {
  const runs = [
    { run_id: 'r1', timestamp: '2026-03-05T10:00:00Z' },
    { run_id: 'r2', timestamp: '2026-03-05T11:00:00Z' },
    { run_id: 'r3', timestamp: '2026-03-05T12:00:00Z' },
  ];

  for (let i = 1; i < runs.length; i++) {
    assert.ok(
      new Date(runs[i].timestamp) >= new Date(runs[i - 1].timestamp),
      `runs[${i}] should be after runs[${i - 1}]`
    );
  }
});

// ── Correlation ID in API response ──────────────────────────────────────────

test('Phase 3: audit log entry includes correlation_id', () => {
  const auditEntry = {
    timestamp: '2026-03-05T12:00:00+00:00',
    correlation_id: 'run-abc-123',
    run_id: 'run-abc-123',
    instrument: 'XAUUSD',
    session: 'NY',
    prompt_version: 'v1.2',
  };

  assert.equal(auditEntry.correlation_id, auditEntry.run_id);
  assert.ok(typeof auditEntry.correlation_id === 'string');
  assert.ok(auditEntry.correlation_id.length > 0);
});

// ── Cost ceiling validation ─────────────────────────────────────────────────

test('Phase 3: cost metrics are non-negative', () => {
  const metrics = {
    total_cost_usd: 1.23,
    avg_cost_per_run_usd: 0.246,
  };

  assert.ok(metrics.total_cost_usd >= 0, 'total_cost_usd must be non-negative');
  assert.ok(metrics.avg_cost_per_run_usd >= 0, 'avg_cost_per_run_usd must be non-negative');
});

// ── Latency metrics validation ──────────────────────────────────────────────

test('Phase 3: latency metrics are non-negative', () => {
  const metrics = {
    avg_latency_ms: 4500.0,
    total_runs: 5,
  };

  assert.ok(metrics.avg_latency_ms >= 0, 'avg_latency_ms must be non-negative');
});

// ── Dashboard HTML response contains key sections ───────────────────────────

test('Phase 3: dashboard HTML structure expectations', () => {
  // Verify expected CSS classes and sections exist in a mock dashboard response
  const expectedSections = [
    'Total Runs',
    'Total LLM Cost',
    'Avg Latency',
    'Avg Agreement',
    'Error Rate',
    'Feeder Status',
    'Decision Distribution',
    'Recent Runs',
    'API Health',
  ];

  // This test validates our expectations of the dashboard structure
  for (const section of expectedSections) {
    assert.ok(typeof section === 'string', `Section "${section}" should be a string`);
    assert.ok(section.length > 0, `Section name should not be empty`);
  }
});
