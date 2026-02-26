/**
 * arbiterPanel.js — Senate Record UI Renderer
 *
 * Renders the Trade Senate Protocol output panel into a designated DOM container.
 * All logic stays in senateArbiter.js. This module handles display only.
 *
 * Exports:
 *   initSenatePanel()              — inject the panel shell into the DOM
 *   renderSenatePanel(decision)    — render a senateDecision object
 *   clearSenatePanel()             — reset panel to idle state
 */

const PANEL_ID     = 'senateArbiterPanel';
const CONTAINER_ID = 'senateArbiterWrap';

// ─── Colour tokens (aligned with existing theme variables) ──────────────────

const RULING_COLOURS = {
  TRADE:            { bg: '#0d2b1a', border: '#2ea84b', badge: '#2ea84b', text: '#ffffff' },
  CONDITIONAL:      { bg: '#2b2000', border: '#e8a020', badge: '#e8a020', text: '#ffffff' },
  NO_TRADE:         { bg: '#2b0d0d', border: '#e84040', badge: '#e84040', text: '#ffffff' },
  PROCEDURAL_FAIL:  { bg: '#2b0d0d', border: '#e84040', badge: '#e84040', text: '#ffffff' }
};

// ─── Helpers ────────────────────────────────────────────────────────────────

function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function pill(text, colour) {
  return `<span style="display:inline-block;padding:2px 10px;border-radius:4px;background:${colour}22;border:1px solid ${colour};color:${colour};font-size:11px;font-family:'IBM Plex Mono',monospace;font-weight:600;">${esc(text)}</span>`;
}

function section(title, bodyHtml, expanded = false) {
  const id = `senate-sec-${Math.random().toString(36).slice(2)}`;
  return `
<div class="senate-collapsible" style="border:1px solid #2a2a2a;border-radius:6px;margin-bottom:8px;overflow:hidden;">
  <button
    onclick="document.getElementById('${id}').style.display=document.getElementById('${id}').style.display==='none'?'block':'none';this.querySelector('.senate-chevron').textContent=this.querySelector('.senate-chevron').textContent==='▸'?'▾':'▸'"
    style="width:100%;text-align:left;background:#181818;border:none;padding:10px 14px;cursor:pointer;color:#ccc;font-size:12px;font-family:'IBM Plex Mono',monospace;display:flex;justify-content:space-between;align-items:center;"
  >
    <span>${esc(title)}</span><span class="senate-chevron" style="color:#888;">${expanded ? '▾' : '▸'}</span>
  </button>
  <div id="${id}" style="padding:12px 14px;background:#111;display:${expanded ? 'block' : 'none'};">
    ${bodyHtml}
  </div>
</div>`;
}

function bulletList(items) {
  if (!items || items.length === 0) return '<p style="color:#666;font-size:12px;">— none —</p>';
  return '<ul style="margin:0;padding-left:16px;color:#bbb;font-size:12px;line-height:1.8;">' +
    items.map(i => `<li>${esc(i)}</li>`).join('') +
    '</ul>';
}

// ─── Section renderers ──────────────────────────────────────────────────────

function renderDocket(docket) {
  if (!docket) return '<p style="color:#666;font-size:12px;">No docket data.</p>';
  return `
<table style="width:100%;border-collapse:collapse;font-size:12px;font-family:'IBM Plex Mono',monospace;">
  <tr><td style="color:#888;padding:3px 8px 3px 0;width:120px;">Instrument</td><td style="color:#e0e0e0;">${esc(docket.instrument)}</td></tr>
  <tr><td style="color:#888;padding:3px 8px 3px 0;">Timestamp</td><td style="color:#e0e0e0;">${esc(docket.timestamp)}</td></tr>
  <tr><td style="color:#888;padding:3px 8px 3px 0;">Regime</td><td style="color:#e0e0e0;">${esc(docket.regime)}</td></tr>
  <tr><td style="color:#888;padding:3px 8px 3px 0;">Volatility</td><td style="color:#e0e0e0;">${esc(docket.volatilityState)}</td></tr>
</table>`;
}

