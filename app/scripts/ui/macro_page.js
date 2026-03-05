import { loadMacroSnapshot, macroState } from '../state/macro_state.js';

// ── Helpers ───────────────────────────────────────────────────────────────

function safeText(value, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
}

function formatTimestamp(value) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return safeText(value);
  return parsed.toLocaleString();
}

function statusClass(status) {
  const normalized = (status || '').toLowerCase();
  if (normalized === 'ok') return 'macro-status--ok';
  if (normalized === 'partial' || normalized === 'degraded') return 'macro-status--warn';
  return 'macro-status--bad';
}

/** Returns a CSS class based on a regime/bias/pressure string. */
function valueClass(value) {
  const v = (value || '').toLowerCase();
  if (v.includes('trending') || v.includes('uptrend')) return 'macro-val--trending';
  if (v.includes('ranging') || v.includes('range')) return 'macro-val--ranging';
  if (v.includes('volatile') || v.includes('news')) return 'macro-val--volatile';
  if (v.includes('bullish') || v.includes('up') || v.includes('risk-on')) return 'macro-val--bullish';
  if (v.includes('bearish') || v.includes('down') || v.includes('risk-off')) return 'macro-val--bearish';
  if (v.includes('neutral') || v.includes('mixed')) return 'macro-val--neutral';
  if (v.includes('high')) return 'macro-val--high';
  if (v.includes('medium') || v.includes('moderate')) return 'macro-val--medium';
  if (v.includes('low')) return 'macro-val--low';
  return '';
}

/** Parse confidence string or float → 0–100 number (for bar fill %). */
function parseConfidencePct(raw) {
  if (raw === null || raw === undefined || raw === '' || raw === '—') return 0;
  const str = String(raw).replace('%', '').trim();
  const num = parseFloat(str);
  if (Number.isNaN(num)) return 0;
  // If it's a 0–1 float, multiply by 100
  return num <= 1 ? Math.round(num * 100) : Math.round(num);
}

// ── Session clock ─────────────────────────────────────────────────────────

const SESSIONS = [
  { key: 'sydney',   name: 'Sydney',   open: 22, close: 7,  wraps: true  },
  { key: 'tokyo',    name: 'Tokyo',    open: 0,  close: 9,  wraps: false },
  { key: 'london',   name: 'London',   open: 7,  close: 16, wraps: false },
  { key: 'new-york', name: 'New York', open: 12, close: 21, wraps: false },
];

function isSessionActive(session, utcHour) {
  if (session.wraps) return utcHour >= session.open || utcHour < session.close;
  return utcHour >= session.open && utcHour < session.close;
}

function getActiveSessions(utcHour) {
  return SESSIONS.map(s => ({ ...s, active: isSessionActive(s, utcHour) }));
}

function fmtHour(h) {
  const suffix = h < 12 ? 'AM' : 'PM';
  const display = h % 12 === 0 ? 12 : h % 12;
  return `${display}${suffix}`;
}

function renderSessionItems(containerEl, utcClockEl) {
  const now = new Date();
  const utcHour = now.getUTCHours();
  const utcMin = now.getUTCMinutes();

  const sessions = getActiveSessions(utcHour);

  // Count how many are active for overlap detection
  const activeCount = sessions.filter(s => s.active).length;

  containerEl.innerHTML = sessions.map(s => {
    const cls = s.active ? (activeCount >= 2 ? 'overlap' : 'active') : '';
    const stateLabel = s.active ? (activeCount >= 2 ? 'Overlap' : 'Open') : 'Closed';
    const hours = s.wraps
      ? `${fmtHour(s.open)} UTC – ${fmtHour(s.close)} UTC`
      : `${fmtHour(s.open)} – ${fmtHour(s.close)} UTC`;
    return `<div class="session-item ${cls}" aria-label="${s.name} session ${stateLabel}">
      <div class="session-dot"></div>
      <div class="session-info">
        <div class="session-name">${s.name}</div>
        <div class="session-hours">${hours}</div>
      </div>
      <div class="session-state">${stateLabel}</div>
    </div>`;
  }).join('');

  if (utcClockEl) {
    const utcStr = `UTC ${String(utcHour).padStart(2, '0')}:${String(utcMin).padStart(2, '0')}`;
    utcClockEl.textContent = utcStr;
  }
}

