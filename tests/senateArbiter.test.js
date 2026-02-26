/**
 * senateArbiter.test.js
 *
 * Node.js native test suite for the Trade Senate Protocol.
 * Run with: node --test tests/senateArbiter.test.js
 *
 * 10 test cases covering all acceptance criteria.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { runSenateArbiter } from '../app/scripts/generators/senateArbiter.js';

// ─── Fixtures ────────────────────────────────────────────────────────────────

const BASE_SETTINGS = {
  minRR:                  2.0,
  maxRiskPercent:         1.0,
  sessionVolatilityState: 'Normal',
  regime:                 'Trending',
  instrument:             'XAUUSD',
  timestamp:              '2026-02-26T09:00:00Z',
  newsEventImminent:      false
};

/**
 * Build a valid analyst object. All fields set to sensible defaults;
 * individual tests override specific properties via spread.
 */
function makeAnalyst(overrides = {}) {
  return {
    agentId:             'TechnicalAnalyst',
    direction:           'Long',
    claims:              ['H4 structure is bullish — series of HH/HL intact', 'Price closed above prior week high confirming breakout', 'M15 BOS confirmed to the upside'],
    evidenceTags:        ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'],
    keyLevels: {
      poi:          2620,
      invalidation: 2600,
      targets:      [2660, 2700]
    },
    primaryScenario:      'Pullback to H4 demand zone — confirmed breakout structure on D1 supports Long continuation.',
    alternativeScenario:  'If price closes below 2600, bearish structure forms; Short becomes valid on retest of breakdown level.',
    confidence:           80,
    uncertaintyReason:    'LTF not yet aligned — entry timing may require patience.',
    noTradeConditions:    ['Abnormal volatility at entry time', 'News event fires before trigger'],
    ...overrides
  };
}

/** Returns a cloned analyst with keyLevels merged. */
function makeAnalystKL(direction, poi, invalidation, targets, agentId, overrides = {}) {
  return makeAnalyst({
    agentId,
    direction,
    keyLevels: { poi, invalidation, targets },
    ...overrides
  });
}

// ─── Test 1: Procedural Fail — missing analyst fields ─────────────────────

test('1. Procedural fail — missing required analyst field returns PROCEDURAL_FAIL', () => {
  const incompleteAnalyst = {
    agentId:   'TechnicalAnalyst',
    direction: 'Long'
    // missing: claims, evidenceTags, keyLevels, primaryScenario, etc.
  };

  const result = runSenateArbiter([incompleteAnalyst], BASE_SETTINGS);

  assert.equal(result.ruling, 'PROCEDURAL_FAIL');
  assert.ok(result.reason, 'reason should be populated');
  assert.ok(result.reason.includes('TechnicalAnalyst'), 'reason should name the failed agent');
  assert.equal(result.confidence, 0);
  assert.equal(result.senateRecord, null);
  assert.equal(result.order, null);
});

// ─── Test 2: Quorum Pass — 2 of 3 agree Long ─────────────────────────────

test('2. Quorum pass — 2 of 3 agree Long, ruling proceeds past quorum check', () => {
  const analysts = [
    makeAnalystKL('Long',  2620, 2600, [2660, 2700], 'TechnicalAnalyst'),
    makeAnalystKL('Long',  2622, 2598, [2658, 2695], 'MacroContextAnalyst', {
      claims:       ['D1 HTF confirmed bullish close', 'Macro sentiment supports risk-on', 'M15 BOS confirmed upside'],
      evidenceTags: ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed']
    }),
    makeAnalystKL('Wait',  null, null, [],            'RiskAnalyst', {
      claims:            ['LTF alignment pending', 'No clear entry trigger yet', 'Setup quality marginal'],
      evidenceTags:      ['M15-no-trigger'],
      primaryScenario:   'Waiting for LTF confirmation before committing to Long.',
      alternativeScenario: 'If price pulls back to demand zone and closes above, Long is valid.'
    })
  ];

  const result = runSenateArbiter(analysts, BASE_SETTINGS);

  // Must not be a quorum fail or procedural fail
  assert.notEqual(result.ruling, 'PROCEDURAL_FAIL', 'should not be procedural fail');
  assert.notEqual(result.reason,  'Quorum not met',  'should not fail quorum');
  assert.notEqual(result.reason,  'Unresolvable direction conflict');
  // Ruling should be a valid final ruling
  assert.ok(['TRADE', 'CONDITIONAL', 'NO_TRADE'].includes(result.ruling));
  // Dissent must always be present on non-procedural rulings
  assert.ok(result.dissent, 'dissent must be present');
});

