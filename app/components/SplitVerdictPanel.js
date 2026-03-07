/**
 * SplitVerdictPanel — Three-panel layout for SystemVerdict / UserDecision / ExecutionPlan
 *
 * UI_STYLE_GUIDE.md Section 9.4: These must remain visually distinct.
 * CONSTRAINTS.md 1.6: Do not collapse into one convenience object.
 */

import { createSurfaceCard } from './SurfaceCard.js';
import { createStatusBadge, createProvenanceBadge } from './StatusBadge.js';

/**
 * Creates the split verdict panel.
 * @param {Object} options
 * @param {import('../types/journey.js').SystemVerdict|null} options.systemVerdict
 * @param {import('../types/journey.js').UserDecision|null} options.userDecision
 * @param {import('../types/journey.js').ExecutionPlan|null} options.executionPlan
 * @param {Function} [options.onUserDecisionChange]
 * @param {Function} [options.onExecutionPlanChange]
 * @returns {HTMLElement}
 */
export function createSplitVerdictPanel({
  systemVerdict,
  userDecision,
  executionPlan,
  onUserDecisionChange,
  onExecutionPlanChange,
}) {
  const panel = document.createElement('div');
  panel.className = 'split-verdict-panel';

  // Panel 1: System Verdict (read-only, AI-generated)
  const verdictCard = createSurfaceCard({ title: 'System Verdict', className: 'split-verdict-panel__system' });
  verdictCard.bodyElement.appendChild(_renderSystemVerdict(systemVerdict));
  panel.appendChild(verdictCard);

  // Panel 2: User Decision (human commitment)
  const decisionCard = createSurfaceCard({ title: 'User Decision', className: 'split-verdict-panel__decision' });
  decisionCard.bodyElement.appendChild(_renderUserDecision(userDecision, onUserDecisionChange));
  panel.appendChild(decisionCard);

  // Panel 3: Execution Plan (human commitment)
  const planCard = createSurfaceCard({ title: 'Execution Plan', className: 'split-verdict-panel__plan' });
  planCard.bodyElement.appendChild(_renderExecutionPlan(executionPlan, onExecutionPlanChange));
  panel.appendChild(planCard);

  return panel;
}

function _renderSystemVerdict(verdict) {
  const el = document.createElement('div');
  el.className = 'system-verdict';

  if (!verdict) {
    el.innerHTML = '<p class="text-muted">No system verdict available.</p>';
    return el;
  }

  const badgeVariant = _verdictBadgeVariant(verdict.verdict);

  el.innerHTML = `
    <div class="system-verdict__provenance">${createProvenanceBadge('ai_prefill').outerHTML}</div>
    <div class="system-verdict__row">
      <span class="system-verdict__label">Verdict</span>
      <span class="badge badge--${badgeVariant}">${_formatVerdict(verdict.verdict)}</span>
    </div>
    <div class="system-verdict__row">
      <span class="system-verdict__label">Confidence</span>
      <span class="text-secondary">${verdict.confidence || '—'}</span>
    </div>
    <div class="system-verdict__row">
      <span class="system-verdict__label">Bias</span>
      <span class="text-secondary">${verdict.directionalBias || '—'}</span>
    </div>
    <div class="system-verdict__row">
      <span class="system-verdict__label">Consensus</span>
      <span class="text-secondary">${verdict.consensusState || '—'}</span>
    </div>
    ${verdict.noTradeEnforced ? '<div class="system-verdict__flag badge badge--blocked">No-Trade Enforced</div>' : ''}
    <div class="system-verdict__summary">
      <span class="system-verdict__label">Summary</span>
      <p class="text-secondary">${_escapeHtml(verdict.winningSummary)}</p>
    </div>
  `;

  return el;
}

