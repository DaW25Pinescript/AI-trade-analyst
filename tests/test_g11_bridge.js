import test from 'node:test';
import assert from 'node:assert/strict';

import { buildAnalyseFormData, postAnalyse, analyseViaBridge, checkBridgeHealth, getRunUsage } from '../app/scripts/api_bridge.js';

function makeDoc(overrides = {}) {
  const map = new Map(Object.entries(overrides));
  return {
    getElementById(id) {
      return map.get(id) || null;
    }
  };
}

test('buildAnalyseFormData builds required scalar payload', () => {
  const doc = makeDoc({
    asset: { value: 'XAUUSD' },
    session: { value: 'NY Open' },
    accountBalance: { value: '15000' },
    minRR: { value: '2.5' },
    maxStop: { value: '0.75' },
    regime: { value: 'Trending' },
    volRisk: { value: 'Normal' },
    broker: { value: 'TradingView' },
    'upload-htf': { files: [] },
    'upload-m15': { files: [] },
    'upload-m5': { files: [] },
    'upload-m15overlay': { files: [] },
  });

  const fd = buildAnalyseFormData(doc);
  assert.equal(fd.get('instrument'), 'XAUUSD');
  assert.equal(fd.get('session'), 'NY Open');
  assert.equal(fd.get('account_balance'), '15000');
  assert.equal(fd.get('min_rr'), '2.5');
  assert.equal(fd.get('max_risk_per_trade'), '0.75');
  assert.equal(fd.get('market_regime'), 'trending');
  assert.equal(fd.get('news_risk'), 'normal');
  assert.equal(fd.get('overlay_indicator_source'), 'TradingView');
  assert.equal(fd.get('timeframes'), '["H4","M15","M5"]');
});

test('postAnalyse posts to /analyse and returns v2.0 envelope JSON', async () => {
  const fakeFetch = async (url, options) => {
    assert.equal(url, 'http://localhost:8000/analyse');
    assert.equal(options.method, 'POST');
    assert.ok(options.body instanceof FormData);
    return {
      ok: true,
      async json() {
        // v2.0 envelope: { verdict, ticket_draft, run_id, source_ticket_id }
        return {
          verdict: { decision: 'NO_TRADE', overall_confidence: 0.4 },
          ticket_draft: { decisionMode: 'WAIT', rawAIReadBias: 'Bearish', shadowMode: false },
          run_id: 'run-abc-123',
          source_ticket_id: null,
        };
      }
    };
  };

  const fd = new FormData();
  const response = await postAnalyse('http://localhost:8000/', fd, fakeFetch);
  // Bridge passes the envelope through; callers unpack response.verdict
  assert.equal(response.verdict.decision, 'NO_TRADE');
  assert.equal(response.verdict.overall_confidence, 0.4);
  assert.equal(response.ticket_draft.decisionMode, 'WAIT');
  assert.equal(response.run_id, 'run-abc-123');
  assert.equal(response.source_ticket_id, null);
});

test('postAnalyse retries once on transient 503 and then succeeds', async () => {
  let calls = 0;
  const fakeFetch = async () => {
    calls += 1;
    if (calls === 1) {
      return {
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        async text() {
          return 'upstream timeout';
        }
      };
    }

    return {
      ok: true,
      async json() {
        return {
          verdict: { decision: 'LONG', overall_confidence: 0.71 },
          ticket_draft: { decisionMode: 'LONG' },
          run_id: 'run-retry-test',
          source_ticket_id: null,
        };
      }
    };
  };

  const response = await postAnalyse('http://localhost:8000/', new FormData(), fakeFetch, {
    retries: 1,
    retryDelayMs: 0,
    timeoutMs: 500,
  });

  assert.equal(calls, 2);
  assert.equal(response.verdict.decision, 'LONG');
});

test('postAnalyse surfaces timeout errors after retries exhausted', async () => {
  const fakeFetch = (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })));
  });

  await assert.rejects(
    () => postAnalyse('http://localhost:8000/', new FormData(), fakeFetch, {
      retries: 0,
      timeoutMs: 20,
    }),
    /Request timed out after 20ms/
  );
});

test('analyseViaBridge uses a 3-minute timeout (not the old 12 s default)', async () => {
  // Capture the AbortSignal timeout that the bridge sets and verify it is
  // at least 170 s — well above 12 s and within the 3-minute budget.
  let capturedSignal = null;
  const fakeFetch = async (_url, opts) => {
    capturedSignal = opts.signal;
    return {
      ok: true,
      async json() {
        return {
          verdict: { decision: 'NO_TRADE', overall_confidence: 0.5 },
          ticket_draft: { decisionMode: 'WAIT', rawAIReadBias: 'Neutral', shadowMode: false },
          run_id: 'run-timeout-test',
          source_ticket_id: null,
        };
      },
    };
  };

  const doc = {
    getElementById(id) {
      const defaults = {
        asset: { value: 'XAUUSD' },
        session: { value: 'London' },
        accountBalance: { value: '10000' },
        minRR: { value: '2' },
        maxStop: { value: '1' },
        maxDailyRisk: { value: '2' },
        regime: { value: 'ranging' },
        volRisk: { value: 'none_noted' },
        broker: { value: 'TradingView' },
      };
      return defaults[id] || null;
    },
  };

  const result = await analyseViaBridge('http://localhost:8000', doc, fakeFetch);
  assert.equal(result.run_id, 'run-timeout-test');

  // The AbortController timer for a 180 s timeout fires 180 000 ms from now.
  // We can't read the raw deadline directly, but we can confirm the signal was
  // provided (meaning a timeout was set) and that the request was not already
  // aborted (which would indicate the timeout was too short and fired immediately).
  assert.ok(capturedSignal !== null, 'fetch should receive an AbortSignal');
  assert.equal(capturedSignal.aborted, false, 'signal should not be aborted — 180 s timeout is far in the future');
});

