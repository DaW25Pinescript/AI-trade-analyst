/**
 * StatusBadge — Semantic state badge
 *
 * Used for triage status, gate state, verdict indication.
 * Badges communicate state and provenance — compact, readable, semantic.
 */

/**
 * Creates a status badge element.
 * @param {Object} options
 * @param {string} options.text
 * @param {string} options.variant - 'actionable'|'conditional'|'watch'|'avoid'|'passed'|'blocked'|'ai-prefill'|'user-confirm'|'user-override'|'user-manual'
 * @returns {HTMLElement}
 */
export function createStatusBadge({ text, variant }) {
  const badge = document.createElement('span');
  badge.className = `badge badge--${variant}`;
  badge.textContent = text;
  return badge;
}

/**
 * Creates a provenance badge.
 * @param {string} provenance - One of Provenance enum values
 * @returns {HTMLElement}
 */
export function createProvenanceBadge(provenance) {
  const labels = {
    'ai_prefill': 'AI Prefill',
    'user_confirm': 'Confirmed',
    'user_override': 'Override',
    'user_manual': 'Manual',
  };

  return createStatusBadge({
    text: labels[provenance] || provenance,
    variant: provenance.replace('_', '-'),
  });
}
