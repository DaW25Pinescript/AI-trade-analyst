/**
 * EvidencePanel — Evidence/attachment container
 *
 * Simple baseline for v1. Communicates that files belong to the decision record.
 */

/**
 * Creates an evidence panel.
 * @param {Object} options
 * @param {string[]} options.evidenceRefs
 * @param {Function} [options.onAdd]
 * @param {Function} [options.onRemove]
 * @returns {HTMLElement}
 */
export function createEvidencePanel({ evidenceRefs = [], onAdd, onRemove }) {
  const panel = document.createElement('div');
  panel.className = 'evidence-panel';

  panel.innerHTML = `
    <div class="evidence-panel__header">
      <h4 class="evidence-panel__title">Evidence & Attachments</h4>
      <span class="text-muted">${evidenceRefs.length} item${evidenceRefs.length !== 1 ? 's' : ''}</span>
    </div>
    <div class="evidence-panel__list">
      ${evidenceRefs.map((ref, i) => `
        <div class="evidence-panel__item" data-index="${i}">
          <span class="evidence-panel__name">${_escapeHtml(ref)}</span>
          ${onRemove ? `<button class="evidence-panel__remove" data-ref="${_escapeHtml(ref)}">✕</button>` : ''}
        </div>
      `).join('') || '<p class="text-muted">No evidence attached.</p>'}
    </div>
    ${onAdd ? `
      <div class="evidence-panel__add">
        <input type="file" class="evidence-panel__input" style="display:none">
        <button class="btn btn--sm btn--ghost">Attach Evidence</button>
      </div>
    ` : ''}
  `;

  if (onAdd) {
    const addBtn = panel.querySelector('.evidence-panel__add button');
    const fileInput = panel.querySelector('.evidence-panel__input');
    addBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
      if (e.target.files[0]) {
        onAdd(e.target.files[0].name);
        e.target.value = '';
      }
    });
  }

  if (onRemove) {
    panel.querySelectorAll('.evidence-panel__remove').forEach(btn => {
      btn.addEventListener('click', () => onRemove(btn.dataset.ref));
    });
  }

  return panel;
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
