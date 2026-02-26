/**
 * senateArbiter.js — Trade Senate Protocol
 *
 * Pure function module. No DOM access, no fetch, no side effects.
 * Takes analyst data and user settings → returns structured senate decision.
 *
 * Entry point: runSenateArbiter(analystOutputs, userSettings)
 */

// ─── Required field definitions ────────────────────────────────────────────

const REQUIRED_ANALYST_FIELDS = [
  'agentId', 'direction', 'claims', 'evidenceTags', 'keyLevels',
  'primaryScenario', 'alternativeScenario', 'confidence',
  'uncertaintyReason', 'noTradeConditions'
];
const REQUIRED_KEY_LEVEL_FIELDS = ['poi', 'invalidation', 'targets'];
const VALID_DIRECTIONS = ['Long', 'Short', 'Wait'];

// ─── Step 1: Procedural validation ─────────────────────────────────────────

function validateAnalysts(analysts) {
  for (const analyst of analysts) {
    if (!analyst || typeof analyst !== 'object') {
      return { valid: false, failedAgentId: 'unknown', missingField: 'analyst object' };
    }
    for (const field of REQUIRED_ANALYST_FIELDS) {
      if (!(field in analyst) || analyst[field] === undefined) {
        return { valid: false, failedAgentId: analyst.agentId || 'unknown', missingField: field };
      }
    }
    if (!analyst.keyLevels || typeof analyst.keyLevels !== 'object') {
      return { valid: false, failedAgentId: analyst.agentId, missingField: 'keyLevels (must be object)' };
    }
    for (const kf of REQUIRED_KEY_LEVEL_FIELDS) {
      if (!(kf in analyst.keyLevels)) {
        return { valid: false, failedAgentId: analyst.agentId, missingField: `keyLevels.${kf}` };
      }
    }
    if (!Array.isArray(analyst.claims)) {
      return { valid: false, failedAgentId: analyst.agentId, missingField: 'claims (must be array)' };
    }
    if (!Array.isArray(analyst.evidenceTags)) {
      return { valid: false, failedAgentId: analyst.agentId, missingField: 'evidenceTags (must be array)' };
    }
    if (!Array.isArray(analyst.noTradeConditions)) {
      return { valid: false, failedAgentId: analyst.agentId, missingField: 'noTradeConditions (must be array)' };
    }
    if (!Array.isArray(analyst.keyLevels.targets)) {
      return { valid: false, failedAgentId: analyst.agentId, missingField: 'keyLevels.targets (must be array)' };
    }
    if (!VALID_DIRECTIONS.includes(analyst.direction)) {
      return { valid: false, failedAgentId: analyst.agentId, missingField: `direction (must be one of: ${VALID_DIRECTIONS.join('|')})` };
    }
  }
  return { valid: true };
}

// ─── Step 3: Disagreement detection helpers ─────────────────────────────────

function getDirectionVotes(analysts) {
  const votes = { Long: 0, Short: 0, Wait: 0 };
  for (const a of analysts) {
    if (a.direction in votes) votes[a.direction]++;
  }
  return votes;
}

/**
 * Returns the direction with a clear 2+ vote majority (Long or Short only).
 * Wait is never returned as a quorum direction — it signals abstention.
 */
function getQuorumDirection(votes) {
  if (votes.Long >= 2) return 'Long';
  if (votes.Short >= 2) return 'Short';
  return null;
}

/** Conflict = at least 1 Long vote AND at least 1 Short vote. */
function hasDirectionConflict(votes) {
  return votes.Long > 0 && votes.Short > 0;
}

/**
 * Attempt conditional resolution for a direction conflict.
 * Looks for conditional language in the dissenting analyst's alternativeScenario.
 * Returns a trigger string on success, null on failure.
 */
