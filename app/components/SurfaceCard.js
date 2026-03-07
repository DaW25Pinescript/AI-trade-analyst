/**
 * SurfaceCard — Standard card for triage items, summaries, review metrics
 *
 * Characteristics (UI_STYLE_GUIDE.md Section 8.2):
 * - Dark neutral fill
 * - Soft border
 * - Strong readability
 * - Moderate elevation
 */

/**
 * Creates a standard surface card.
 * @param {Object} options
 * @param {string} [options.title]
 * @param {string} [options.className] - Additional CSS classes
 * @param {boolean} [options.elevated] - Use elevated surface variant
 * @returns {HTMLElement}
 */
export function createSurfaceCard({ title, className = '', elevated = false } = {}) {
  const card = document.createElement('div');
  card.className = `surface-card ${elevated ? 'surface-card--elevated' : ''} ${className}`.trim();

  if (title) {
    const header = document.createElement('div');
    header.className = 'surface-card__header';
    header.innerHTML = `<h3 class="surface-card__title">${_escapeHtml(title)}</h3>`;
    card.appendChild(header);
  }

  const body = document.createElement('div');
  body.className = 'surface-card__body';
  card.appendChild(body);

  card.bodyElement = body;
  return card;
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