function renderMotions(motions) {
  if (!motions || motions.length === 0) return '<p style="color:#666;font-size:12px;">No motions.</p>';
  const dirColour = { Long: '#2ea84b', Short: '#e84040', Wait: '#e8a020' };
  return `<div style="display:flex;flex-wrap:wrap;gap:10px;">` +
    motions.map(m => {
      const c = dirColour[m.direction] || '#888';
      return `<div style="padding:8px 12px;border:1px solid ${c}44;border-radius:6px;background:${c}11;">
        <div style="font-size:11px;color:#888;font-family:'IBM Plex Mono',monospace;">${esc(m.agentId)}</div>
        <div style="font-size:13px;color:${c};font-weight:600;font-family:'IBM Plex Mono',monospace;">${esc(m.direction)}</div>
        <div style="font-size:10px;color:#666;font-family:'IBM Plex Mono',monospace;">conf: ${m.confidence ?? '—'}</div>
      </div>`;
    }).join('') +
    '</div>';
}

function renderEvidenceLedger(ledger) {
  if (!ledger || ledger.length === 0) return '<p style="color:#666;font-size:12px;">No evidence recorded.</p>';
  return ledger.map((item, i) =>
    `<div style="margin-bottom:10px;padding:8px 10px;background:#181818;border-radius:4px;border-left:3px solid #444;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
        <span style="font-size:12px;color:#e0e0e0;font-family:'IBM Plex Mono',monospace;">${i + 1}. ${esc(item.evidence)}</span>
        <span style="font-size:11px;color:#e8a020;font-family:'IBM Plex Mono',monospace;">wt: ${item.weight}</span>
      </div>
      <div style="font-size:10px;color:#666;font-family:'IBM Plex Mono',monospace;">${esc(item.decidingRule)}</div>
      <div style="font-size:10px;color:#555;margin-top:2px;">Sources: ${esc((item.sources || []).join(', '))}</div>
    </div>`
  ).join('');
}

function renderConfidence(confidence, decision) {
  if (confidence == null) return '<p style="color:#666;font-size:12px;">Score not computed.</p>';
  const pct = Math.max(0, Math.min(100, confidence));
  const barColour = pct >= 70 ? '#2ea84b' : pct >= 55 ? '#e8a020' : '#e84040';
  return `
<div style="margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
    <span style="font-size:24px;font-weight:700;font-family:'IBM Plex Mono',monospace;color:${barColour};">${pct}</span>
    <span style="font-size:12px;color:#666;">/ 100</span>
  </div>
  <div style="background:#222;border-radius:4px;height:8px;overflow:hidden;">
    <div style="background:${barColour};width:${pct}%;height:100%;border-radius:4px;transition:width .3s;"></div>
  </div>
  <div style="margin-top:8px;font-size:10px;color:#666;font-family:'IBM Plex Mono',monospace;line-height:1.7;">
    Base: 50 | Confluences: +${Math.min((decision.senateRecord?.evidenceLedger?.filter(e => e.sources?.length >= 2).length || 0) * 10, 30)}
    ${decision.senateRecord?.contestedPoints?.length > 0 ? '| Direction conflict: −15' : ''}
  </div>
</div>`;
}

function renderPlanCard(plan, label, colour) {
  if (!plan) return '';
  return `
<div style="border:1px solid ${colour}44;border-radius:8px;padding:14px;background:${colour}08;margin-bottom:12px;">
  <div style="font-size:11px;color:${colour};font-family:'IBM Plex Mono',monospace;font-weight:600;margin-bottom:10px;letter-spacing:1px;">${esc(label)}</div>
  ${plan.trigger ? `<div style="margin-bottom:8px;padding:6px 10px;background:#2b2000;border-radius:4px;font-size:11px;color:#e8a020;font-family:'IBM Plex Mono',monospace;">⚡ Trigger: ${esc(plan.trigger)}</div>` : ''}
  <table style="width:100%;border-collapse:collapse;font-size:12px;">
    ${[
      ['Entry',       plan.entryModel],
      ['Invalidation', plan.invalidation],
      ['Take Profit',  plan.takeProfitLogic],
      ['Management',   plan.managementRule],
      ['Risk',         plan.riskInstruction]
    ].map(([k, v]) =>
      `<tr><td style="color:#888;padding:4px 10px 4px 0;width:110px;vertical-align:top;font-family:'IBM Plex Mono',monospace;">${k}</td><td style="color:#ddd;padding:4px 0;line-height:1.5;">${esc(v)}</td></tr>`
    ).join('')}
  </table>
  ${plan.doNotTradeIf && plan.doNotTradeIf.length > 0 ? `
  <div style="margin-top:10px;">
    <div style="font-size:10px;color:#e84040;font-family:'IBM Plex Mono',monospace;margin-bottom:4px;">DO NOT TRADE IF:</div>
    ${bulletList(plan.doNotTradeIf)}
  </div>` : ''}
</div>`;
}