function resolveConflict(analysts, quorumDirection) {
  if (!quorumDirection) return null; // no majority → unresolvable

  const dissenters = analysts.filter(
    a => a.direction !== quorumDirection && a.direction !== 'Wait'
  );

  for (const dissenter of dissenters) {
    const scenario = (dissenter.alternativeScenario || '').trim();
    if (scenario.length >= 10) {
      const lower = scenario.toLowerCase();
      if (/\bif\b|\bwhen\b|\bonce\b|\bwait\b|\btrigger\b|\bbreaks?\b|\bretests?\b|\bconfirm|\babove\b|\bbelow\b|\bclos(e|ed|ing)\b/.test(lower)) {
        return `Only ${quorumDirection} if: ${scenario}`;
      }
    }
  }
  return null;
}

// ─── Step 4: Evidence helpers ───────────────────────────────────────────────

/** Collect evidenceTags shared by 2+ analysts as points of agreement. */
function buildPointsOfAgreement(analysts) {
  const tagCount = {};
  for (const a of analysts) {
    const seen = new Set(a.evidenceTags);
    for (const tag of seen) {
      tagCount[tag] = (tagCount[tag] || 0) + 1;
    }
  }
  return Object.entries(tagCount)
    .filter(([, count]) => count >= 2)
    .map(([tag]) => tag);
}

/** Build contested-point descriptions where Long and Short analysts disagree. */
function buildContestedPoints(analysts) {
  const contested = [];
  const longA = analysts.filter(a => a.direction === 'Long');
  const shortA = analysts.filter(a => a.direction === 'Short');
  for (const l of longA) {
    for (const s of shortA) {
      contested.push(
        `${l.agentId} (Long) vs ${s.agentId} (Short) — ` +
        `Long: "${l.primaryScenario.slice(0, 80)}" | ` +
        `Short: "${s.primaryScenario.slice(0, 80)}"`
      );
    }
  }
  return contested;
}

/**
 * Build evidence ledger: rank evidenceTags from all analysts by weight.
 * Applies the 4 evidence weighting rules, storing the deciding rule per item.
 */
function buildEvidenceLedger(analysts) {
  const tagCount = {};
  const tagSources = {};

  for (const a of analysts) {
    const seen = new Set();
    for (const tag of a.evidenceTags) {
      if (!seen.has(tag)) {
        tagCount[tag] = (tagCount[tag] || 0) + 1;
        tagSources[tag] = tagSources[tag] || [];
        tagSources[tag].push(a.agentId);
        seen.add(tag);
      }
    }
  }

  return Object.entries(tagCount)
    .map(([tag, count]) => {
      let weight = 0;
      const rules = [];

      // Rule 1: HTF bias (D/H4/H1) > LTF → +3
      if (/\b(D1?|W1?|H4|4H|HTF|daily|weekly|monthly)\b/i.test(tag)) {
        weight += 3;
        rules.push('HTF bias (D/H4/H1) > LTF: +3');
      }
      // Rule 2: Close-based confirmation > wick-based → +2
      if (/\b(clos(e|ed|ing))\b/i.test(tag)) {
        weight += 2;
        rules.push('Close-based confirmation > wick-based: +2');
      }
      // Rule 3: Confluence count → +2 per extra analyst citing it
      if (count > 1) {
        const bonus = 2 * (count - 1);
        weight += bonus;
        rules.push(`Confluence ×${count} analysts: +${bonus}`);
      }
      // Rule 4: Freshness baseline → +1
      weight += 1;
      rules.push('Freshness baseline: +1');

      return {
        evidence: tag,
        weight,
        sources: tagSources[tag],
        decidingRule: rules.join(' | ')
      };
    })
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 5);
}

/** Count evidence tags shared by 2+ analysts — each counts as one confluence. */
function countConfluentEvidence(analysts) {
  const tagCount = {};
  for (const a of analysts) {
    const seen = new Set();
    for (const tag of a.evidenceTags) {
      if (!seen.has(tag)) {
        tagCount[tag] = (tagCount[tag] || 0) + 1;
        seen.add(tag);
      }
    }
  }
  return Object.values(tagCount).filter(c => c >= 2).length;
}

// ─── Step 5: Quorum helpers ─────────────────────────────────────────────────

