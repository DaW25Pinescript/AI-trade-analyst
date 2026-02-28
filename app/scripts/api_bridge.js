function parseBool(value, fallback = false) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') return ['true', '1', 'on', 'yes'].includes(value.toLowerCase());
  return fallback;
}

export function buildAnalyseFormData(doc = document) {
  const get = (id, fallback = '') => doc.getElementById(id)?.value || fallback;
  const maybeFile = (id) => doc.getElementById(id)?.files?.[0] || null;

  const fd = new FormData();
  fd.append('instrument', get('asset', 'UNKNOWN'));
  fd.append('session', get('session', 'Unknown'));
  fd.append('timeframes', JSON.stringify(['H4', 'M15', 'M5']));

  fd.append('account_balance', String(parseFloat(get('accountBalance', '10000')) || 10000));
  fd.append('min_rr', String(parseFloat(get('minRR', '2')) || 2));
  fd.append('max_risk_per_trade', String(parseFloat(get('maxStop', '1')) || 1));
  fd.append('max_daily_risk', String(parseFloat(get('maxDailyRisk', '2')) || 2));
  fd.append('no_trade_windows', JSON.stringify([]));

  fd.append('market_regime', get('regime', 'unknown').toLowerCase() || 'unknown');
  fd.append('news_risk', get('volRisk', 'none_noted').toLowerCase().replace(/\s+/g, '_'));
  fd.append('open_positions', JSON.stringify([]));

  fd.append('lens_ict_icc', String(parseBool(get('lensICT', 'true'), true)));
  fd.append('lens_market_structure', String(parseBool(get('lensMS', 'true'), true)));
  fd.append('lens_orderflow', String(parseBool(get('lensOrderflow', 'false'))));
  fd.append('lens_trendlines', String(parseBool(get('lensTrendline', 'false'))));
  fd.append('lens_classical', 'false');
  fd.append('lens_harmonic', 'false');
  fd.append('lens_smt', String(parseBool(get('lensSMT', 'false'))));
  fd.append('lens_volume_profile', 'false');

  const chartH4 = maybeFile('upload-htf');
  const chartM15 = maybeFile('upload-m15');
  const chartM5 = maybeFile('upload-m5');
  const chartOverlay = maybeFile('upload-m15overlay');
  if (chartH4) fd.append('chart_h4', chartH4);
  if (chartM15) fd.append('chart_m15', chartM15);
  if (chartM5) fd.append('chart_m5', chartM5);
  if (chartOverlay) fd.append('chart_m15_overlay', chartOverlay);

  fd.append('overlay_indicator_source', get('broker', 'TradingView'));
  fd.append('overlay_settings_locked', 'true');
  fd.append('overlay_indicator_claims', JSON.stringify(['FVG', 'OrderBlock', 'SessionLiquidity']));

  return fd;
}

export async function postAnalyse(serverUrl, formData, fetchImpl = fetch) {
  const trimmed = (serverUrl || '').trim().replace(/\/$/, '');
  if (!trimmed) throw new Error('Server URL is required.');
  const response = await fetchImpl(`${trimmed}/analyse`, { method: 'POST', body: formData });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Analyse failed (${response.status}): ${detail || response.statusText}`);
  }
  return response.json();
}

export async function analyseViaBridge(serverUrl, doc = document, fetchImpl = fetch) {
  const formData = buildAnalyseFormData(doc);
  return postAnalyse(serverUrl, formData, fetchImpl);
}

export async function checkBridgeHealth(serverUrl, fetchImpl = fetch) {
  const trimmed = (serverUrl || '').trim().replace(/\/$/, '');
  if (!trimmed) throw new Error('Server URL is required.');

  const response = await fetchImpl(`${trimmed}/health`, { method: 'GET' });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Health check failed (${response.status}): ${detail || response.statusText}`);
  }
  return response.json();
}