// ─── Test 3: Quorum Fail — all analysts disagree ─────────────────────────

test('3. Quorum fail — all analysts disagree in direction → NO_TRADE', () => {
  const analysts = [
    makeAnalystKL('Long',  2620, 2600, [2660], 'TechnicalAnalyst', {
      // Short analyst has no resolvable condition → conflict unresolvable
      alternativeScenario: 'Market structure looks confused.'
    }),
    makeAnalystKL('Short', 2620, 2650, [2570], 'MacroContextAnalyst', {
      claims:              ['H4 bearish, rejecting prior resistance', 'Macro headwinds from DXY', 'M15 break of structure to downside'],
      evidenceTags:        ['H4-resistance-rejection', 'DXY-strength'],
      primaryScenario:     'Short from H4 resistance after bearish close.',
      alternativeScenario: 'Structure unclear.'  // No clear conditional trigger
    }),
    makeAnalystKL('Wait',  null, null, [], 'RiskAnalyst', {
      claims:              ['Direction conflict between analysts', 'No clean setup visible', 'RR unacceptable in current volatility'],
      evidenceTags:        ['no-clear-direction'],
      primaryScenario:     'No trade — direction is contested.'
    })
  ];

  const result = runSenateArbiter(analysts, BASE_SETTINGS);

  assert.equal(result.ruling, 'NO_TRADE');
  // Should be due to unresolvable conflict (no majority direction)
  assert.ok(
    result.reason === 'Unresolvable direction conflict' ||
    result.reason === 'Quorum not met',
    `Expected conflict or quorum fail, got: ${result.reason}`
  );
});

// ─── Test 4: Hard Gate R:R — below minimum → NO_TRADE ────────────────────

test('4. Hard gate R:R — R:R below minimum fires NO_TRADE', () => {
  // Entry: 2620, Invalidation: 2610, TP1: 2622 → RR = (2622-2620)/(2620-2610) = 0.2 < 2.0
  const analysts = [
    makeAnalystKL('Long', 2620, 2610, [2622], 'TechnicalAnalyst', {
      claims:       ['H4 demand zone present', 'M15 BOS confirmed', 'D1 HTF bullish close'],
      evidenceTags: ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'],
      primaryScenario: 'Pullback to H4 demand zone with tight stop for scalp.'
    }),
    makeAnalystKL('Long', 2620, 2610, [2622], 'MacroContextAnalyst', {
      claims:       ['D1 HTF bullish close confirms upside bias', 'Macro supports Long', 'M15 BOS confirmed'],
      evidenceTags: ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'],
      primaryScenario: 'Long on pullback — macro aligns.'
    }),
    makeAnalystKL('Long', 2620, 2610, [2622], 'RiskAnalyst', {
      claims:       ['M15 BOS confirmed upside', 'H4 demand zone valid', 'Structure supports long'],
      evidenceTags: ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'],
      primaryScenario: 'Setup valid but R:R is tight — proceed with caution.'
    })
  ];

  const settings = { ...BASE_SETTINGS, minRR: 2.0 };
  const result = runSenateArbiter(analysts, settings);

  assert.equal(result.ruling, 'NO_TRADE');
  assert.ok(result.vetoReason, 'vetoReason must be populated');
  assert.ok(result.vetoReason.toLowerCase().includes('r:r') ||
            result.vetoReason.toLowerCase().includes('risk'), `vetoReason: ${result.vetoReason}`);
});

// ─── Test 5: Hard Gate Invalidation — no invalidation level → NO_TRADE ────

test('5. Hard gate invalidation — no invalidation level provided → NO_TRADE', () => {
  const analysts = [
    makeAnalystKL('Long', 2620, null, [2660, 2700], 'TechnicalAnalyst', {
      claims:       ['H4 bullish structure', 'D1 HTF bullish close', 'M15 BOS confirmed'],
      evidenceTags: ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'],
      primaryScenario: 'Pullback to H4 demand — no clear invalidation identified yet.'
    }),
    makeAnalystKL('Long', 2622, null, [2658, 2695], 'MacroContextAnalyst', {
      claims:       ['Macro confirms Long bias', 'D1 HTF bullish close', 'H4 demand zone intact'],
      evidenceTags: ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'],
      primaryScenario: 'Long supported by macro — invalidation TBD from structure.'
    }),
    makeAnalystKL('Long', 2618, null, [2655, 2690], 'RiskAnalyst', {
      claims:       ['M15 BOS confirmed upside', 'H4 demand valid', 'Structure bullish'],
      evidenceTags: ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'],
      primaryScenario: 'Long on pullback — no stop level confirmed by structure review.'
    })
  ];

  const result = runSenateArbiter(analysts, BASE_SETTINGS);

  assert.equal(result.ruling, 'NO_TRADE');
  assert.ok(result.vetoReason, 'vetoReason must be set');
  assert.ok(
    result.vetoReason.toLowerCase().includes('invalidation'),
    `Expected invalidation veto, got: ${result.vetoReason}`
  );
});