/** A noTradeCondition is "fatal" if it matches the current userSettings state. */
function hasFatalNoTradeCondition(analysts, userSettings) {
  for (const a of analysts) {
    for (const cond of a.noTradeConditions) {
      const c = cond.toLowerCase();
      if (userSettings.sessionVolatilityState === 'Abnormal' &&
          /abnormal|extreme.?volat|spike/.test(c)) return true;
      if (userSettings.newsEventImminent &&
          /\bnews\b|\bevent\b|\bannouncement\b|\bfomc\b|\bcpi\b|\bnfp\b/.test(c)) return true;
    }
  }
  return false;
}

// ─── Step 6: Hard gate vetoes ───────────────────────────────────────────────

function computeExpectedRR(analysts, direction) {
  const da = analysts.filter(a => a.direction === direction);
  if (da.length === 0) return null;

  const avg = (arr) => arr.length > 0 ? arr.reduce((s, v) => s + v, 0) / arr.length : null;

  const pois = da.map(a => a.keyLevels.poi).filter(v => v != null);
  const invls = da.map(a => a.keyLevels.invalidation).filter(v => v != null);
  const tp1s  = da.map(a => (a.keyLevels.targets || [])[0]).filter(v => v != null);

  const poi  = avg(pois);
  const inv  = avg(invls);
  const tp1  = avg(tp1s);

  if (poi == null || inv == null || tp1 == null) return null;

  if (direction === 'Long') {
    const risk   = poi - inv;
    const reward = tp1 - poi;
    if (risk <= 0) return null;
    return reward / risk;
  }
  if (direction === 'Short') {
    const risk   = inv - poi;
    const reward = poi - tp1;
    if (risk <= 0) return null;
    return reward / risk;
  }
  return null;
}

/**
 * Run all hard gates in order, short-circuiting on first veto.
 * Returns { ruling: null } if all gates pass.
 *
 * NOTE: Invalidation Gate runs BEFORE R:R Gate because R:R cannot be computed
 * without a known invalidation level — missing invalidation is the root cause.
 */
function runHardGates(analysts, userSettings, direction) {
  const da = analysts.filter(a => a.direction === direction);

  // ── Invalidation Gate (no explicit level) — must run before R:R ──────────
  const hasInvalidation = da.some(a => a.keyLevels.invalidation != null);
  if (!hasInvalidation) {
    return {
      ruling: 'NO_TRADE',
      vetoReason: 'Invalidation Gate: no explicit invalidation level provided by directional analysts'
    };
  }

  // ── R:R Gate ──────────────────────────────────────────────────────────────
  const rr = computeExpectedRR(analysts, direction);
  if (rr === null || rr < userSettings.minRR) {
    return {
      ruling: 'NO_TRADE',
      vetoReason: `R:R Gate: expected R:R (${rr !== null ? rr.toFixed(2) : 'unclear'}) is below minimum (${userSettings.minRR})`
    };
  }

  // ── Volatility Gate ───────────────────────────────────────────────────────
  if (userSettings.sessionVolatilityState === 'Abnormal') {
    return {
      ruling: 'NO_TRADE',
      vetoReason: 'Volatility Gate: session volatility state is Abnormal — no trades'
    };
  }

  // ── Chop Gate ─────────────────────────────────────────────────────────────
  if (userSettings.regime === 'Choppy') {
    const hasEdge = analysts.some(
      a => (a.primaryScenario || '').trim().length > 20
    );
    if (!hasEdge) {
      return {
        ruling: 'NO_TRADE',
        vetoReason: 'Chop Gate: regime is Choppy and no identifiable edge in analyst scenarios'
      };
    }
  }

  // ── News Gate ─────────────────────────────────────────────────────────────
  if (userSettings.newsEventImminent) {
    return {
      ruling: 'CONDITIONAL',
      vetoReason: 'News Gate: high-impact news event imminent — wait until post-event'
    };
  }

  // ── Setup Quality Gate ────────────────────────────────────────────────────
  const setupKeywords = /pullback|breakout|reversal|range|sweep|retest|break|momentum|fvg|orderblock|poi|structure|bos|mss|liquidity/i;
  const hasSetup = analysts.some(a => setupKeywords.test(a.primaryScenario || ''));
  if (!hasSetup) {
    return {
      ruling: 'NO_TRADE',
      vetoReason: 'Setup Quality Gate: no clear setup type identified across analyst scenarios'
    };
  }

  return { ruling: null, vetoReason: null };
}

