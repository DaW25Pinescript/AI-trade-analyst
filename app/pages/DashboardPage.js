/**
 * DashboardPage — Triage board landing surface
 *
 * Answers: "Why should I care about this asset right now?"
 * Triage-first, not form-first. Pre-loaded intelligence.
 *
 * V1.1: Wired to real backend via service layer.
 * Shows truthful data state indicators (unavailable, stale, demo, etc.).
 */

import { createPageHeader } from '../components/PageHeader.js';
import { createSurfaceCard } from '../components/SurfaceCard.js';
import { createStatusBadge } from '../components/StatusBadge.js';
import { fetchTriage } from '../lib/services.js';
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

  // Load triage items through service layer
  const result = await fetchTriage();
  loadingEl.remove();

  const { items, dataState } = result;

  // Data state banner
  if (dataState && dataState !== 'live') {
    const banner = _createDataStateBanner(dataState);
    container.appendChild(banner);
  }

  // Triage grid
  const grid = document.createElement('div');
  grid.className = 'triage-grid';

  if (dataState === 'unavailable') {
    grid.innerHTML = `
      <div class="data-state-empty">
        <h3 class="text-secondary">No triage data available</h3>
        <p class="text-muted">Run the multi-analyst pipeline to generate triage data, or check that analyst/output/ contains analysis files.</p>
      </div>
    `;
  } else if (items.length === 0) {
    grid.innerHTML = '<p class="text-muted">No triage data available. Run the multi-analyst pipeline first.</p>';
  } else {
    items.forEach(item => {
      const card = _createTriageCard(item, dataState);
      grid.appendChild(card);
    });
  }

  container.appendChild(grid);
}

function _createDataStateBanner(dataState) {
  const banner = document.createElement('div');
  banner.className = `data-state-banner data-state-banner--${dataState}`;

  const messages = {
    unavailable: 'No real data available — analyst output directory is empty.',
    stale: 'Data may be outdated — analyst output has not been refreshed recently.',
    partial: 'Some data is missing — partial results are displayed.',
    demo: 'Demo mode — backend is unreachable. Showing sample data for UI preview only.',
    error: 'Error loading data — please check the backend server.',
  };

  banner.innerHTML = `
    <span class="data-state-banner__icon">${_dataStateIcon(dataState)}</span>
    <span class="data-state-banner__text">${messages[dataState] || `Data state: ${dataState}`}</span>
  `;
  return banner;
}

function _dataStateIcon(dataState) {
  const icons = {
    unavailable: '&#9744;',
    stale: '&#9888;',
    partial: '&#9888;',
    demo: '&#9881;',
    error: '&#10006;',
  };
  return icons[dataState] || '';
}

function _createTriageCard(item, globalDataState) {
  const card = createSurfaceCard({ className: 'triage-card' });

  const badgeVariant = item.triageStatus;
  const biasClass = item.biasHint === 'bullish' ? 'state--passed' :
                     item.biasHint === 'bearish' ? 'state--blocked' : 'text-secondary';

  const itemDataState = item.dataState || globalDataState;
  const demoBadge = itemDataState === 'demo'
    ? '<span class="badge badge--demo">Demo data</span>'
    : '';
  const staleBadge = itemDataState === 'stale'
    ? '<span class="badge badge--stale">Stale</span>'
    : '';

  card.bodyElement.innerHTML = `
    <div class="triage-card__top">
      <div class="triage-card__symbol-row">
        <span class="triage-card__symbol">${_escapeHtml(item.symbol)}</span>
        ${createStatusBadge({ text: item.triageStatus, variant: badgeVariant }).outerHTML}
        ${demoBadge}
        ${staleBadge}
      </div>
      <span class="triage-card__bias ${biasClass}">${_escapeHtml(item.biasHint)}</span>
    </div>

    <div class="triage-card__chart-area">
      <div class="triage-card__mini-chart">
        <span class="text-muted">Chart — pending</span>
      </div>
    </div>

    <div class="triage-card__tags">
      ${(item.whyInterestingTags || []).map(tag => `<span class="triage-card__tag">${_escapeHtml(tag)}</span>`).join('')}
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
