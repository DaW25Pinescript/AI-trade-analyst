function esc(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

/**
 * Phase 2a float fix: format a 0.0–1.0 confidence float as a percentage string.
 * Handles both Python-side 0.0–1.0 floats and legacy 0–100 integer values.
 * Returns "N/A" for non-numeric or missing values.
 */
export function formatConfidencePct(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return 'N/A';
  // If value is already in 0–100 range (> 1.0), treat as percentage directly.
  // Otherwise, multiply by 100 to convert 0.0–1.0 to percentage.
  const pct = num > 1.0 ? num : num * 100;
  return `${Math.round(pct)}%`;
}

/**
 * Phase 2a float fix: format a price float to a display string with appropriate
 * decimal places. Gold prices use 2 decimals; forex pairs use 5.
 */
export function formatPrice(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return 'N/A';
  // Heuristic: values > 100 are likely gold/index prices (2 decimals)
  // values < 100 are likely forex rates (5 decimals)
  const decimals = num > 100 ? 2 : 5;
  return num.toFixed(decimals);
}

export function renderFinalVerdict(verdict) {
  if (!verdict) return '<p class="hint">No verdict available yet.</p>';

  const setups = (verdict.approved_setups || []).map((s) => `
    <li>
      <strong>${esc(s.type)}</strong> · R:R ${esc(s.rr_estimate)} · confidence ${formatConfidencePct(s.confidence)}
      <div style="font-size:12px;color:var(--muted);">Entry: ${esc(s.entry_zone)} | Stop: ${esc(s.stop)} | Targets: ${esc((s.targets || []).join(', '))}</div>
    </li>
  `).join('');

  const blockers = (verdict.no_trade_conditions || []).map((c) => `<li>${esc(c)}</li>`).join('');

  return `
    <div class="output-panel" style="margin-top:8px;">
      <div class="output-header">
        <span class="output-title">● FINAL VERDICT</span>
      </div>
      <div style="white-space:normal;font-family:'IBM Plex Mono',monospace;font-size:12px;line-height:1.7;">
        <p><strong>Decision:</strong> ${esc(verdict.decision)}</p>
        <p><strong>Final Bias:</strong> ${esc(verdict.final_bias)}</p>
        <p><strong>Overall Confidence:</strong> ${formatConfidencePct(verdict.overall_confidence)}</p>
        <p><strong>Analyst Agreement:</strong> ${esc(verdict.analyst_agreement_pct)}%</p>
        <p><strong>Arbiter Notes:</strong> ${esc(verdict.arbiter_notes)}</p>
        <div><strong>Approved Setups:</strong>
          ${setups ? `<ul>${setups}</ul>` : '<p>None</p>'}
        </div>
        <div><strong>No-Trade Conditions:</strong>
          ${blockers ? `<ul>${blockers}</ul>` : '<p>None</p>'}
        </div>
      </div>
    </div>
  `;
}

function formatNumber(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return 'N/A';
  return num.toLocaleString('en-US');
}

function normalizeUsagePayload(usage, runIdFallback = '') {
  const payload = usage && typeof usage === 'object' ? usage : {};
  const totals = payload.totals && typeof payload.totals === 'object' ? payload.totals : {};
  const tokens = payload.tokens && typeof payload.tokens === 'object' ? payload.tokens : {};
  const tokenUsage = payload.token_usage && typeof payload.token_usage === 'object' ? payload.token_usage : {};

  const runId = payload.run_id ?? runIdFallback;
  const calls = payload.calls ?? payload.total_calls ?? totals.calls;
  const totalTokens = payload.total_tokens ?? totals.total_tokens ?? tokens.total ?? tokenUsage.total_tokens;
  const inputTokens = payload.input_tokens ?? totals.input_tokens ?? tokens.input ?? tokenUsage.input_tokens;
  const outputTokens = payload.output_tokens ?? totals.output_tokens ?? tokens.output ?? tokenUsage.output_tokens;

  const modelsRaw = payload.models ?? payload.models_used ?? totals.models ?? [];
  const models = Array.isArray(modelsRaw)
    ? modelsRaw.map((model) => String(model || '').trim()).filter(Boolean)
    : typeof modelsRaw === 'string' ? modelsRaw.split(',').map((model) => model.trim()).filter(Boolean) : [];

  return {
    runId: runId ? String(runId) : 'N/A',
    calls: formatNumber(calls),
    totalTokens: formatNumber(totalTokens),
    inputTokens: formatNumber(inputTokens),
    outputTokens: formatNumber(outputTokens),
    models: models.length ? models.join(', ') : 'Unavailable',
  };
}

export function renderUsageSummary(usage, runIdFallback = '') {
  const summary = normalizeUsagePayload(usage, runIdFallback);

  return `
    <div class="output-panel" style="margin-top:10px;opacity:0.94;">
      <div class="output-header">
        <span class="output-title">● USAGE SUMMARY</span>
      </div>
      <div style="white-space:normal;font-family:'IBM Plex Mono',monospace;font-size:12px;line-height:1.7;">
        <p><strong>Run ID:</strong> ${esc(summary.runId)}</p>
        <p><strong>Total calls:</strong> ${esc(summary.calls)}</p>
        <p><strong>Total tokens:</strong> ${esc(summary.totalTokens)}</p>
        <p><strong>Input tokens:</strong> ${esc(summary.inputTokens)}</p>
        <p><strong>Output tokens:</strong> ${esc(summary.outputTokens)}</p>
        <details style="margin-top:6px;">
          <summary style="cursor:pointer;">Models used</summary>
          <div style="margin-top:4px;">${esc(summary.models)}</div>
        </details>
      </div>
    </div>
  `;
}

export function mountAnalysisResults(container, verdict, usage, runIdFallback = '') {
  if (!container) return;
  container.innerHTML = `${renderFinalVerdict(verdict)}${renderUsageSummary(usage, runIdFallback)}`;
}

export function mountFinalVerdict(container, verdict) {
  if (!container) return;
  container.innerHTML = renderFinalVerdict(verdict);
}
