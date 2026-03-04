import { loadMacroSnapshot, macroState } from '../state/macro_state.js';

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

  document.getElementById('macroRegimeLabel').textContent = safeText(context.regime);
  document.getElementById('macroVolBias').textContent = safeText(context.vol_bias);
  document.getElementById('macroDirectionalPressure').textContent = safeText(context.directional_pressure);
  document.getElementById('macroConfidence').textContent = safeText(context.confidence);
  document.getElementById('macroFreshness').textContent = formatTimestamp(macroState.observability.lastUpdated);
  document.getElementById('macroFeederStatus').textContent = safeText(macroState.observability.feederStatus);
  document.getElementById('macroFeederStatus').className = `macro-status ${statusClass(macroState.observability.feederStatus)}`;

  const explanation = Array.isArray(context.explanation) ? context.explanation : [];
  document.getElementById('macroReasoningText').textContent = explanation.join(' ') || 'No MRO explanation available.';
  document.getElementById('macroTopDrivers').textContent = (context.top_drivers || []).join(', ') || '—';
  document.getElementById('macroConflictScore').textContent = safeText(context.conflict_score);

  document.getElementById('macroSourceHealthList').innerHTML = renderSourceHealth(macroState.sourceHealth);
  document.getElementById('macroEventList').innerHTML = renderEvents(events);
}

export async function initMacroPage() {
  try {
    await loadMacroSnapshot();
    renderMacroPage();
  } catch (error) {
    document.getElementById('macroReasoningText').textContent = `Unable to load macro snapshot: ${error.message}`;
  }
}

function _setNavActive(activeId) {
  document.querySelectorAll('.top-nav-toggle .btn-ghost').forEach((btn) => {
    btn.classList.toggle('btn-ghost--active', btn.dataset.view === activeId);
  });
}

export function showMacroPage() {
  document.getElementById('workflowView').style.display = 'none';
  document.getElementById('macroView').style.display = 'block';
  _setNavActive('macro');
}

export function showWorkflowPage() {
  document.getElementById('workflowView').style.display = 'block';
  document.getElementById('macroView').style.display = 'none';
  _setNavActive('workflow');
}
