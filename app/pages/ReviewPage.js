/**
 * ReviewPage — Review/pattern analysis surface
 *
 * Framing: transparent, rule-based, not black-box.
 * Decision Review Engine / Pattern Review / Policy Refinement.
 */

import { createPageHeader } from '../components/PageHeader.js';
import { createSurfaceCard } from '../components/SurfaceCard.js';
import { loadReviewPatterns } from '../lib/services.js';

export async function renderReviewPage(container) {
  container.innerHTML = '';

  container.appendChild(createPageHeader({
    title: 'Decision Review Engine',
    subtitle: 'Transparent review — planned vs actual, override patterns, gate analysis',
  }));

  const patterns = await loadReviewPatterns();

  // Planned vs Actual comparison panel
  const comparisonCard = createSurfaceCard({ title: 'Planned vs Actual', elevated: true });
  comparisonCard.bodyElement.innerHTML = `
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
      <span class="text-muted">Insufficient data — complete more journeys to populate.</span>
    </div>
  `;
  container.appendChild(overrideCard);

  // Gate failure cluster panel
  const gateCard = createSurfaceCard({ title: 'Gate Failure Patterns' });
  gateCard.bodyElement.innerHTML = `
    <p class="text-muted">Identifies which gates are most frequently blocked or conditionally overridden.</p>
    <div class="review-placeholder">
      <span class="text-muted">Insufficient data — complete more journeys to populate.</span>
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