// ── Macro page render ─────────────────────────────────────────────────────

function renderSourceHealth(sourceHealth = {}) {
  const entries = Object.entries(sourceHealth);
  if (!entries.length) return '<li class="macro-list-empty">No source health data.</li>';
  return entries
    .map(([name, health]) => {
      const status = safeText(health?.status, 'unknown');
      const refresh = formatTimestamp(health?.last_updated);
      const error = health?.error ? `<div class="macro-health-error">${safeText(health.error)}</div>` : '';
      return `<li class="macro-source-row">
        <div><strong>${name}</strong><span class="macro-status ${statusClass(status)}">${status}</span></div>
        <div class="macro-source-meta">Last refresh: ${refresh}</div>
        ${error}
      </li>`;
    })
    .join('');
}

function renderEvents(events = []) {
  if (!events.length) return '<li class="macro-list-empty">No normalized macro events yet.</li>';
  return events
    .slice(0, 12)
    .map((event) => `<li class="macro-event-row">
      <div class="macro-event-title">${safeText(event.title)}</div>
      <div class="macro-event-meta">${formatTimestamp(event.timestamp)} · ${safeText(event.category)} · ${safeText(event.source)} · importance: ${safeText(event.importance, 'n/a')}</div>
    </li>`)
    .join('');
}

export function renderMacroPage() {
  const context = macroState.context || {};
  const events = macroState.eventBatch?.events || [];

  const regime = safeText(context.regime);
  const volBias = safeText(context.vol_bias);
  const directional = safeText(context.directional_pressure);
  const confidence = safeText(context.confidence);

  const regimeEl = document.getElementById('macroRegimeLabel');
  if (regimeEl) { regimeEl.textContent = regime; regimeEl.className = valueClass(regime); }

  const volEl = document.getElementById('macroVolBias');
  if (volEl) { volEl.textContent = volBias; volEl.className = valueClass(volBias); }

  const pressureEl = document.getElementById('macroDirectionalPressure');
  if (pressureEl) { pressureEl.textContent = directional; pressureEl.className = valueClass(directional); }

  const confEl = document.getElementById('macroConfidence');
  if (confEl) { confEl.textContent = confidence; confEl.className = valueClass(confidence); }

  // Confidence bar
  const pct = parseConfidencePct(context.confidence);
  const barEl = document.getElementById('macroConfidenceBar');
  if (barEl) {
    barEl.style.width = `${pct}%`;
    barEl.style.background = pct >= 70 ? 'var(--green)' : pct >= 40 ? 'var(--amber)' : 'var(--red)';
  }

  document.getElementById('macroFreshness').textContent = formatTimestamp(macroState.observability.lastUpdated);

  const feederEl = document.getElementById('macroFeederStatus');
  if (feederEl) {
    feederEl.textContent = safeText(macroState.observability.feederStatus);
    feederEl.className = `macro-status ${statusClass(macroState.observability.feederStatus)}`;
  }

  const explanation = Array.isArray(context.explanation) ? context.explanation : [];
  document.getElementById('macroReasoningText').textContent = explanation.join(' ') || 'No MRO explanation available.';
  document.getElementById('macroTopDrivers').textContent = (context.top_drivers || []).join(', ') || '—';

  const conflictEl = document.getElementById('macroConflictScore');
  if (conflictEl) conflictEl.textContent = safeText(context.conflict_score);

  document.getElementById('macroSourceHealthList').innerHTML = renderSourceHealth(macroState.sourceHealth);
  document.getElementById('macroEventList').innerHTML = renderEvents(events);

  // Session clock
  const sessionClock = document.getElementById('sessionClock');
  const sessionUtcClock = document.getElementById('sessionUtcClock');
  if (sessionClock) renderSessionItems(sessionClock, sessionUtcClock);
}