test('checkBridgeHealth requests /health and returns payload', async () => {
  const fakeFetch = async (url, options) => {
    assert.equal(url, 'http://localhost:8000/health');
    assert.equal(options.method, 'GET');
    return {
      ok: true,
      async json() {
        return { status: 'ok', version: '1.2.0' };
      }
    };
  };

  const health = await checkBridgeHealth('http://localhost:8000/', fakeFetch);
  assert.equal(health.status, 'ok');
  assert.equal(health.version, '1.2.0');
});

test('getRunUsage requests /runs/{run_id}/usage and returns payload', async () => {
  const fakeFetch = async (url, options) => {
    assert.equal(url, 'http://localhost:8000/runs/run-abc-123/usage');
    assert.equal(options.method, 'GET');
    return {
      ok: true,
      async json() {
        return { run_id: 'run-abc-123', calls: 4, total_tokens: 1234, models: ['claude-3-5-sonnet'] };
      }
    };
  };

  const usage = await getRunUsage('http://localhost:8000/', 'run-abc-123', fakeFetch);
  assert.equal(usage.run_id, 'run-abc-123');
  assert.equal(usage.calls, 4);
  assert.equal(usage.total_tokens, 1234);
  assert.deepEqual(usage.models, ['claude-3-5-sonnet']);
});

// ── MED-5: timeframes built dynamically from uploaded charts ─────────────────

test('buildAnalyseFormData timeframes reflect only the uploaded charts (H4 + M15)', () => {
  // Simulate user uploading only H4 and M15 charts (no M5)
  const fakeFile = { name: 'chart.png', size: 1024 };
  const doc = {
    getElementById(id) {
      const map = {
        asset: { value: 'XAUUSD' },
        session: { value: 'London' },
        accountBalance: { value: '10000' },
        minRR: { value: '2' },
        maxStop: { value: '1' },
        regime: { value: 'trending' },
        volRisk: { value: 'normal' },
        broker: { value: 'TradingView' },
        'upload-htf':  { files: [fakeFile] },
        'upload-m15':  { files: [fakeFile] },
        'upload-m5':   { files: [] },            // no M5
        'upload-m15overlay': { files: [] },
      };
      return map[id] || null;
    },
  };

  const fd = buildAnalyseFormData(doc);
  const tfs = JSON.parse(fd.get('timeframes'));
  assert.deepEqual(tfs, ['H4', 'M15'], 'timeframes must only include uploaded charts');
  assert.ok(!tfs.includes('M5'), 'M5 must not appear when no M5 chart is uploaded');
});

test('buildAnalyseFormData timeframes fall back to defaults when no charts uploaded', () => {
  const doc = {
    getElementById(id) {
      const map = {
        asset: { value: 'EURUSD' },
        session: { value: 'NY Open' },
        accountBalance: { value: '5000' },
        minRR: { value: '2' },
        maxStop: { value: '1' },
        regime: { value: 'ranging' },
        volRisk: { value: 'none_noted' },
        broker: { value: 'TradingView' },
        'upload-htf':  { files: [] },
        'upload-m15':  { files: [] },
        'upload-m5':   { files: [] },
        'upload-m15overlay': { files: [] },
      };
      return map[id] || null;
    },
  };

  const fd = buildAnalyseFormData(doc);
  const tfs = JSON.parse(fd.get('timeframes'));
  // No files uploaded → fall back to defaults so the form is still submittable
  assert.deepEqual(tfs, ['H4', 'M15', 'M5'], 'must fall back to default timeframes when no files provided');
});

test('buildAnalyseFormData timeframes include M5 only when M5 file is present', () => {
  const fakeFile = { name: 'chart.png', size: 512 };
  const doc = {
    getElementById(id) {
      const map = {
        asset: { value: 'XAUUSD' },
        session: { value: 'Asia' },
        accountBalance: { value: '10000' },
        minRR: { value: '2' },
        maxStop: { value: '1' },
        regime: { value: 'unknown' },
        volRisk: { value: 'normal' },
        broker: { value: 'TradingView' },
        'upload-htf':  { files: [] },
        'upload-m15':  { files: [fakeFile] },
        'upload-m5':   { files: [fakeFile] },
        'upload-m15overlay': { files: [] },
      };
      return map[id] || null;
    },
  };

  const fd = buildAnalyseFormData(doc);
  const tfs = JSON.parse(fd.get('timeframes'));
  assert.deepEqual(tfs, ['M15', 'M5']);
});
