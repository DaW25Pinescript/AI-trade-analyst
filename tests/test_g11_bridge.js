import test from 'node:test';
import assert from 'node:assert/strict';

import { buildAnalyseFormData, postAnalyse, checkBridgeHealth } from '../app/scripts/api_bridge.js';

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

test('postAnalyse posts to /analyse and returns JSON', async () => {
  const fakeFetch = async (url, options) => {
    assert.equal(url, 'http://localhost:8000/analyse');
    assert.equal(options.method, 'POST');
    assert.ok(options.body instanceof FormData);
    return {
      ok: true,
      async json() {
        return { decision: 'NO_TRADE', overall_confidence: 0.4 };
      }
    };
  };

  const fd = new FormData();
  const verdict = await postAnalyse('http://localhost:8000/', fd, fakeFetch);
  assert.equal(verdict.decision, 'NO_TRADE');
  assert.equal(verdict.overall_confidence, 0.4);
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
        return { decision: 'LONG', overall_confidence: 0.71 };
      }
    };
  };

  const verdict = await postAnalyse('http://localhost:8000/', new FormData(), fakeFetch, {
    retries: 1,
    retryDelayMs: 0,
    timeoutMs: 500,
  });

  assert.equal(calls, 2);
  assert.equal(verdict.decision, 'LONG');
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
