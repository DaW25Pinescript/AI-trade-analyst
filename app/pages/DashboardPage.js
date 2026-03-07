/**
 * DashboardPage — Triage board landing surface
 *
 * Answers: "Why should I care about this asset right now?"
 * Triage-first, not form-first. Pre-loaded intelligence.
 */

import { createPageHeader } from '../components/PageHeader.js';
import { createSurfaceCard } from '../components/SurfaceCard.js';
import { createStatusBadge } from '../components/StatusBadge.js';
import { loadTriageItems } from '../lib/services.js';
import { navigate } from '../lib/router.js';

/**
 * Renders the dashboard page.
 * @param {HTMLElement} container
 */
export async function renderDashboardPage(container) {
  container.innerHTML = '';

  const header = createPageHeader({
    title: 'Market Triage',
    subtitle: 'Pre-loaded intelligence — assets ranked by relevance and opportunity quality',
  });
  container.appendChild(header);

  // Loading state
  const loadingEl = document.createElement('div');
  loadingEl.className = 'triage-loading';
  loadingEl.innerHTML = '<p class="text-muted">Loading triage data...</p>';
  container.appendChild(loadingEl);

  // Load triage items through typed service layer
  const items = await loadTriageItems();
  loadingEl.remove();

  // Triage grid
  const grid = document.createElement('div');
  grid.className = 'triage-grid';

  items.forEach(item => {
    const card = _createTriageCard(item);
    grid.appendChild(card);
  });

  if (items.length === 0) {
    grid.innerHTML = '<p class="text-muted">No triage data available. Run the multi-analyst pipeline first.</p>';
  }

  container.appendChild(grid);
}

function _createTriageCard(item) {
  const card = createSurfaceCard({ className: 'triage-card' });

  const badgeVariant = item.triageStatus;
  const biasClass = item.biasHint === 'bullish' ? 'state--passed' :
                     item.biasHint === 'bearish' ? 'state--blocked' : 'text-secondary';

  card.bodyElement.innerHTML = `
    <div class="triage-card__top">
      <div class="triage-card__symbol-row">
        <span class="triage-card__symbol">${_escapeHtml(item.symbol)}</span>
        ${createStatusBadge({ text: item.triageStatus, variant: badgeVariant }).outerHTML}
      </div>
      <span class="triage-card__bias ${biasClass}">${_escapeHtml(item.biasHint)}</span>
    </div>

    <div class="triage-card__chart-area">
      <div class="triage-card__mini-chart">
        <span class="text-muted">Chart — pending</span>
      </div>
    </div>

    <div class="triage-card__tags">
      ${item.whyInterestingTags.map(tag => `<span class="triage-card__tag">${_escapeHtml(tag)}</span>`).join('')}
    </div>

    <div class="triage-card__confidence">
      <span class="text-muted">Confidence:</span>
      <span class="text-secondary">${_escapeHtml(item.confidence)}</span>
    </div>

    <p class="triage-card__rationale">${_escapeHtml(item.rationaleSummary)}</p>

    <div class="triage-card__action">
      <button class="btn btn--primary btn--sm triage-card__begin" data-symbol="${_escapeHtml(item.symbol)}">
        Begin Journey
      </button>
    </div>
  `;

  const beginBtn = card.bodyElement.querySelector('.triage-card__begin');
  beginBtn.addEventListener('click', () => {
    navigate(`/journey/${item.symbol}`);
  });

  return card;
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