// ─── Test 6: Confidence Score — 3 confluences, no conflict → score = 80 ──

test('6. Confidence score — 3 shared confluences, no direction conflict → score = 80', () => {
  // 3 evidenceTags shared across all 3 analysts → 3 confluences → +30
  // No conflict, regime = Trending, claims contain "confirmed" → no deductions
  // Base 50 + 30 = 80
  const sharedTags = ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'];

  const analysts = [
    makeAnalyst({
      agentId:      'TechnicalAnalyst',
      direction:    'Long',
      evidenceTags: sharedTags,
      claims:       ['H4 structure confirmed bullish', 'D1 close confirmed breakout', 'M15 BOS confirmed upside'],
      keyLevels:    { poi: 2620, invalidation: 2600, targets: [2660, 2700] }
    }),
    makeAnalyst({
      agentId:      'MacroContextAnalyst',
      direction:    'Long',
      evidenceTags: sharedTags,
      claims:       ['Macro confirmed bullish alignment', 'D1 close confirmed trend', 'Sentiment confirmed positive'],
      keyLevels:    { poi: 2622, invalidation: 2598, targets: [2658, 2695] }
    }),
    makeAnalyst({
      agentId:      'RiskAnalyst',
      direction:    'Long',
      evidenceTags: sharedTags,
      claims:       ['Risk confirmed acceptable', 'Structure confirmed H4 demand', 'M15 BOS confirmed entry trigger'],
      keyLevels:    { poi: 2618, invalidation: 2602, targets: [2655, 2695] }
    })
  ];

  const result = runSenateArbiter(analysts, BASE_SETTINGS);

  assert.equal(result.confidence, 80, `Expected 80, got ${result.confidence}`);
});

// ─── Test 7: Confidence Score — direction conflict subtracts 15 ───────────

test('7. Confidence score — direction conflict reduces score by 15', () => {
  // Same setup as test 6 but with 2 Long and 1 Short (resolvable conflict)
  // 3 shared tags → +30, conflict → -15, no regime/anticipation deductions → 50+30-15 = 65
  const sharedTags = ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'];

  const analysts = [
    makeAnalyst({
      agentId:      'TechnicalAnalyst',
      direction:    'Long',
      evidenceTags: sharedTags,
      claims:       ['H4 structure confirmed bullish', 'D1 close confirmed breakout', 'M15 BOS confirmed upside'],
      keyLevels:    { poi: 2620, invalidation: 2600, targets: [2660, 2700] }
    }),
    makeAnalyst({
      agentId:      'MacroContextAnalyst',
      direction:    'Long',
      evidenceTags: sharedTags,
      claims:       ['Macro confirmed bullish', 'D1 confirmed trend', 'Sentiment confirmed positive'],
      keyLevels:    { poi: 2622, invalidation: 2598, targets: [2658, 2695] }
    }),
    makeAnalyst({
      agentId:            'RiskAnalyst',
      direction:          'Short',
      evidenceTags:       sharedTags,
      claims:             ['H4 resistance rejection confirmed', 'D1 bearish close signals weakness', 'M15 confirmed breakdown'],
      primaryScenario:    'Short from H4 resistance — bearish structure confirmed.',
      // Provide a conditional trigger so the conflict is resolvable (→ CONDITIONAL not NO_TRADE)
      alternativeScenario: 'If price closes above 2640 and confirms breakout, Long becomes valid again.',
      keyLevels:          { poi: 2640, invalidation: 2660, targets: [2580, 2550] }
    })
  ];

  const result = runSenateArbiter(analysts, BASE_SETTINGS);

  // Ruling may be CONDITIONAL (conflict, resolvable) but confidence should reflect the -15 penalty
  assert.ok(
    result.ruling === 'CONDITIONAL' || result.ruling === 'TRADE' || result.ruling === 'NO_TRADE',
    `Unexpected ruling: ${result.ruling}`
  );
  assert.equal(result.confidence, 65,
    `Expected confidence 65 (50 + 30 confluences - 15 conflict), got ${result.confidence}`
  );
});

