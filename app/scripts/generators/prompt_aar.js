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

  return `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 AFTER ACTION REVIEW (AAR) — V3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID:       ${ticketId}
Asset:           ${asset}
Generated:       ${now}
Pre-AI Score:    ${confluence}/10

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTUAL OUTCOME — fill in before pasting
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Outcome:         [WIN / LOSS / BREAKEVEN / MISSED / SCRATCH]
Verdict:         [PLAN_FOLLOWED / PLAN_VIOLATION / PROCESS_GOOD / PROCESS_POOR]
Actual Entry:    [price or N/A]
Actual Exit:     [price or N/A]
R Achieved:      [e.g. +1.5R, -1R, 0R]
Exit Reason:     [TP_HIT / SL_HIT / TIME_EXIT / MANUAL_EXIT / INVALIDATION / NO_FILL]
First Touch:     [YES / NO — did price touch entry zone on first approach?]
Would Have Won:  [YES / NO — only if MISSED or NO_FILL]
Kill Switch:     [YES / NO — was the kill-switch condition triggered before entry?]
Failure codes:   [LATE_ENTRY | OVERSIZED_RISK | IGNORED_GATE | MISREAD_STRUCTURE | NEWS_BLINDSPOT | EMOTIONAL_EXECUTION | NO_EDGE — all that apply, or NONE]
Psych tag:       [CALM / FOMO / HESITATION / REVENGE / OVERCONFIDENCE / FATIGUE / DISCIPLINED]
Post-trade conf: [1–5 — how confident are you NOW that this was the right process?]
Notes:           [brief description of what happened]

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