// ─── Step 7: Confidence score ───────────────────────────────────────────────

function computeConfidenceScore(analysts, userSettings, conflictMode, confluentCount) {
  let score = 50;

  // +10 per independent confluence, max +30
  score += Math.min(confluentCount * 10, 30);

  // -15 if direction disagreement
  if (conflictMode) score -= 15;

  // -10 if regime is uncertain (choppy/ranging)
  if (userSettings.regime === 'Choppy' || userSettings.regime === 'Ranging') {
    score -= 10;
  }

  // -10 if entry relies on anticipation, not confirmation
  const anyAnticipation = analysts.some(a => {
    const text = ([...(a.claims || []), a.primaryScenario || '']).join(' ').toLowerCase();
    const hasAnticipation = /\banticipat|\bahead of\b|\bexpecting\b|\bwait(ing)? for\b/.test(text);
    const hasConfirmation = /\bconfirm(ed|ation)?\b|\bclosed?\b|\bbroken?\b|\breclaim(ed)?\b/.test(text);
    return hasAnticipation && !hasConfirmation;
  });
  if (anyAnticipation) score -= 10;

  return Math.max(0, Math.min(100, score));
}

// ─── Step 8: Order builder ──────────────────────────────────────────────────

function buildOrder(analysts, userSettings, direction, conditionalTrigger) {
  const da = analysts.filter(a => a.direction === direction);

  const avg = (arr) => arr.length > 0 ? arr.reduce((s, v) => s + v, 0) / arr.length : null;

  const pois  = da.map(a => a.keyLevels.poi).filter(v => v != null);
  const invls = da.map(a => a.keyLevels.invalidation).filter(v => v != null);
  const tps   = da.flatMap(a => a.keyLevels.targets || []).filter(v => v != null);

  const avgPoi = avg(pois);
  const avgInv = avg(invls);
  const sortedTPs = [...new Set(tps)].sort(
    (a, b) => direction === 'Long' ? a - b : b - a
  );
  const tp1 = sortedTPs[0] ?? null;
  const tp2 = sortedTPs[1] ?? null;

  const fmt = (n) => n != null ? n.toFixed(5) : 'TBD';

  const tpLogic = tp2
    ? `TP1 at ${fmt(tp1)} (50% exit), TP2 at ${fmt(tp2)} (trail remainder to full exit)`
    : tp1
      ? `Single target at ${fmt(tp1)} — full exit`
      : 'Targets TBD — derived from structure';

  const allNoTrade = [...new Set(analysts.flatMap(a => a.noTradeConditions))];

  const planA = {
    entryModel: `Limit at ${fmt(avgPoi)} POI zone`,
    invalidation: `${fmt(avgInv)} — ${direction === 'Long' ? 'close below' : 'close above'} invalidates setup`,
    takeProfitLogic: tpLogic,
    managementRule: `Move to breakeven at TP1. Partial close 50% at TP1. Trail remainder to TP2. Time stop: exit if no trigger within session.`,
    riskInstruction: `Risk ${userSettings.maxRiskPercent}% of account`,
    doNotTradeIf: allNoTrade
  };

  let planB = null;
  if (conditionalTrigger) {
    planB = {
      trigger: conditionalTrigger,
      entryModel: `Market / trigger entry on: ${conditionalTrigger}`,
      invalidation: `${fmt(avgInv)} — reassess after trigger fires`,
      takeProfitLogic: tpLogic,
      managementRule: `Reduce size 50% vs Plan A. Standard partial and trail rules apply post-entry.`,
      riskInstruction: `Risk ${(userSettings.maxRiskPercent * 0.5).toFixed(2)}% of account (reduced — conditional entry)`,
      doNotTradeIf: [...allNoTrade, 'Trigger does not fire within session window']
    };
  }

  return { planA, planB };
}

// ─── Step 9: Dissent ────────────────────────────────────────────────────────

