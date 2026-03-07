/**
 * GateChecklist — Gate rows with passed/conditional/blocked state
 *
 * UI_STYLE_GUIDE.md Section 9.3 + CONSTRAINTS.md 2.2:
 * - Gate checks are a discipline boundary, NOT decorative
 * - Stronger title treatment
 * - Global boundary state banner
 * - Stacked gate rows with three visually distinct states
 * - Justification area for conditional/blocked items
 * - Disabled progression when policy requires it
 */

import { GateState } from '../types/journey.js';
import { createSeverityCard } from './SeverityCard.js';

/**
 * Creates the gate checklist.
 * @param {Object} options
 * @param {import('../types/journey.js').GateCheckItem[]} options.gates
 * @param {Function} [options.onGateUpdate] - Called with (gateId, newState, justification)
 * @returns {HTMLElement}
 */
export function createGateChecklist({ gates, onGateUpdate }) {
  const overallState = _deriveOverallState(gates);
  const bannerText = _bannerText(overallState);

  const card = createSeverityCard({
    title: 'Gate Checks — Control Boundary',
    severity: overallState,
    bannerText,
  });

  const list = document.createElement('div');
  list.className = 'gate-checklist';

  gates.forEach(gate => {
    const row = _createGateRow(gate, onGateUpdate);
    list.appendChild(row);
  });

  card.bodyElement.appendChild(list);
  return card;
}

function _createGateRow(gate, onGateUpdate) {
  const row = document.createElement('div');
  row.className = `gate-row gate-row--${gate.state}`;
  row.dataset.gateId = gate.id;

  const icon = _stateIcon(gate.state);
  const stateLabel = gate.state.toUpperCase();

  row.innerHTML = `
    <div class="gate-row__indicator">
      <span class="gate-row__icon gate-row__icon--${gate.state}">${icon}</span>
    </div>
    <div class="gate-row__content">
      <div class="gate-row__header">
        <span class="gate-row__label">${_escapeHtml(gate.label)}</span>
        <span class="badge badge--${gate.state}">${stateLabel}</span>
      </div>
      ${gate.detail ? `<p class="gate-row__detail">${_escapeHtml(gate.detail)}</p>` : ''}
      ${gate.state !== GateState.PASSED ? `
        <div class="gate-row__justification">
          <label class="form-label">Justification ${gate.state === GateState.BLOCKED ? '(required to override)' : '(recommended)'}</label>
          <textarea class="form-textarea gate-row__textarea" rows="2" placeholder="Provide justification for proceeding...">${_escapeHtml(gate.justification || '')}</textarea>
        </div>
      ` : ''}
    </div>
    ${gate.source === 'system' && gate.state !== GateState.PASSED && onGateUpdate ? `
      <div class="gate-row__actions">
        <select class="form-select gate-row__state-select" data-gate-id="${gate.id}">
          <option value="blocked" ${gate.state === GateState.BLOCKED ? 'selected' : ''}>Blocked</option>
          <option value="conditional" ${gate.state === GateState.CONDITIONAL ? 'selected' : ''}>Conditional</option>
          <option value="passed" ${gate.state === GateState.PASSED ? 'selected' : ''}>Passed</option>
        </select>
      </div>
    ` : ''}
  `;

  if (onGateUpdate) {
    const select = row.querySelector('.gate-row__state-select');
    const textarea = row.querySelector('.gate-row__textarea');

    if (select) {
      select.addEventListener('change', () => {
        const justification = textarea?.value || '';
        onGateUpdate(gate.id, select.value, justification);
      });
    }
    if (textarea) {
      textarea.addEventListener('change', () => {
        const state = select?.value || gate.state;
        onGateUpdate(gate.id, state, textarea.value);
      });
    }
  }

  return row;
}

function _deriveOverallState(gates) {
  if (gates.some(g => g.state === GateState.BLOCKED)) return 'blocked';
  if (gates.some(g => g.state === GateState.CONDITIONAL)) return 'conditional';
  return 'passed';
}

function _bannerText(state) {
  if (state === 'blocked') return 'FORWARD PROGRESSION BLOCKED — Resolve blocked gates before proceeding';
  if (state === 'conditional') return 'CONDITIONAL — Some gates require attention before proceeding';
  return 'ALL GATES PASSED — Clear to proceed';
}

function _stateIcon(state) {
  if (state === GateState.PASSED) return '✓';
  if (state === GateState.CONDITIONAL) return '⚠';
  return '✕';
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