function renderDissent(dissent) {
  if (!dissent) return '<p style="color:#666;font-size:12px;">No dissent recorded.</p>';
  return `
<div style="border:1px solid #e8a02055;border-radius:6px;padding:12px;background:#2b1a0011;">
  <div style="font-size:11px;color:#e8a020;font-family:'IBM Plex Mono',monospace;font-weight:600;margin-bottom:8px;">⚠ MINORITY REPORT</div>
  <p style="color:#ddd;font-size:12px;margin:0 0 10px 0;line-height:1.6;">${esc(dissent.strongestOpposingCase)}</p>
  <div style="padding:8px 10px;background:#1a1000;border-radius:4px;border-left:3px solid #e8402044;">
    <span style="font-size:11px;color:#e84040;font-family:'IBM Plex Mono',monospace;">FAST FAIL: </span>
    <span style="font-size:12px;color:#ccc;">${esc(dissent.whatWouldFailFast)}</span>
  </div>
</div>`;
}

// ─── Main render ─────────────────────────────────────────────────────────────

/**
 * Render a senate decision object into the panel container.
 * @param {Object} decision  Return value of runSenateArbiter()
 */
export function renderSenatePanel(decision) {
  const container = document.getElementById(CONTAINER_ID);
  if (!container) {
    console.warn('[arbiterPanel] Container #' + CONTAINER_ID + ' not found.');
    return;
  }

  const ruling = decision.ruling || 'NO_TRADE';
  const colours = RULING_COLOURS[ruling] || RULING_COLOURS.NO_TRADE;
  const rec     = decision.senateRecord || {};

  const conditionalBox = (ruling === 'CONDITIONAL' && decision.conditionalTrigger)
    ? `<div style="margin-bottom:12px;padding:12px 14px;border-radius:6px;background:#2b200044;border:1px solid #e8a020;color:#e8a020;font-size:13px;font-family:'IBM Plex Mono',monospace;">
        ⚠ Only trade if: ${esc(decision.conditionalTrigger)}
      </div>`
    : '';

  const vetoBox = decision.vetoReason
    ? `<div style="margin-bottom:12px;padding:10px 14px;border-radius:6px;background:#2b0d0d44;border:1px solid #e84040;color:#e84040;font-size:12px;font-family:'IBM Plex Mono',monospace;">
        🚫 Gate fired: ${esc(decision.vetoReason)}
      </div>`
    : '';

  const reasonBox = decision.reason && ruling !== 'TRADE'
    ? `<div style="margin-bottom:8px;font-size:12px;color:#888;font-family:'IBM Plex Mono',monospace;">Reason: ${esc(decision.reason)}</div>`
    : '';

  // Build all sections
  const sectionsHtml = [

    section('01 · Docket',
      renderDocket(rec.docket),
      false),

    section('02 · Motions',
      renderMotions(rec.motions),
      false),

    section('03 · Points of Agreement',
      bulletList(rec.pointsOfAgreement),
      false),

    section('04 · Contested Points',
      bulletList(rec.contestedPoints),
      false),

    section('05 · Evidence Ledger',
      renderEvidenceLedger(rec.evidenceLedger),
      false),

    section('06 · Confidence Score',
      renderConfidence(decision.confidence, decision),
      false),

    // Ruling — expanded by default
    section(`07 · Ruling — ${ruling}`,
      `<div style="margin-bottom:10px;">
        ${conditionalBox}${vetoBox}${reasonBox}
        <div style="font-size:28px;font-weight:700;font-family:'IBM Plex Mono',monospace;color:${colours.badge};">${esc(ruling)}</div>
        <div style="font-size:12px;color:#888;margin-top:4px;">Confidence: ${decision.confidence ?? '—'}/100</div>
      </div>`,
      true),

    // Orders — expanded by default
    section('08 · Orders',
      decision.order
        ? renderPlanCard(decision.order.planA, 'PLAN A — PRIMARY', '#2ea84b') +
          (decision.order.planB ? renderPlanCard(decision.order.planB, 'PLAN B — CONDITIONAL', '#e8a020') : '')
        : '<p style="color:#666;font-size:12px;">No orders generated (ruling is NO_TRADE or PROCEDURAL_FAIL).</p>',
      true)

  ].join('');

  container.innerHTML = `
<div id="${PANEL_ID}" style="margin-top:20px;">
  <!-- ── Header ── -->
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;padding:14px;border-radius:8px;background:${colours.bg};border:1px solid ${colours.border};">
    <div style="padding:6px 16px;border-radius:4px;background:${colours.badge};color:#fff;font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:13px;letter-spacing:1px;">${esc(ruling)}</div>
    <div>
      <div style="font-size:14px;color:#e0e0e0;font-weight:600;">Trade Senate Protocol</div>
      <div style="font-size:11px;color:#888;font-family:'IBM Plex Mono',monospace;">${esc(rec.docket?.instrument || '—')} · ${esc(rec.docket?.timestamp || '—')}</div>
    </div>
    <div style="margin-left:auto;font-size:20px;font-weight:700;font-family:'IBM Plex Mono',monospace;color:${colours.badge};">${decision.confidence ?? '—'}<span style="font-size:12px;color:#666;">/100</span></div>
  </div>

  <!-- ── Collapsible sections 01–08 ── -->
  ${sectionsHtml}

  <!-- ── Dissent — always visible ── -->
  <div style="margin-top:12px;">
    <div style="font-size:11px;color:#e8a020;font-family:'IBM Plex Mono',monospace;font-weight:600;margin-bottom:8px;letter-spacing:1px;">09 · DISSENT — MANDATORY</div>
    ${renderDissent(decision.dissent)}
  </div>
</div>`;
}

