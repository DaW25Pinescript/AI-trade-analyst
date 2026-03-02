/**
 * ticket_form.js — Form pre-population from ticket_draft
 *
 * Consumes the ticket_draft object returned by the POST /analyse response
 * envelope and writes values into the corresponding form fields.
 *
 * Only non-null draft fields are written; null fields leave the existing
 * user-entered value untouched. Populated fields receive a brief yellow
 * flash (.draft-applied) to signal auto-fill.
 */

import { selectRadio, onDecisionModeChange, onShadowModeChange } from './form_bindings.js';
import { syncOutput } from './sync_output.js';

// ── Private helpers ───────────────────────────────────────────────────────────

function _flash(el) {
  if (!el) return;
  el.classList.remove('draft-applied');
  void el.offsetWidth; // force reflow so animation restarts
  el.classList.add('draft-applied');
}

function _setSelect(doc, id, value) {
  if (value == null || value === '') return;
  const el = doc.getElementById(id);
  if (!el) return;
  const valid = Array.from(el.options).some(o => o.value === value);
  if (!valid) return;
  el.value = value;
  _flash(el);
}

function _setNumber(doc, id, value) {
  if (value == null || !isFinite(value)) return;
  const el = doc.getElementById(id);
  if (!el) return;
  el.value = value;
  _flash(el);
}

function _setText(doc, id, value) {
  if (value == null || value === '') return;
  const el = doc.getElementById(id);
  if (!el) return;
  el.value = value;
  _flash(el);
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Apply a ticket_draft object to the form fields.
 *
 * @param {Object}   draft - ticket_draft from the /analyse response envelope
 * @param {Document} doc   - document to operate on (defaults to window.document)
 */
export function applyTicketDraftToForm(draft, doc = document) {
  if (!draft) return;

  // ── Decision mode ───────────────────────────────────────────────────────────
  if (draft.decisionMode != null) {
    const el = doc.getElementById('decisionMode');
    if (el) {
      const valid = Array.from(el.options).some(o => o.value === draft.decisionMode);
      if (valid) {
        el.value = draft.decisionMode;
        _flash(el);
        onDecisionModeChange(el);
      }
    }
  }

  // ── AI read bias ────────────────────────────────────────────────────────────
  _setSelect(doc, 'rawAIReadBias', draft.rawAIReadBias);

  // ── AI edge score ───────────────────────────────────────────────────────────
  _setNumber(doc, 'aiEdgeScore', draft.aiEdgeScore);

  // ── Entry prices + zone hint ────────────────────────────────────────────────
  if (draft.entry) {
    _setNumber(doc, 'entryPriceMin', draft.entry.priceMin);
    _setNumber(doc, 'entryPriceMax', draft.entry.priceMax);
    const hint = doc.getElementById('aiEntryZoneHint');
    if (hint) hint.textContent = draft.entry.zone || '';
  }

  // ── Stop ────────────────────────────────────────────────────────────────────
  if (draft.stop) {
    _setNumber(doc, 'stopPrice', draft.stop.price);
    _setText(doc, 'stopRationale', draft.stop.rationale);
  }

  // ── Targets ─────────────────────────────────────────────────────────────────
  if (draft.targets) {
    if (draft.targets[0]) _setNumber(doc, 'tp1Price', draft.targets[0].price);
    if (draft.targets[1]) _setNumber(doc, 'tp2Price', draft.targets[1].price);
    // No tp3Price input in HTML — targets[2] silently skipped
  }

  // ── Confluence score ─────────────────────────────────────────────────────────
  if (draft.checklist?.confluenceScore != null) {
    const el = doc.getElementById('confluenceScore');
    if (el) {
      el.value = Math.min(10, Math.max(1, Math.round(draft.checklist.confluenceScore)));
      el.dispatchEvent(new Event('input')); // triggers onSlider() to update confVal span
      _flash(el);
    }
  }

  // ── Conviction radio ─────────────────────────────────────────────────────────
  if (draft.checklist?.conviction) {
    const group = doc.getElementById('rg-conviction');
    if (group) {
      const opt = group.querySelector(`.radio-opt[data-val="${draft.checklist.conviction}"]`);
      if (opt) selectRadio('conviction', opt);
    }
  }

  // ── Shadow mode toggle ───────────────────────────────────────────────────────
  if (draft.shadowMode != null) {
    const el = doc.getElementById('shadowModeToggle');
    if (el) {
      el.checked = Boolean(draft.shadowMode);
      onShadowModeChange();
    }
  }

  // ── Re-entry condition (WAIT gate) ──────────────────────────────────────────
  if (draft.gate?.reentryCondition) {
    _setText(doc, 'reentryCondition', draft.gate.reentryCondition);
  }

  syncOutput();
}
