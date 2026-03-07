/**
 * JournalPage — Saved ideas and results
 */

import { createPageHeader } from '../components/PageHeader.js';
import { createSurfaceCard } from '../components/SurfaceCard.js';
import { loadSnapshotIndex, loadSnapshot } from '../lib/services.js';
import { navigate } from '../lib/router.js';

export async function renderJournalPage(container) {
  container.innerHTML = '';

  container.appendChild(createPageHeader({
    title: 'Trade Journal',
    subtitle: 'Saved decision snapshots — frozen records for later review',
  }));

  const index = await loadSnapshotIndex();

  if (index.length === 0) {
    const emptyCard = createSurfaceCard({});
    emptyCard.bodyElement.innerHTML = '<p class="text-muted">No saved journeys yet. Complete a journey to see records here.</p>';
    container.appendChild(emptyCard);
    return;
  }

  const list = document.createElement('div');
  list.className = 'journal-list';

  index.forEach(entry => {
    const card = createSurfaceCard({});
    card.bodyElement.innerHTML = `
      <div class="journal-entry">
        <div class="journal-entry__header">
          <span class="journal-entry__symbol">${entry.instrument || '—'}</span>
          <span class="badge badge--ai-prefill">${entry.journeyStatus}</span>
        </div>
        <span class="text-muted">${entry.frozenAt ? new Date(entry.frozenAt).toLocaleString() : '—'}</span>
      </div>
    `;
    list.appendChild(card);
  });

  container.appendChild(list);
}
