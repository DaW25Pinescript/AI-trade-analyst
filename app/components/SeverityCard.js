/**
 * SeverityCard — Elevated severe-treatment card for gate/compliance surfaces
 *
 * UI_STYLE_GUIDE.md Section 8.5:
 * - Stronger border contrast
 * - Rose/red severity accents where appropriate
 * - Stronger visual weight
 * - Intentionally more serious than surrounding screens
 */

/**
 * Creates a severity card for control-boundary moments.
 * @param {Object} options
 * @param {string} options.title
 * @param {string} [options.severity] - 'passed' | 'conditional' | 'blocked'
 * @param {string} [options.bannerText] - Global boundary state text
 * @returns {HTMLElement}
 */
export function createSeverityCard({ title, severity = 'conditional', bannerText } = {}) {
  const card = document.createElement('div');
  card.className = `severity-card severity-card--${severity}`;

  let html = '';
  if (bannerText) {
    html += `<div class="severity-card__banner severity-card__banner--${severity}">${_escapeHtml(bannerText)}</div>`;
  }
  html += `<div class="severity-card__header"><h3 class="severity-card__title">${_escapeHtml(title)}</h3></div>`;

  card.innerHTML = html;

  const body = document.createElement('div');
  body.className = 'severity-card__body';
  card.appendChild(body);

  card.bodyElement = body;
  return card;
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
