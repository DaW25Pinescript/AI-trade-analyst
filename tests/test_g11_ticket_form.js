/**
 * test_g11_ticket_form.js — Unit tests for applyTicketDraftToForm()
 *
 * Exercises the form pre-population logic against a minimal DOM stub
 * without requiring a browser. A global `document` stub is installed
 * so that the imported callbacks (selectRadio, evaluateGate,
 * onShadowModeChange, onDecisionModeChange) can run without throwing.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { applyTicketDraftToForm } from '../app/scripts/ui/ticket_form.js';

// ── DOM stub helpers ──────────────────────────────────────────────────────────

/** Returns a minimal element stub covering all properties used by the form. */
function makeEl(extra = {}) {
  const el = {
    value: '',
    checked: false,
    textContent: '',
    className: '',
    style: {},
    dataset: {},
    options: [],
    offsetWidth: 0,
    classList: {
      _classes: new Set(),
      remove(c) { this._classes.delete(c); },
      add(c)    { this._classes.add(c); },
      contains(c) { return this._classes.has(c); },
    },
    _events: {},
    dispatchEvent(evt) {
      (this._events[evt.type] || []).forEach(h => h(evt));
    },
    addEventListener(type, fn) {
      this._events[type] = this._events[type] || [];
      this._events[type].push(fn);
    },
    querySelectorAll(_sel) { return []; },
    querySelector(_sel)    { return null; },
    ...extra,
  };
  return el;
}

/**
 * Builds a fake document and sets it as globalThis.document.
 *
 * Side-effect stubs for all IDs accessed internally by the imported callbacks
 * (evaluateGate, onDecisionModeChange, onShadowModeChange, selectRadio) are
 * pre-registered so those functions do not throw.
 *
 * @param {Object} formEls  id → stub for elements the current test cares about
 * @returns {{ doc, els }}  doc is the fake document; els is the full element map
 */
function makeDoc(formEls = {}) {
  const els = {
    // evaluateGate() elements (gates.js accesses document directly)
    gateBadge:   makeEl(),
    gateStatus:  makeEl(),
    gateText:    makeEl(),
    waitPanel:   makeEl(),
    noTradeToggle: makeEl({ checked: false }),
    // onDecisionModeChange()
    conditionalWrap: makeEl(),
    // onShadowModeChange()
    shadowModeToggle:  makeEl({ checked: false }),
    shadowBadge:       makeEl(),
    shadowOutcomeCard: makeEl(),
    // Caller-supplied elements override defaults above
    ...formEls,
  };

  const doc = { getElementById(id) { return els[id] ?? null; } };
  globalThis.document = doc;   // satisfy callbacks that use document directly
  return { doc, els };
}

// ── Draft factory ─────────────────────────────────────────────────────────────

