/**
 * ReviewPage — Review/pattern analysis surface
 *
 * Framing: transparent, rule-based, not black-box.
 * Decision Review Engine / Pattern Review / Policy Refinement.
 *
 * V1.1: Reads saved records from backend via GET /review/records.
 */

import { createPageHeader } from '../components/PageHeader.js';
import { createSurfaceCard } from '../components/SurfaceCard.js';
import { fetchReviewRecords } from '../lib/services.js';

export async function renderReviewPage(container) {
  container.innerHTML = '';

  container.appendChild(createPageHeader({
    title: 'Decision Review Engine',
    subtitle: 'Transparent review — planned vs actual, override patterns, gate analysis',
  }));

  // Loading state
  const loadingEl = document.createElement('div');
  loadingEl.className = 'review-loading';
  loadingEl.innerHTML = '<p class="text-muted">Loading review records...</p>';
  container.appendChild(loadingEl);

  const records = await fetchReviewRecords();
  loadingEl.remove();

  // Saved records summary
  if (records.length > 0) {
    const recordsCard = createSurfaceCard({ title: 'Saved Decision Records', elevated: true });
    let recordsHtml = '<div class="review-records">';
    records.forEach(r => {
      recordsHtml += `
        <div class="review-record">
          <span class="review-record__symbol">${_escapeHtml(r.instrument)}</span>
          <span class="badge badge--ai-prefill">${_escapeHtml(r.journeyStatus)}</span>
          ${r.verdict ? `<span class="badge badge--watch">${_escapeHtml(r.verdict)}</span>` : ''}
          ${r.hasResult ? '<span class="badge badge--passed">Has result</span>' : '<span class="badge badge--conditional">No result</span>'}
          <span class="text-muted">${r.savedAt ? new Date(r.savedAt).toLocaleString() : '—'}</span>
        </div>
      `;
    });
    recordsHtml += '</div>';
    recordsCard.bodyElement.innerHTML = recordsHtml;
    container.appendChild(recordsCard);
  }

  // Planned vs Actual comparison panel
  const comparisonCard = createSurfaceCard({ title: 'Planned vs Actual', elevated: records.length === 0 });
  const hasResults = records.some(r => r.hasResult);
  comparisonCard.bodyElement.innerHTML = hasResults
    ? '<p class="text-muted">Result comparison data available for records with results.</p>'
    : `
      <p class="text-muted">Comparison data populates as journal entries accumulate result snapshots.</p>
      <div class="review-placeholder">
        <span class="text-muted">No result snapshots recorded yet.</span>
      </div>
    `;
  container.appendChild(comparisonCard);

  // Override frequency panel
  const overrideCard = createSurfaceCard({ title: 'Override Frequency Analysis' });
  overrideCard.bodyElement.innerHTML = `
    <p class="text-muted">Tracks how often user decisions diverge from system recommendations.</p>
    <div class="review-placeholder">
      <span class="text-muted">${records.length > 0 ? `${records.length} decision record(s) available.` : 'Insufficient data — complete more journeys to populate.'}</span>
    </div>
  `;
  container.appendChild(overrideCard);

  // Gate failure cluster panel
  const gateCard = createSurfaceCard({ title: 'Gate Failure Patterns' });
  gateCard.bodyElement.innerHTML = `
    <p class="text-muted">Identifies which gates are most frequently blocked or conditionally overridden.</p>
    <div class="review-placeholder">
      <span class="text-muted">${records.length > 0 ? `${records.length} decision record(s) available.` : 'Insufficient data — complete more journeys to populate.'}</span>
    </div>
  `;
  container.appendChild(gateCard);

  // Policy refinement placeholder
  const policyCard = createSurfaceCard({ title: 'Policy Refinement Suggestions' });
  policyCard.bodyElement.innerHTML = `
    <p class="text-muted">Rule-based suggestions for improving decision quality based on accumulated patterns.</p>
    <div class="review-placeholder">
      <span class="text-muted">Requires review pattern data — stub per interface audit.</span>
    </div>
  `;
  container.appendChild(policyCard);
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