function _renderUserDecision(decision, onChange) {
  const el = document.createElement('div');
  el.className = 'user-decision';

  const actions = ['take_trade', 'pass', 'watch', 'conditional_entry'];
  const currentAction = decision?.action || '';

  el.innerHTML = `
    <div class="user-decision__provenance">${createProvenanceBadge('user_manual').outerHTML}</div>
    <div class="user-decision__actions">
      ${actions.map(action => `
        <button class="btn btn--sm ${currentAction === action ? 'btn--active' : 'btn--ghost'}" data-action="${action}">
          ${_formatAction(action)}
        </button>
      `).join('')}
    </div>
    <div class="user-decision__rationale">
      <label class="form-label">Rationale</label>
      <textarea class="form-textarea" placeholder="Why this decision?" rows="3">${_escapeHtml(decision?.rationale || '')}</textarea>
    </div>
  `;

  if (onChange) {
    el.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        onChange({ action: btn.dataset.action, rationale: el.querySelector('textarea').value });
      });
    });
    el.querySelector('textarea').addEventListener('change', (e) => {
      onChange({ action: currentAction, rationale: e.target.value });
    });
  }

  return el;
}

function _renderExecutionPlan(plan, onChange) {
  const el = document.createElement('div');
  el.className = 'execution-plan';

  el.innerHTML = `
    <div class="execution-plan__provenance">${createProvenanceBadge('user_manual').outerHTML}</div>
    <div class="execution-plan__fields">
      <div class="form-group">
        <label class="form-label">Direction</label>
        <select class="form-select" data-field="direction">
          <option value="">—</option>
          <option value="long" ${plan?.direction === 'long' ? 'selected' : ''}>Long</option>
          <option value="short" ${plan?.direction === 'short' ? 'selected' : ''}>Short</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Entry Price</label>
        <input class="form-input" type="number" step="any" data-field="entryPrice" value="${plan?.entryPrice || ''}" placeholder="—">
      </div>
      <div class="form-group">
        <label class="form-label">Stop Loss</label>
        <input class="form-input" type="number" step="any" data-field="stopLoss" value="${plan?.stopLoss || ''}" placeholder="—">
      </div>
      <div class="form-group">
        <label class="form-label">Take Profit</label>
        <input class="form-input" type="number" step="any" data-field="takeProfit" value="${plan?.takeProfit || ''}" placeholder="—">
      </div>
      <div class="form-group">
        <label class="form-label">Position Size</label>
        <input class="form-input" type="number" step="any" data-field="positionSize" value="${plan?.positionSize || ''}" placeholder="—">
      </div>
      <div class="form-group">
        <label class="form-label">Entry Type</label>
        <select class="form-select" data-field="entryType">
          <option value="">—</option>
          <option value="market" ${plan?.entryType === 'market' ? 'selected' : ''}>Market</option>
          <option value="limit" ${plan?.entryType === 'limit' ? 'selected' : ''}>Limit</option>
          <option value="stop" ${plan?.entryType === 'stop' ? 'selected' : ''}>Stop</option>
        </select>
      </div>
      <div class="form-group form-group--full">
        <label class="form-label">Notes</label>
        <textarea class="form-textarea" data-field="notes" rows="2" placeholder="Execution notes">${_escapeHtml(plan?.notes || '')}</textarea>
      </div>
    </div>
  `;

  if (onChange) {
    el.querySelectorAll('input, select, textarea').forEach(input => {
      input.addEventListener('change', () => {
        const formData = {};
        el.querySelectorAll('[data-field]').forEach(f => {
          const val = f.value;
          formData[f.dataset.field] = f.type === 'number' ? (val ? parseFloat(val) : null) : (val || null);
        });
        onChange(formData);
      });
    });
  }

  return el;
}

function _verdictBadgeVariant(verdict) {
  if (verdict === 'long_bias' || verdict === 'short_bias') return 'actionable';
  if (verdict === 'conditional') return 'conditional';
  if (verdict === 'no_trade') return 'avoid';
  return 'watch';
}

function _formatVerdict(verdict) {
  return (verdict || 'unknown').replace(/_/g, ' ').toUpperCase();
}

function _formatAction(action) {
  return (action || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