function buildDissent(analysts, direction) {
  const opposing = direction === 'Long' ? 'Short' : direction === 'Short' ? 'Long' : 'Wait';
  const opposingA = analysts.filter(a => a.direction === opposing);
  const waitA     = analysts.filter(a => a.direction === 'Wait');

  let strongestOpposingCase;
  if (opposingA.length > 0) {
    const best = opposingA.sort((a, b) => b.confidence - a.confidence)[0];
    strongestOpposingCase =
      `Best ${opposing} case (${best.agentId}): ${best.primaryScenario}`;
  } else if (waitA.length > 0) {
    const w = waitA[0];
    strongestOpposingCase =
      `No-trade case (${w.agentId}): ${w.primaryScenario || w.uncertaintyReason || 'Analyst recommends waiting for better conditions'}`;
  } else {
    // Unanimous — synthesise from uncertainty reasons
    const uncertainties = analysts.map(a => a.uncertaintyReason).filter(Boolean);
    strongestOpposingCase =
      `Counter-case from uncertainty: ${uncertainties[0] || 'No explicit counter-case raised — validate before entry'}`;
  }

  // "Fails fast if" — from noTradeConditions + alternative scenarios
  const failSignals = analysts.flatMap(a => a.noTradeConditions).filter(Boolean);
  const failScenarios = analysts
    .map(a => a.alternativeScenario)
    .filter(s => s && /fail|invalid|break|reject|reverse/i.test(s));

  const combined = [...failSignals, ...failScenarios];
  const whatWouldFailFast = combined.length > 0
    ? `This fails fast if: ${combined.slice(0, 2).join('; ')}`
    : `This fails fast if: price breaks through the invalidation level on a closing basis without reclaim`;

  return { strongestOpposingCase, whatWouldFailFast };
}

// ─── Public API ─────────────────────────────────────────────────────────────

/**
 * runSenateArbiter — deterministic deliberation engine.
 *
 * @param {Object[]} analystOutputs  Array of 3 analyst result objects
 * @param {Object}   userSettings    Risk and market context settings
 * @returns {Object}                 Senate decision object
 */