function makeDraft(overrides = {}) {
  return {
    decisionMode: 'LONG',
    rawAIReadBias: 'Bullish',
    aiEdgeScore: 0.72,
    entry: { zone: '1930–1935', priceMin: 1930, priceMax: 1935 },
    stop:  { price: 1925.0, rationale: 'Below 1925.00' },
    targets: [
      { label: 'TP1', price: 1950.0 },
      { label: 'TP2', price: 1960.0 },
    ],
    checklist: { confluenceScore: 8, conviction: 'High' },
    shadowMode: false,
    gate: { status: 'PROCEED', reentryCondition: '' },
    ...overrides,
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

// 1. decisionMode ──────────────────────────────────────────────────────────────

test('applyTicketDraftToForm sets decisionMode select value', () => {
  const { doc, els } = makeDoc({
    decisionMode: makeEl({
      value: 'WAIT',
      options: [{ value: 'LONG' }, { value: 'SHORT' }, { value: 'WAIT' }],
    }),
  });
  applyTicketDraftToForm(makeDraft({ decisionMode: 'LONG' }), doc);
  assert.equal(els.decisionMode.value, 'LONG');
});

test('applyTicketDraftToForm skips decisionMode when value is not an <option>', () => {
  const { doc, els } = makeDoc({
    decisionMode: makeEl({
      value: 'WAIT',
      options: [{ value: 'LONG' }, { value: 'SHORT' }, { value: 'WAIT' }],
    }),
  });
  applyTicketDraftToForm(makeDraft({ decisionMode: 'INVALID_VALUE' }), doc);
  assert.equal(els.decisionMode.value, 'WAIT'); // unchanged
});

// 2. rawAIReadBias ─────────────────────────────────────────────────────────────

test('applyTicketDraftToForm sets rawAIReadBias select value', () => {
  const { doc, els } = makeDoc({
    rawAIReadBias: makeEl({
      value: '',
      options: [{ value: '' }, { value: 'Bullish' }, { value: 'Bearish' }, { value: 'Neutral' }],
    }),
  });
  applyTicketDraftToForm(makeDraft({ rawAIReadBias: 'Bearish' }), doc);
  assert.equal(els.rawAIReadBias.value, 'Bearish');
});

test('applyTicketDraftToForm skips rawAIReadBias when draft value is empty string', () => {
  const { doc, els } = makeDoc({
    rawAIReadBias: makeEl({
      value: 'Bullish',
      options: [{ value: '' }, { value: 'Bullish' }],
    }),
  });
  applyTicketDraftToForm(makeDraft({ rawAIReadBias: '' }), doc);
  assert.equal(els.rawAIReadBias.value, 'Bullish'); // unchanged
});

// 3. aiEdgeScore ───────────────────────────────────────────────────────────────

test('applyTicketDraftToForm sets aiEdgeScore numeric input', () => {
  const { doc, els } = makeDoc({ aiEdgeScore: makeEl() });
  applyTicketDraftToForm(makeDraft({ aiEdgeScore: 0.72 }), doc);
  assert.equal(els.aiEdgeScore.value, 0.72);
});

test('applyTicketDraftToForm leaves aiEdgeScore unchanged when draft value is null', () => {
  const { doc, els } = makeDoc({ aiEdgeScore: makeEl({ value: '0.5' }) });
  applyTicketDraftToForm(makeDraft({ aiEdgeScore: null }), doc);
  assert.equal(els.aiEdgeScore.value, '0.5'); // unchanged
});

// 4. Entry prices + zone hint ──────────────────────────────────────────────────

test('applyTicketDraftToForm populates entryPriceMin and entryPriceMax when non-null', () => {
  const { doc, els } = makeDoc({
    entryPriceMin: makeEl(),
    entryPriceMax: makeEl(),
  });
  applyTicketDraftToForm(makeDraft({ entry: { zone: '1930–1935', priceMin: 1930, priceMax: 1935 } }), doc);
  assert.equal(els.entryPriceMin.value, 1930);
  assert.equal(els.entryPriceMax.value, 1935);
});

test('applyTicketDraftToForm leaves entry price fields unchanged when priceMin/Max are null', () => {
  const { doc, els } = makeDoc({
    entryPriceMin: makeEl({ value: '1900' }),
    entryPriceMax: makeEl({ value: '1910' }),
  });
  applyTicketDraftToForm(makeDraft({ entry: { zone: '', priceMin: null, priceMax: null } }), doc);
  assert.equal(els.entryPriceMin.value, '1900'); // unchanged
  assert.equal(els.entryPriceMax.value, '1910'); // unchanged
});

test('applyTicketDraftToForm writes entry zone string to aiEntryZoneHint', () => {
  const { doc, els } = makeDoc({ aiEntryZoneHint: makeEl() });
  applyTicketDraftToForm(makeDraft({ entry: { zone: '1930–1935', priceMin: 1930, priceMax: 1935 } }), doc);
  assert.equal(els.aiEntryZoneHint.textContent, '1930–1935');
});

// 5. Stop fields ───────────────────────────────────────────────────────────────

test('applyTicketDraftToForm populates stopPrice when stop.price is non-null', () => {
  const { doc, els } = makeDoc({ stopPrice: makeEl() });
  applyTicketDraftToForm(makeDraft({ stop: { price: 1925.0, rationale: 'Test' } }), doc);
  assert.equal(els.stopPrice.value, 1925.0);
});

test('applyTicketDraftToForm leaves stopPrice unchanged when stop.price is null', () => {
  const { doc, els } = makeDoc({ stopPrice: makeEl({ value: '1900' }) });
  applyTicketDraftToForm(makeDraft({ stop: { price: null, rationale: '' } }), doc);
  assert.equal(els.stopPrice.value, '1900'); // unchanged
});

test('applyTicketDraftToForm populates stopRationale when non-empty', () => {
  const { doc, els } = makeDoc({ stopRationale: makeEl() });
  applyTicketDraftToForm(makeDraft({ stop: { price: 1925.0, rationale: 'Below swing low' } }), doc);
  assert.equal(els.stopRationale.value, 'Below swing low');
});

// 6. Target prices ─────────────────────────────────────────────────────────────

test('applyTicketDraftToForm populates tp1Price and tp2Price from targets[0] and targets[1]', () => {
  const { doc, els } = makeDoc({ tp1Price: makeEl(), tp2Price: makeEl() });
  applyTicketDraftToForm(makeDraft(), doc);
  assert.equal(els.tp1Price.value, 1950.0);
  assert.equal(els.tp2Price.value, 1960.0);
});

test('applyTicketDraftToForm leaves tp2Price unchanged when targets[1] is absent', () => {
  const { doc, els } = makeDoc({
    tp1Price: makeEl(),
    tp2Price: makeEl({ value: '1999' }),
  });
  applyTicketDraftToForm(makeDraft({ targets: [{ label: 'TP1', price: 1950 }] }), doc);
  assert.equal(els.tp1Price.value, 1950);
  assert.equal(els.tp2Price.value, '1999'); // unchanged
});

// 7. Confluence score ──────────────────────────────────────────────────────────

test('applyTicketDraftToForm sets confluenceScore range and fires input event', () => {
  let inputFired = false;
  const range = makeEl({ value: '7' });
  range._events.input = [() => { inputFired = true; }];
  const { doc } = makeDoc({ confluenceScore: range });
  applyTicketDraftToForm(makeDraft({ checklist: { confluenceScore: 9, conviction: 'High' } }), doc);
  assert.equal(range.value, 9);
  assert.ok(inputFired, 'input event should fire to update confVal span');
});

test('applyTicketDraftToForm clamps confluenceScore above 10 to 10', () => {
  const range = makeEl({ value: '7' });
  const { doc } = makeDoc({ confluenceScore: range });
  applyTicketDraftToForm(makeDraft({ checklist: { confluenceScore: 15, conviction: '' } }), doc);
  assert.equal(range.value, 10);
});

test('applyTicketDraftToForm clamps confluenceScore below 1 to 1', () => {
  const range = makeEl({ value: '7' });
  const { doc } = makeDoc({ confluenceScore: range });
  applyTicketDraftToForm(makeDraft({ checklist: { confluenceScore: -3, conviction: '' } }), doc);
  assert.equal(range.value, 1);
});

// 8. Conviction radio ─────────────────────────────────────────────────────────

test('applyTicketDraftToForm calls selectRadio when matching conviction option is found', () => {
  const optStub = makeEl({
    dataset: { val: 'High', sel: 'selected' },
  });
  const rgConviction = makeEl({
    querySelectorAll(_sel) { return [optStub]; },
    querySelector(sel) { return sel.includes('High') ? optStub : null; },
  });
  const { doc } = makeDoc({ 'rg-conviction': rgConviction });
  applyTicketDraftToForm(makeDraft({ checklist: { confluenceScore: 8, conviction: 'High' } }), doc);
  // selectRadio adds dataset.sel class to the matched option
  assert.ok(optStub.classList._classes.has('selected'), 'conviction radio option should be marked selected');
});

test('applyTicketDraftToForm skips selectRadio when conviction option is not found', () => {
  const rgConviction = makeEl({
    querySelectorAll(_sel) { return []; },
    querySelector(_sel) { return null; }, // no matching option
  });
  const { doc } = makeDoc({ 'rg-conviction': rgConviction });
  // Must not throw even though no opt is found
  assert.doesNotThrow(() => {
    applyTicketDraftToForm(makeDraft({ checklist: { confluenceScore: 8, conviction: 'Unknown' } }), doc);
  });
});

// 9. Shadow mode ───────────────────────────────────────────────────────────────

test('applyTicketDraftToForm sets shadowModeToggle.checked to true', () => {
  const toggle = makeEl({ checked: false });
  const { doc, els } = makeDoc({ shadowModeToggle: toggle });
  applyTicketDraftToForm(makeDraft({ shadowMode: true }), doc);
  assert.equal(els.shadowModeToggle.checked, true);
});

test('applyTicketDraftToForm sets shadowModeToggle.checked to false', () => {
  const toggle = makeEl({ checked: true });
  const { doc, els } = makeDoc({ shadowModeToggle: toggle });
  applyTicketDraftToForm(makeDraft({ shadowMode: false }), doc);
  assert.equal(els.shadowModeToggle.checked, false);
});

// 10. Gate display ─────────────────────────────────────────────────────────────

test('applyTicketDraftToForm does not write gate.status directly to gateStatus element', () => {
  // Verify that ticket_form.js does NOT directly write draft.gate.status to the
  // gateStatus element — that is evaluateGate()'s responsibility only.
  // A sparse draft (no conviction → no selectRadio → no evaluateGate) leaves
  // gateStatus textContent at its pre-call value.
  const gateStatus = makeEl({ textContent: 'original' });
  const { doc } = makeDoc({ gateStatus });
  applyTicketDraftToForm({ decisionMode: null, shadowMode: null }, doc);
  assert.equal(gateStatus.textContent, 'original');
});

// 11. Sparse / null drafts ─────────────────────────────────────────────────────

test('applyTicketDraftToForm does not throw when draft is missing entry, stop, targets', () => {
  const { doc } = makeDoc();
  assert.doesNotThrow(() => {
    applyTicketDraftToForm({
      decisionMode: null,
      rawAIReadBias: null,
      aiEdgeScore: null,
      shadowMode: null,
    }, doc);
  });
});

test('applyTicketDraftToForm is a no-op and does not throw when draft is null', () => {
  const { doc } = makeDoc({ decisionMode: makeEl({ value: 'WAIT' }) });
  assert.doesNotThrow(() => applyTicketDraftToForm(null, doc));
});
