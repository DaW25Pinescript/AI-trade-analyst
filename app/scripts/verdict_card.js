function esc(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function renderFinalVerdict(verdict) {
  if (!verdict) return '<p class="hint">No verdict available yet.</p>';

  const setups = (verdict.approved_setups || []).map((s) => `
    <li>
      <strong>${esc(s.type)}</strong> · R:R ${esc(s.rr_estimate)} · confidence ${esc(s.confidence)}
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
        <p><strong>Overall Confidence:</strong> ${esc(verdict.overall_confidence)}</p>
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

export function mountFinalVerdict(container, verdict) {
  if (!container) return;
  container.innerHTML = renderFinalVerdict(verdict);
}
