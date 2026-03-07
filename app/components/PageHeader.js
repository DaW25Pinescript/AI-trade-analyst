/**
 * PageHeader — Page-level title and context bar
 */

/**
 * Creates a page header element.
 * @param {Object} options
 * @param {string} options.title
 * @param {string} [options.subtitle]
 * @param {string} [options.badgeText]
 * @param {string} [options.badgeVariant] - CSS class suffix (e.g. 'actionable', 'blocked')
 * @returns {HTMLElement}
 */
export function createPageHeader({ title, subtitle, badgeText, badgeVariant }) {
  const header = document.createElement('header');
  header.className = 'page-header';

  let html = `<div class="page-header__content">`;
  html += `<h1 class="page-header__title">${_escapeHtml(title)}</h1>`;
  if (subtitle) {
    html += `<p class="page-header__subtitle">${_escapeHtml(subtitle)}</p>`;
  }
  html += `</div>`;

  if (badgeText) {
    const variant = badgeVariant ? `badge--${badgeVariant}` : '';
    html += `<span class="badge ${variant}">${_escapeHtml(badgeText)}</span>`;
  }

  header.innerHTML = html;
  return header;
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