// ─── Test 8: Conditional Mode — resolvable conflict → CONDITIONAL ─────────

test('8. Conditional mode — direction conflict with resolvable trigger → CONDITIONAL', () => {
  const analysts = [
    makeAnalystKL('Long', 2620, 2600, [2680, 2720], 'TechnicalAnalyst', {
      claims:            ['H4 bullish structure confirmed', 'D1 HTF bullish close', 'M15 BOS confirmed upside'],
      evidenceTags:      ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'],
      primaryScenario:   'Pullback to H4 demand zone — confirmed bullish structure supports Long.'
    }),
    makeAnalystKL('Long', 2620, 2600, [2680, 2720], 'MacroContextAnalyst', {
      claims:            ['Macro confirms Long', 'D1 HTF confirmed', 'M15 structure confirmed'],
      evidenceTags:      ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'],
      primaryScenario:   'Long supported by macro environment and confirmed structure.'
    }),
    makeAnalystKL('Short', 2620, 2650, [2570, 2540], 'RiskAnalyst', {
      claims:            ['H4 resistance is strong', 'Risk of reversal if Long fails', 'M15 shows hesitation'],
      evidenceTags:      ['H4-demand-zone', 'H4-resistance-level', 'M15-hesitation'],
      primaryScenario:   'Short if Long thesis breaks down — watch for H4 rejection.',
      // Resolvable conditional trigger
      alternativeScenario: 'If price closes above 2640 on H1 and confirms the breakout, would switch to Long — structure is conditionally valid.',
      noTradeConditions: ['If news event fires before trigger', 'Abnormal volatility at entry']
    })
  ];

  const result = runSenateArbiter(analysts, BASE_SETTINGS);

  assert.equal(result.ruling, 'CONDITIONAL',
    `Expected CONDITIONAL ruling, got ${result.ruling} (reason: ${result.reason})`
  );
  assert.ok(result.conditionalTrigger, 'conditionalTrigger must be non-null on CONDITIONAL ruling');
  assert.ok(
    result.conditionalTrigger.includes('Long'),
    `conditionalTrigger should reference the quorum direction: ${result.conditionalTrigger}`
  );
});

// ─── Test 9: Dissent always present — even on approved TRADE ─────────────

test('9. Dissent always present — TRADE ruling still includes dissent block', () => {
  const sharedTags = ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'];

  const analysts = [
    makeAnalyst({ agentId: 'TechnicalAnalyst',    direction: 'Long', evidenceTags: sharedTags }),
    makeAnalyst({ agentId: 'MacroContextAnalyst', direction: 'Long', evidenceTags: sharedTags,
      claims:       ['Macro confirmed Long', 'D1 close confirmed', 'Sentiment confirmed'],
      keyLevels:    { poi: 2622, invalidation: 2598, targets: [2658, 2695] }
    }),
    makeAnalyst({ agentId: 'RiskAnalyst',         direction: 'Long', evidenceTags: sharedTags,
      claims:       ['Risk confirmed acceptable', 'Structure confirmed', 'M15 confirmed'],
      keyLevels:    { poi: 2618, invalidation: 2602, targets: [2655, 2695] }
    })
  ];

  const result = runSenateArbiter(analysts, BASE_SETTINGS);

  // Whatever the ruling (TRADE, CONDITIONAL, etc.) dissent must be present
  assert.ok(result.dissent !== null && result.dissent !== undefined,
    'dissent must not be null or undefined');
  assert.ok(typeof result.dissent.strongestOpposingCase === 'string' &&
            result.dissent.strongestOpposingCase.length > 0,
    'dissent.strongestOpposingCase must be a non-empty string');
  assert.ok(typeof result.dissent.whatWouldFailFast === 'string' &&
            result.dissent.whatWouldFailFast.length > 0,
    'dissent.whatWouldFailFast must be a non-empty string');
});

// ─── Test 10: Full happy path → TRADE with Plan A/B and dissent ──────────