// ── Scout page render ─────────────────────────────────────────────────────

const WATCHLIST = [
  { ticker: 'XAUUSD', name: 'Gold',        cls: 'commodity', corr: 'risk-off hedge, inverse DXY' },
  { ticker: 'DXY',    name: 'US Dollar',   cls: 'index',     corr: 'macro anchor, inverse gold/EUR' },
  { ticker: 'SPX500', name: 'S&P 500',     cls: 'index',     corr: 'risk-on proxy' },
  { ticker: 'NAS100', name: 'Nasdaq 100',  cls: 'index',     corr: 'risk-on, rate-sensitive' },
  { ticker: 'EURUSD', name: 'Euro / USD',  cls: 'fx',        corr: 'inverse DXY' },
  { ticker: 'GBPUSD', name: 'Cable',       cls: 'fx',        corr: 'risk-correlated' },
  { ticker: 'BTCUSDT',name: 'Bitcoin',     cls: 'crypto',    corr: 'risk-on speculative' },
  { ticker: 'XAGUSD', name: 'Silver',      cls: 'commodity', corr: 'risk-off/industrial' },
];

const PLAYBOOK = [
  {
    regime: 'trending',
    label: 'Trending',
    rules: [
      'Trade with HTF structure — buy higher lows, sell lower highs',
      'Enter on pullbacks to 0.5–0.618 retracement POIs',
      'Trail stop on structural pivots; avoid premature exits',
      'Avoid counter-trend setups unless extremely high-probability',
    ],
  },
  {
    regime: 'ranging',
    label: 'Ranging',
    rules: [
      'Buy support, sell resistance — fade range extremes',
      'Wait for rejection confirmation before entry',
      'Target range midpoint or opposite boundary',
      'Avoid breakout trades until sustained close outside range',
    ],
  },
  {
    regime: 'volatile',
    label: 'Volatile / News-driven',
    rules: [
      'Reduce position size by 30–50%',
      'Wait for news event to pass before entry',
      'Trade post-impulse retracement with tight stops',
      'Default to wait / no-trade if confluence is unclear',
    ],
  },
];

function getBiasForAsset(ticker, macroContext) {
  const pressure = (macroContext.directional_pressure || '').toLowerCase();
  const regime   = (macroContext.regime || '').toLowerCase();

  // Simple heuristic alignment
  if (ticker === 'DXY') {
    if (pressure.includes('risk-off') || pressure.includes('up')) return 'bullish';
    if (pressure.includes('risk-on') || pressure.includes('down')) return 'bearish';
  }
  if (ticker === 'XAUUSD' || ticker === 'XAGUSD') {
    if (pressure.includes('risk-off')) return 'bullish';
    if (pressure.includes('risk-on')) return 'caution';
  }
  if (['SPX500', 'NAS100', 'BTCUSDT'].includes(ticker)) {
    if (pressure.includes('risk-on')) return 'bullish';
    if (pressure.includes('risk-off')) return 'bearish';
  }
  if (ticker === 'EURUSD' || ticker === 'GBPUSD') {
    if (pressure.includes('risk-on')) return 'bullish';
    if (pressure.includes('risk-off')) return 'bearish';
  }
  return 'neutral';
}