/**
 * Clear the panel back to its idle state.
 */
export function clearSenatePanel() {
  const container = document.getElementById(CONTAINER_ID);
  if (container) container.innerHTML = '';
}

/**
 * Inject the panel wrapper and input area into section-5 (Output step).
 * Called once from main.js on window.onload.
 */
export function initSenatePanel() {
  const outputSection = document.getElementById('section-5');
  if (!outputSection) return;
  if (document.getElementById(CONTAINER_ID)) return; // already injected

  const wrapper = document.createElement('div');
  wrapper.className = 'card';
  wrapper.innerHTML = `
<div class="card-label" style="color:#e8a020;">Trade Senate Protocol</div>
<p class="step-note">
  Paste the JSON array of analyst outputs below, then click <strong>Run Senate</strong>.
  Each analyst object must match the required schema (agentId, direction, claims, evidenceTags,
  keyLevels, primaryScenario, alternativeScenario, confidence, uncertaintyReason, noTradeConditions).
</p>
<textarea
  id="senateAnalystInput"
  rows="6"
  placeholder='[{"agentId":"TechnicalAnalyst","direction":"Long","claims":["H4 bullish structure"],"evidenceTags":["H4-demand"],"keyLevels":{"poi":1.0850,"invalidation":1.0800,"targets":[1.0920,1.0970]},"primaryScenario":"Pullback to H4 demand zone","alternativeScenario":"If price closes below 1.0820 short becomes valid","confidence":75,"uncertaintyReason":"LTF not yet aligned","noTradeConditions":["Abnormal volatility","News event imminent"]}]'
  style="width:100%;box-sizing:border-box;background:#111;color:#ddd;border:1px solid #333;border-radius:4px;padding:10px;font-family:'IBM Plex Mono',monospace;font-size:11px;resize:vertical;margin-bottom:10px;"
></textarea>
<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:4px;">
  <button class="btn btn-primary" onclick="runSenateArb()" style="font-size:12px;">Run Senate ⚖</button>
  <button class="btn btn-ghost" onclick="clearSenateArb()" style="font-size:12px;">Clear</button>
</div>
<div id="${CONTAINER_ID}"></div>`;

  // Insert before the btn-row at end of section-5
  const btnRow = outputSection.querySelector('.btn-row');
  if (btnRow) {
    outputSection.insertBefore(wrapper, btnRow);
  } else {
    outputSection.appendChild(wrapper);
  }
}