test('10. Full happy path — valid inputs, quorum, all gates pass → TRADE with orders and dissent', () => {
  const sharedTags = ['H4-demand-zone', 'D1-HTF-bullish-close', 'M15-BOS-confirmed'];

  const analysts = [
    makeAnalyst({
      agentId:      'TechnicalAnalyst',
      direction:    'Long',
      evidenceTags: sharedTags,
      claims:       ['H4 structure confirmed bullish — HH/HL intact', 'D1 closed above prior week high confirming breakout', 'M15 BOS confirmed upside entry trigger'],
      keyLevels:    { poi: 2620, invalidation: 2600, targets: [2680, 2720] },
      primaryScenario:   'Pullback to H4 demand zone — confirmed breakout structure on D1 supports Long continuation.',
      alternativeScenario: 'If price rejects and closes below 2600, bearish structure would form; re-assess Short.',
      confidence:        80
    }),
    makeAnalyst({
      agentId:      'MacroContextAnalyst',
      direction:    'Long',
      evidenceTags: sharedTags,
      claims:       ['Macro environment confirmed bullish via DXY weakness', 'D1 weekly close confirmed upside continuation', 'Risk-on sentiment confirmed across correlated assets'],
      keyLevels:    { poi: 2620, invalidation: 2600, targets: [2680, 2720] },
      primaryScenario:   'Long is confirmed by macro context — DXY weakness and risk-on environment support upside.',
      alternativeScenario: 'If DXY reverses and breaks above resistance, macro flips bearish — would reconsider Long.',
      confidence:        75
    }),
    makeAnalyst({
      agentId:      'RiskAnalyst',
      direction:    'Long',
      evidenceTags: sharedTags,
      claims:       ['R:R confirmed acceptable at 3:1 to both targets', 'Invalidation confirmed at 2600 structural low', 'Setup quality confirmed — pullback setup with BOS entry'],
      keyLevels:    { poi: 2620, invalidation: 2600, targets: [2680, 2720] },
      primaryScenario:   'Long on confirmed pullback to H4 demand — acceptable risk parameters and clear invalidation.',
      alternativeScenario: 'If volatility spikes abnormally, position sizing would need to be cut; wait for stabilisation.',
      confidence:        78
    })
  ];

  const settings = {
    ...BASE_SETTINGS,
    minRR:                  2.0,
    maxRiskPercent:         1.0,
    sessionVolatilityState: 'Normal',
    regime:                 'Trending',
    newsEventImminent:      false
  };

  const result = runSenateArbiter(analysts, settings);

  // ── Ruling ──
  assert.equal(result.ruling, 'TRADE', `Expected TRADE, got ${result.ruling} (reason: ${result.reason}, veto: ${result.vetoReason})`);
  assert.ok(result.confidence >= 55, `Confidence ${result.confidence} should be ≥ 55`);

  // ── Senate Record ──
  assert.ok(result.senateRecord, 'senateRecord must be present');
  assert.ok(result.senateRecord.docket, 'docket must be present');
  assert.equal(result.senateRecord.docket.instrument, 'XAUUSD');
  assert.ok(Array.isArray(result.senateRecord.motions) && result.senateRecord.motions.length === 3,
    'motions must have 3 entries');
  assert.ok(result.senateRecord.pointsOfAgreement.length > 0,
    'pointsOfAgreement must be non-empty when all 3 analysts share evidenceTags');
  assert.ok(result.senateRecord.evidenceLedger.length > 0,
    'evidenceLedger must be populated');

  // ── Order — Plan A ──
  assert.ok(result.order, 'order must be present on TRADE ruling');
  assert.ok(result.order.planA, 'planA must be present');
  assert.ok(typeof result.order.planA.entryModel === 'string' && result.order.planA.entryModel.length > 0);
  assert.ok(typeof result.order.planA.invalidation === 'string' && result.order.planA.invalidation.length > 0);
  assert.ok(typeof result.order.planA.takeProfitLogic === 'string' && result.order.planA.takeProfitLogic.length > 0);
  assert.ok(typeof result.order.planA.managementRule === 'string' && result.order.planA.managementRule.length > 0);
  assert.ok(typeof result.order.planA.riskInstruction === 'string' && result.order.planA.riskInstruction.length > 0);
  assert.ok(result.order.planA.riskInstruction.includes('1%'), 'riskInstruction should embed maxRiskPercent');

  // ── Order — Plan B (null on clean TRADE with no conflict) ──
  assert.equal(result.order.planB, null, 'planB should be null on a clean TRADE ruling with no conflict');

  // ── Dissent ──
  assert.ok(result.dissent, 'dissent must always be present');
  assert.ok(typeof result.dissent.strongestOpposingCase === 'string' &&
            result.dissent.strongestOpposingCase.length > 0);
  assert.ok(typeof result.dissent.whatWouldFailFast === 'string' &&
            result.dissent.whatWouldFailFast.length > 0);

  // ── Meta ──
  assert.equal(result.vetoReason, null, 'vetoReason should be null when all gates pass');
  assert.equal(result.conditionalTrigger, null, 'conditionalTrigger should be null on TRADE');
});