function renderAssetTable(macroContext) {
  const hasMacro = macroContext && (macroContext.directional_pressure || macroContext.regime);
  const rows = WATCHLIST.map(asset => {
    const bias = hasMacro ? getBiasForAsset(asset.ticker, macroContext) : 'neutral';
    const biasLabel = bias.charAt(0).toUpperCase() + bias.slice(1);
    return `<tr>
      <td><span class="asset-ticker">${asset.ticker}</span></td>
      <td>${asset.name}</td>
      <td class="asset-class-col"><span class="asset-class-pill ${asset.cls}">${asset.cls}</span></td>
      <td><span class="align-badge ${bias}">${biasLabel}</span></td>
      <td style="color:var(--muted);font-size:11px;">${asset.corr}</td>
    </tr>`;
  }).join('');

  return `<table class="asset-align-table">
    <thead>
      <tr>
        <th>Ticker</th>
        <th>Instrument</th>
        <th class="asset-class-col">Class</th>
        <th>Macro Bias</th>
        <th>Correlation Note</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function renderPlaybook(currentRegime) {
  const normalized = (currentRegime || '').toLowerCase();
  return PLAYBOOK.map(p => {
    const isActive = normalized.includes(p.regime) || (p.regime === 'volatile' && normalized.includes('news'));
    const activeCls = isActive ? 'active-regime' : '';
    const rules = p.rules.map(r => `<li>${r}</li>`).join('');
    return `<div class="playbook-card ${activeCls}" data-regime="${p.regime}">
      <div class="playbook-regime-label">
        <span class="regime-dot"></span>${p.label}${isActive ? ' — Current' : ''}
      </div>
      <ul class="playbook-rules">${rules}</ul>
    </div>`;
  }).join('');
}

export function renderScoutPage() {
  const context = macroState.context || {};
  const hasMacro = !!(context.regime || context.directional_pressure);

  const noDataEl = document.getElementById('scoutNomacro');
  if (noDataEl) noDataEl.style.display = hasMacro ? 'none' : 'flex';

  // Session grid
  const grid = document.getElementById('scoutSessionGrid');
  const utc = document.getElementById('scoutUtcClock');
  if (grid) renderSessionItems(grid, utc);

  // Asset table
  const tableEl = document.getElementById('scoutAssetTable');
  if (tableEl) tableEl.innerHTML = renderAssetTable(context);

  // Playbook
  const playbookEl = document.getElementById('scoutPlaybook');
  if (playbookEl) playbookEl.innerHTML = renderPlaybook(context.regime);
}

export async function initMacroPage() {
  try {
    await loadMacroSnapshot();
    renderMacroPage();
  } catch (error) {
    const el = document.getElementById('macroReasoningText');
    if (el) el.textContent = `Unable to load macro snapshot: ${error.message}`;
  }
}

export function renderDashboardSessions() {
  const clock = document.getElementById('dashSessionClock');
  const utc = document.getElementById('dashSessionUtcClock');
  if (clock) renderSessionItems(clock, utc);
}

export function initScoutPage() {
  // Scout renders from macroState which may already be loaded
  renderScoutPage();
}

// ── Navigation ────────────────────────────────────────────────────────────

function _setNavActive(activeId) {
  document.querySelectorAll('.top-nav-toggle .btn-ghost').forEach((btn) => {
    btn.classList.toggle('btn-ghost--active', btn.dataset.view === activeId);
  });
}

function _hideAllViews() {
  const workflow = document.getElementById('workflowView');
  const macro    = document.getElementById('macroView');
  const scout    = document.getElementById('scoutView');
  if (workflow) workflow.style.display = 'none';
  if (macro)    macro.style.display    = 'none';
  if (scout)    scout.style.display    = 'none';
}

export function showMacroPage() {
  _hideAllViews();
  const el = document.getElementById('macroView');
  if (el) el.style.display = 'block';
  _setNavActive('macro');
  renderMacroPage();
}

export function showScoutPage() {
  _hideAllViews();
  const el = document.getElementById('scoutView');
  if (el) el.style.display = 'block';
  _setNavActive('scout');
  renderScoutPage();
}

export function showWorkflowPage() {
  _hideAllViews();
  const el = document.getElementById('workflowView');
  if (el) el.style.display = 'block';
  _setNavActive('workflow');
}
