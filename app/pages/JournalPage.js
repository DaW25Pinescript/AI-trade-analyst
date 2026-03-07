/**
 * JournalPage — Saved ideas and results
 *
 * V1.1: Reads saved decision records from backend via GET /journal/decisions.
 */

import { createPageHeader } from '../components/PageHeader.js';
import { createSurfaceCard } from '../components/SurfaceCard.js';
import { fetchJournalDecisions } from '../lib/services.js';
import { navigate } from '../lib/router.js';

export async function renderJournalPage(container) {
  container.innerHTML = '';

  container.appendChild(createPageHeader({
    title: 'Trade Journal',
    subtitle: 'Saved decision snapshots — frozen records for later review',
  }));

  // Loading state
  const loadingEl = document.createElement('div');
  loadingEl.className = 'journal-loading';
  loadingEl.innerHTML = '<p class="text-muted">Loading journal records...</p>';
  container.appendChild(loadingEl);

  const records = await fetchJournalDecisions();
  loadingEl.remove();

  if (records.length === 0) {
    const emptyCard = createSurfaceCard({});
    emptyCard.bodyElement.innerHTML = '<p class="text-muted">No saved journeys yet. Complete a journey to see records here.</p>';
    container.appendChild(emptyCard);
    return;
  }

  const list = document.createElement('div');
  list.className = 'journal-list';

  records.forEach(entry => {
    const card = createSurfaceCard({});
    card.bodyElement.innerHTML = `
      <div class="journal-entry">
        <div class="journal-entry__header">
          <span class="journal-entry__symbol">${_escapeHtml(entry.instrument) || '—'}</span>
          <span class="badge badge--ai-prefill">${_escapeHtml(entry.journeyStatus)}</span>
          ${entry.verdict ? `<span class="badge badge--watch">${_escapeHtml(entry.verdict)}</span>` : ''}
        </div>
        <span class="text-muted">${entry.savedAt ? new Date(entry.savedAt).toLocaleString() : (entry.frozenAt ? new Date(entry.frozenAt).toLocaleString() : '—')}</span>
      </div>
    `;
    list.appendChild(card);
  });

  container.appendChild(list);
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
