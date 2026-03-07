/**
 * AIPrefillCard — System-generated context block with indigo provenance marker
 *
 * UI_STYLE_GUIDE.md Section 10.4:
 * - Indigo-toned badge or marker
 * - Labeled section headers
 * - Stable formatting
 */

import { createProvenanceBadge } from './StatusBadge.js';

/**
 * Creates an AI prefill card.
 * @param {Object} options
 * @param {string} options.title
 * @param {Object[]} [options.fields] - Array of { label, value } pairs
 * @param {string} [options.summary] - Text summary
 * @returns {HTMLElement}
 */
export function createAIPrefillCard({ title, fields = [], summary }) {
  const card = document.createElement('div');
  card.className = 'ai-prefill-card';

  const header = document.createElement('div');
  header.className = 'ai-prefill-card__header';
  header.innerHTML = `<h4 class="ai-prefill-card__title">${_escapeHtml(title)}</h4>`;
  header.appendChild(createProvenanceBadge('ai_prefill'));
  card.appendChild(header);

  if (fields.length > 0) {
    const fieldList = document.createElement('div');
    fieldList.className = 'ai-prefill-card__fields';
    fields.forEach(({ label, value }) => {
      fieldList.innerHTML += `
        <div class="ai-prefill-card__field">
          <span class="ai-prefill-card__label">${_escapeHtml(label)}</span>
          <span class="ai-prefill-card__value">${_escapeHtml(String(value ?? '—'))}</span>
        </div>
      `;
    });
    card.appendChild(fieldList);
  }

  if (summary) {
    const summaryEl = document.createElement('p');
    summaryEl.className = 'ai-prefill-card__summary';
    summaryEl.textContent = summary;
    card.appendChild(summaryEl);
  }

  return card;
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
