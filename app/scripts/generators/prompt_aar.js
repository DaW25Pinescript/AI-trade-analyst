import { state } from '../state/model.js';

export function buildAARPrompt() {
  const ticketId = state.ticketID || '—';
  const ptc = state.ptcState;
  const get = id => document.getElementById(id)?.value ?? '';

  const decisionMode  = get('decisionMode') || 'WAIT';
  const entryType     = get('entryType') || '—';
  const entryTrigger  = get('entryTrigger') || '—';
  const stopLogic     = get('stopLogic') || '—';
  const timeInForce   = get('timeInForce') || '—';
  const stopPrice     = get('stopPrice') || '—';
  const stopRationale = get('stopRationale') || '—';
  const tp1Price      = get('tp1Price') || '—';
  const tp1Rationale  = get('tp1Rationale') || '—';
  const tp2Price      = get('tp2Price') || '—';
  const tp2Rationale  = get('tp2Rationale') || '—';
  const entryMin      = get('entryPriceMin') || '—';
  const entryMax      = get('entryPriceMax') || '—';
  const confluence    = document.getElementById('confluenceScore')?.value || '—';
  const asset         = get('asset') || '—';
  const now           = new Date().toISOString().replace('T', ' ').slice(0, 19) + 'Z';

  // G8: AI Edge Score recorded from AI response
  const aiEdgeScore   = get('aiEdgeScore') || '—';

  // G3: read actual AAR values from DOM when available
  const aarOutcome    = get('aarOutcome') || '[WIN / LOSS / BREAKEVEN / MISSED / SCRATCH]';
  const aarVerdict    = get('aarVerdict') || '[PLAN_FOLLOWED / PLAN_VIOLATION / PROCESS_GOOD / PROCESS_POOR]';
  const aarEntry      = get('aarActualEntry') || '[price or N/A]';
  const aarExit       = get('aarActualExit') || '[price or N/A]';
  const aarR          = get('aarRachieved') || '[e.g. +1.5R, -1R, 0R]';
  const aarExitReason = get('aarExitReason') || '[TP_HIT / SL_HIT / TIME_EXIT / MANUAL_EXIT / INVALIDATION / NO_FILL]';
  const aarFirstTouch = state.aarState.firstTouch !== null
    ? (state.aarState.firstTouch === 'true' ? 'YES' : 'NO')
    : '[YES / NO]';
  const aarWouldWin   = state.aarState.wouldHaveWon !== null
    ? (state.aarState.wouldHaveWon === 'true' ? 'YES' : 'NO')
    : '[YES / NO — only if MISSED or NO_FILL]';
  const aarKillSwitch = state.aarState.killSwitch !== null
    ? (state.aarState.killSwitch === 'true' ? 'YES' : 'NO')
    : '[YES / NO]';
  const aarPsych      = get('aarPsychTag') || '[CALM / FOMO / HESITATION / REVENGE / OVERCONFIDENCE / FATIGUE / DISCIPLINED]';
  const aarConf       = document.getElementById('aarConfidence')?.value || '[1–5]';
  const aarNotes      = document.getElementById('aarNotes')?.value || '[brief description of what happened]';

  // Failure codes from multi-select checkboxes
  const failureCodes  = Array.from(
    document.querySelectorAll('#aarFailureCodes .checkbox-item.checked input[data-code]')
  ).map(el => el.dataset.code);
  const aarFailure = failureCodes.length > 0 ? failureCodes.join(' | ') : '[NONE or list codes]';

  return `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 AFTER ACTION REVIEW (AAR) — V3 · G3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID:       ${ticketId}
Asset:           ${asset}
Generated:       ${now}
Pre-AI Score:    ${confluence}/10
AI Edge Score:   ${aiEdgeScore !== '—' ? aiEdgeScore + ' (AI predicted confidence)' : '—'}

─── ORIGINAL TICKET PARAMETERS ───────────
Decision Made:   ${decisionMode}
Entry Type:      ${entryType}
Entry Trigger:   ${entryTrigger}
Entry Zone:      ${entryMin} – ${entryMax}
Stop Price:      ${stopPrice}  (Logic: ${stopLogic} — ${stopRationale})
TP1:             ${tp1Price}  — ${tp1Rationale}
TP2:             ${tp2Price}  — ${tp2Rationale}
Time-in-Force:   ${timeInForce}

─── PRE-TICKET READ ───────────────────────
HTF State:       ${ptc.htfState || '⚠ not set'}
HTF Location:    ${ptc.htfLocation || '⚠ not set'}
LTF Alignment:   ${ptc.ltfAlignment || '⚠ not set'}
Liquidity:       ${ptc.liquidityContext || '⚠ not set'}
Vol Risk:        ${ptc.volRisk || '⚠ not set'}
Exec Quality:    ${ptc.execQuality || '⚠ not set'}
Conviction:      ${ptc.conviction || '⚠ not set'}
Edge Tag:        ${ptc.edgeTag || '⚠ not set'}

─── ACTUAL OUTCOME ────────────────────────
Outcome:         ${aarOutcome}
Verdict:         ${aarVerdict}
Actual Entry:    ${aarEntry}
Actual Exit:     ${aarExit}
R Achieved:      ${aarR}
Exit Reason:     ${aarExitReason}
First Touch:     ${aarFirstTouch}
Would Have Won:  ${aarWouldWin}
Kill Switch:     ${aarKillSwitch}
Failure codes:   ${aarFailure}
Psych tag:       ${aarPsych}
Post-trade conf: ${aarConf}/5
Notes:           ${aarNotes}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM PERSONA (AAR review mode — obey strictly):

You are a ruthless, zero-ego prop trading coach.
Post-mortem analysis only — not comfort.
Separate process quality from outcome quality: a winning trade with a bad process is still a violation.

Please provide:

1. WHAT HAPPENED vs PLAN
   Compare actual execution against the original ticket parameters above.
   Was the entry within the predicted zone (${entryMin}–${entryMax})?
   Were the stop (${stopPrice}) and targets (TP1: ${tp1Price}, TP2: ${tp2Price}) respected?
   What deviated from plan and why?

2. RULE ADHERENCE
   Was the gate decision (exec quality: ${ptc.execQuality || 'not set'}, LTF: ${ptc.ltfAlignment || 'not set'}) respected?
   Did the trader follow kill-switch conditions?
   Flag any process violations — even if the trade was profitable.

3. DECISION QUALITY
   Was pre-AI conviction (${confluence}/10) calibrated correctly given the outcome?
   Was the edge tag (${ptc.edgeTag || 'not set'}) accurate in hindsight?
   Bias check: did the trader's stated bias (${state.currentBias || 'not stated'}) distort the read?

4. PROCESS IMPROVEMENTS
   List exactly 2–3 concrete, actionable improvements for the next session.
   Specific rules, not generic advice. Based only on what went wrong in this trade.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;
}