export function runSenateArbiter(analystOutputs, userSettings) {
  const FAIL = (reason) => ({
    ruling: 'PROCEDURAL_FAIL',
    reason,
    confidence: 0,
    senateRecord: null,
    order: null,
    dissent: null,
    vetoReason: null,
    conditionalTrigger: null
  });

  // ── Step 1: Procedural validation ─────────────────────────────────────────
  if (!Array.isArray(analystOutputs) || analystOutputs.length === 0) {
    return FAIL('analystOutputs must be a non-empty array');
  }
  if (!userSettings || typeof userSettings !== 'object') {
    return FAIL('userSettings is required');
  }

  const validation = validateAnalysts(analystOutputs);
  if (!validation.valid) {
    return FAIL(`Missing required fields from ${validation.failedAgentId}: ${validation.missingField}`);
  }

  // ── Step 2: Build Senate Record skeleton ──────────────────────────────────
  const senateRecord = {
    docket: {
      instrument:      userSettings.instrument      || 'Unknown',
      timestamp:       userSettings.timestamp        || new Date().toISOString(),
      regime:          userSettings.regime           || 'Unknown',
      volatilityState: userSettings.sessionVolatilityState || 'Unknown'
    },
    motions: analystOutputs.map(a => ({
      agentId:    a.agentId,
      direction:  a.direction,
      confidence: a.confidence
    })),
    pointsOfAgreement: [],
    contestedPoints:   [],
    evidenceLedger:    [],
    ruling:  null,
    order:   null,
    dissent: null
  };

  // ── Step 3: Disagreement detection ────────────────────────────────────────
  const votes        = getDirectionVotes(analystOutputs);
  const conflictMode = hasDirectionConflict(votes);
  const quorumDir    = getQuorumDirection(votes);
  let conditionalTrigger = null;

  if (conflictMode) {
    conditionalTrigger = resolveConflict(analystOutputs, quorumDir);
    if (!conditionalTrigger) {
      // Unresolvable — early exit
      return {
        ruling: 'NO_TRADE',
        reason: 'Unresolvable direction conflict',
        confidence: 0,
        senateRecord: {
          ...senateRecord,
          contestedPoints: buildContestedPoints(analystOutputs),
          ruling: 'NO_TRADE'
        },
        order:   null,
        dissent: buildDissent(analystOutputs, quorumDir || 'Long'),
        vetoReason:         null,
        conditionalTrigger: null
      };
    }
  }

  // ── Step 4: Evidence weighting ────────────────────────────────────────────
  senateRecord.pointsOfAgreement = buildPointsOfAgreement(analystOutputs);
  senateRecord.contestedPoints   = buildContestedPoints(analystOutputs);
  senateRecord.evidenceLedger    = buildEvidenceLedger(analystOutputs);
  const confluentCount = countConfluentEvidence(analystOutputs);

  // ── Step 5: Quorum check ──────────────────────────────────────────────────
  const directionalVotes = votes.Long + votes.Short;
  const fatalCondition   = hasFatalNoTradeCondition(analystOutputs, userSettings);
  const quorumPassed     = (directionalVotes >= 2) ||
                           (directionalVotes === 1 && !fatalCondition);

  if (!quorumPassed) {
    const confidence = computeConfidenceScore(analystOutputs, userSettings, conflictMode, confluentCount);
    return {
      ruling: 'NO_TRADE',
      reason: 'Quorum not met',
      confidence,
      senateRecord: { ...senateRecord, ruling: 'NO_TRADE' },
      order:   null,
      dissent: buildDissent(analystOutputs, quorumDir || 'Long'),
      vetoReason:         null,
      conditionalTrigger: null
    };
  }

  // Resolve effective direction for gate evaluation
  let effectiveDirection;
  if (quorumDir) {
    effectiveDirection = quorumDir;
  } else if (directionalVotes === 1) {
    effectiveDirection = votes.Long === 1 ? 'Long' : 'Short';
  } else {
    effectiveDirection = votes.Long > votes.Short ? 'Long' : 'Short';
  }

  // ── Step 6: Hard gate vetoes ──────────────────────────────────────────────
  const gateResult = runHardGates(analystOutputs, userSettings, effectiveDirection);
  if (gateResult.ruling !== null) {
    const confidence = computeConfidenceScore(analystOutputs, userSettings, conflictMode, confluentCount);
    const dissent    = buildDissent(analystOutputs, effectiveDirection);

    if (gateResult.ruling === 'CONDITIONAL') {
      const trigger = conditionalTrigger || gateResult.vetoReason;
      return {
        ruling: 'CONDITIONAL',
        confidence,
        senateRecord:       { ...senateRecord, ruling: 'CONDITIONAL' },
        order:              buildOrder(analystOutputs, userSettings, effectiveDirection, trigger),
        dissent,
        vetoReason:         gateResult.vetoReason,
        conditionalTrigger: trigger
      };
    }

    return {
      ruling: 'NO_TRADE',
      confidence,
      senateRecord: { ...senateRecord, ruling: 'NO_TRADE' },
      order:   null,
      dissent,
      vetoReason:         gateResult.vetoReason,
      conditionalTrigger: null
    };
  }

  // ── Step 7: Confidence score ──────────────────────────────────────────────
  const confidence = computeConfidenceScore(
    analystOutputs, userSettings, conflictMode, confluentCount
  );

  // Downgrade to CONDITIONAL if score is below threshold
  let ruling = conflictMode && conditionalTrigger ? 'CONDITIONAL' : 'TRADE';
  if (confidence < 55 && ruling === 'TRADE') ruling = 'CONDITIONAL';

  // ── Step 8: Build order ───────────────────────────────────────────────────
  const order = buildOrder(
    analystOutputs, userSettings, effectiveDirection,
    ruling === 'CONDITIONAL' ? (conditionalTrigger || `Confidence ${confidence} < 55 — wait for additional confirmation`) : null
  );

  // ── Step 9: Dissent (always present) ─────────────────────────────────────
  const dissent = buildDissent(analystOutputs, effectiveDirection);

  senateRecord.ruling = ruling;

  return {
    ruling,
    confidence,
    senateRecord,
    order,
    dissent,
    vetoReason:         null,
    conditionalTrigger: ruling === 'CONDITIONAL' ? (conditionalTrigger || `Confidence ${confidence} < 55`) : null
  };
}
