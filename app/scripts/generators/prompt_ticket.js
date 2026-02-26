import { state, generateTicketID } from '../state/model.js';
import { getChecked } from '../ui/form_bindings.js';

function buildPrompt() {
  generateTicketID();

  const get = id => (document.getElementById(id) ? document.getElementById(id).value : '') || '';

  const asset       = get('asset') || '[ASSET NOT SET]';
  const session     = get('session') || 'Not specified';
  const execHorizon = get('execHorizon') || 'All ideas';
  const broker      = get('broker') || 'TradingView';
  const candleType  = get('candleType') || 'Normal';
  const chartTZ     = get('chartTimezone') || 'Not specified';
  const priceNow        = get('priceNow') || '—';
  const regime          = get('regime') || 'Not specified';
  const biasHorizon     = get('biasHorizon') || 'Not specified';
  const counterTrend    = get('counterTrendMode') || 'Mixed';
  const noTradeOK   = document.getElementById('noTradeToggle')?.checked ?? false;
  const minRR       = get('minRR') || 'None specified';
  const rrException = get('rrException');
  const rrJust      = get('rrJustification');
  const maxStop     = get('maxStop') || 'Not specified';
  const spread      = get('spread') || 'Not specified';
  const corrNote    = get('correlationNote');
  const corrConf    = get('correlationConf');
  const htfCtx      = get('htfContextSetup') || 'Not specified';
  const cleanliness = get('chartCleanliness') || 'Clean';
  const persona     = get('persona') || 'Default — ruthless prop trader';

  const indicators  = get('indicators') || 'None specified';
  const levels      = get('levels') || 'None — identify from charts';
  const news        = get('news') || 'None known';
  const position    = get('position') || 'None';

  const confluence  = document.getElementById('confluenceScore')?.value || '7';

  // Pre-ticket state
  const ptc = state.ptcState;
  const waitReason    = get('waitReason');
  const reentry       = get('reentryCondition');
  const reentryTime   = get('reentryTime');

  const checked = getChecked();

  const now = new Date().toISOString().replace('T',' ').slice(0,19) + 'Z';

  const tfLines = [
    `  • 4H/1H clean price      — ${state.uploads.htf ? '✓ screenshot attached: ' + state.uploads.htf : '⚠  NO SCREENSHOT'}`,
    `  • 15M clean price        — ${state.uploads.m15 ? '✓ screenshot attached: ' + state.uploads.m15 : '⚠  NO SCREENSHOT'}`,
    `  • 5M clean price         — ${state.uploads.m5 ? '✓ screenshot attached: ' + state.uploads.m5 : '⚠  NO SCREENSHOT'}`,
    `  • 15M ICT overlay        — ${state.uploads.m15overlay ? '✓ screenshot attached: ' + state.uploads.m15overlay : '—  optional / not uploaded'}`,
    `  • 15M structure overlay  — ${state.uploads.m15structure ? '✓ screenshot attached: ' + state.uploads.m15structure : '—  optional / not uploaded'}`,
    `  • 15M trendline overlay  — ${state.uploads.m15trendline ? '✓ screenshot attached: ' + state.uploads.m15trendline : '—  optional / not uploaded'}`,
    `  • Custom overlay         — ${state.uploads.customoverlay ? '✓ screenshot attached: ' + state.uploads.customoverlay : '—  optional / not uploaded'}`,
  ].join('\n');

  const requests = checked.length > 0 ? checked.map(c => `  ☑ ${c}`).join('\n') : '  (none selected)';

  const gateStatus = document.getElementById('gateStatus');
  const gateDecision = gateStatus?.classList.contains('wait') ? 'WAIT (conditions poor — see below)'
    : gateStatus?.classList.contains('caution') ? 'CAUTION (risk flags present)'
    : gateStatus?.classList.contains('proceed') ? 'PROCEED'
    : 'INCOMPLETE — not all checklist fields completed';

  const rrLine = minRR && minRR !== 'None specified'
    ? `Min R:R:         ${minRR}R${rrException === 'yes' ? ` (exception allowed: ${rrJust || 'justification not entered'})` : ' — strict'}`
    : 'Min R:R:         None specified';

  const corrLine = corrNote
    ? `Correlation:     ${corrNote}${corrConf ? ` [confidence: ${corrConf}]` : ''} — secondary confirmation only`
    : 'Correlation:     None noted';

  const waitBlock = (waitReason || reentry)
    ? `\nWAIT Reason:     ${waitReason || '—'}\nRe-entry if:     ${reentry || '—'}\nRe-check at:     ${reentryTime || '—'}`
    : '';

  // G2 Test Mode fields
  const decisionMode   = get('decisionMode') || 'WAIT';
  const ticketType     = get('ticketType') || 'Zone ticket';
  const entryType      = get('entryType') || 'Limit';
  const entryTrigger   = get('entryTrigger') || 'Pullback to zone';
  const confTF         = get('confTF') || '1H';
  const stopLogic      = get('stopLogic') || 'Below swing low / above swing high';
  const timeInForce    = get('timeInForce') || 'This session';
  const maxAttempts    = get('maxAttempts') || '2';
  const askMissing     = document.getElementById('askMissing')?.checked ?? true;
  const conditionalTxt = get('conditionalText');

  // Price level predictions
  const entryPriceMin  = get('entryPriceMin');
  const entryPriceMax  = get('entryPriceMax');
  const stopPrice      = get('stopPrice');
  const stopRationale  = get('stopRationale');
  const tp1Price       = get('tp1Price');
  const tp1Rationale   = get('tp1Rationale');
  const tp2Price       = get('tp2Price');
  const tp2Rationale   = get('tp2Rationale');
  const entryNotes     = get('entryNotes');

  const entryZoneLine = (entryPriceMin || entryPriceMax)
    ? `Entry Zone:      ${entryPriceMin || '—'} – ${entryPriceMax || '—'}${entryNotes ? '\nEntry Notes:     ' + entryNotes : ''}`
    : `Entry Zone:      Not specified${entryNotes ? '\nEntry Notes:     ' + entryNotes : ''}`;
  const stopLine = stopPrice
    ? `Stop Price:      ${stopPrice}${stopRationale ? '  (' + stopRationale + ')' : ''}`
    : `Stop Price:      Not specified`;
  const tp1Line = tp1Price
    ? `TP1:             ${tp1Price}${tp1Rationale ? '  — ' + tp1Rationale : ''}`
    : `TP1:             Not specified`;
  const tp2Line = tp2Price
    ? `TP2:             ${tp2Price}${tp2Rationale ? '  — ' + tp2Rationale : ''}`
    : `TP2:             Not specified`;

  const personaInstruction = persona && persona !== 'Default — ruthless prop trader'
    ? `You operate as a ${persona} analyst. Apply that methodology's framework strictly throughout.`
    : '';

  const prompt = `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 AI TRADE ANALYSIS REQUEST — V3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID:       ${state.ticketID}
Generated:       ${now}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

─── ASSET & SESSION ───────────────────────
Asset:           ${asset}
Session:         ${session}
Market Regime:   ${regime}
Exec Horizon:    ${execHorizon}
Bias Horizon:    ${biasHorizon}${state.currentBias ? '\nMy Bias:         ' + state.currentBias + ' (my current read — do not anchor on this)' : ''}
Counter-Trend:   ${counterTrend}
No-Trade OK?:    ${noTradeOK ? 'YES — you may and should recommend WAIT if conditions are poor' : 'NO — always provide a scenario even if low quality'}

─── PLATFORM ──────────────────────────────
Broker:          ${broker}
Candle Type:     ${candleType}
Chart Timezone:  ${chartTZ}
Price Now:       ${priceNow}
HTF Context:     ${htfCtx}
Chart Cleanliness: ${cleanliness}

─── RISK PARAMETERS ───────────────────────
${rrLine}
Max Stop:        ${maxStop}
Spread/Slippage: ${spread}
${corrLine}

─── CHARTS PROVIDED ───────────────────────
${tfLines}
(All screenshots attached to this message)

─── INDICATORS ON CHART ───────────────────
${indicators}

─── KEY LEVELS I ALREADY SEE ──────────────
${levels}

─── NEWS / EVENTS ─────────────────────────
${news}

─── OPEN POSITIONS ────────────────────────
${position}

─── PRE-TICKET CHECKLIST (user read) ──────
HTF State:           ${ptc.htfState || '⚠ not set'}
HTF Location:        ${ptc.htfLocation || '⚠ not set'}
LTF Alignment:       ${ptc.ltfAlignment || '⚠ not set'}
Liquidity Context:   ${ptc.liquidityContext || '⚠ not set'}
Volatility Risk:     ${ptc.volRisk || '⚠ not set'}
Execution Quality:   ${ptc.execQuality || '⚠ not set'}
My Conviction:       ${ptc.conviction || '⚠ not set'}
My Edge Tag:         ${ptc.edgeTag || '⚠ not set'}
Confluence Score:    ${confluence}/10 (pre-AI gut feel — will be tracked vs outcome)
Gate Decision:       ${gateDecision}${waitBlock}

─── ANALYSIS REQUESTED ────────────────────
${requests}

─── MY PREDICTION (Test / Prediction Mode) ──
Decision Mode:   ${decisionMode}
Ticket Type:     ${ticketType}
Entry Type:      ${entryType}
Entry Trigger:   ${entryTrigger}
Confirm TF:      ${confTF}
Stop Logic:      ${stopLogic}
Time-in-Force:   ${timeInForce}
Max Attempts:    ${maxAttempts}
Ask for gaps:    ${askMissing ? 'YES — request missing info before committing ticket' : 'NO — proceed with available data'}${conditionalTxt ? '\nConditional:     ' + conditionalTxt : ''}
${entryZoneLine}
${stopLine}
${tp1Line}
${tp2Line}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM PERSONA (obey strictly):

You are a ruthless, zero-ego 20-year prop trader and analyst.
You would rather say WAIT than force a low-quality ticket.
Never sugar-coat. Precision over comfort.
${personaInstruction}

SCORING RULES (apply to every output):

R:R: Always calculated after deducting spread and slippage listed above.
  • If R:R < minimum specified, you MUST either (a) reject the trade or (b) explicitly justify the exception.
  • Never inflate R:R by cherry-picking entry; use the realistic zone midpoint.

Confidence scale (mandatory — provide score AND 2–3 explicit reasons):
  5/5 — Maximum conviction. All timeframes aligned, entry zone unambiguous, no conflicting signals.
        Would commit prop capital to this setup today without hesitation.
  4/5 — High conviction. Minor uncertainty in one dimension (e.g. LTF entry timing unclear).
        Valid trade — proceed with standard sizing.
  3/5 — Moderate. Structural case exists but one key element is missing or in conflict.
        Reduce size or wait for a confirmation trigger before entry.
  2/5 — Low conviction. Multiple conditions need to improve. Marginal setup.
        Lean toward WAIT unless a very tight stop is possible.
  1/5 — Very low. Conditions are poor across the board. WAIT is strongly preferred.
        Only trade if user has explicitly overridden no-trade flag.

Counter-trend guidance: ${counterTrend === 'Strict HTF-only' ? 'NO counter-trend ideas. All tickets must align with HTF bias. Reject CT setups.' : counterTrend === 'Mixed' ? 'Counter-trend ideas ONLY if strongly justified by structure (e.g. confirmed reversal, liquidity sweep complete). Flag clearly as CT.' : 'Any direction acceptable — let the chart dictate. No HTF bias restriction.'}

NO_TRADE rule: If no setup meets the minimum standards, WAIT is the correct output. Forcing a ticket when conditions are marginal is a failure of process.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — CHART NARRATIVE (mandatory grounding):

Describe EXACTLY what you see on each chart. No assumptions. No inference yet.
This section is your audit trail — what did the chart actually show at time of analysis?

4H/1H clean: [describe trend, key swing highs/lows, dominant structure, notable levels]
15M clean:   [describe structure and setup quality]
5M clean:    [describe entry context]
Overlays:    [describe each uploaded overlay separately, then compare vs clean-price baseline]

Overall raw bias from charts only (before user bias injected):
→ [Bullish / Bearish / Neutral / Range]

Note any discrepancy between user's stated bias (${state.currentBias || 'none stated'}) and chart read.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — TIMEFRAME ANALYSIS (systematic):

For each timeframe:
1. Trend state: Bullish / Bearish / Range / Transition
2. Market structure: HH/HL or LH/LL, MSS/BOS if present
3. Key demand/supply zones and high-impact levels
4. Risk notes: choppy / extended / late-trend / news-sensitive

Then cross-reference: HTF ↔ Mid ↔ LTF for alignment.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3 — TRADE TICKET [${state.ticketID}]:

Provide ONE primary ticket. A second conditional ticket ONLY if materially different.

Decision:          LONG / SHORT / WAIT / CONDITIONAL
Setup Type:        Pullback / Breakout / Reversal / Range trade / Other
Entry:             [zone, not a single price — specify range]
Entry Trigger:     [Close above/below level | Break + retest | Sweep + reclaim | Pullback to zone | Momentum shift MSS/BOS]
Confirmation TF:   [1m | 5m | 15m | 1H]
Stop:              [exact level]
Stop Logic:        [Below swing low/above swing high | Below zone | ATR-based | Structure + buffer] — state WHY that level
TP1:               [level] — rationale
TP2:               [level] — rationale
R:R (TP1/TP2):    [calculated after spread assumption]
Time Validity:     [this session | 24H | custom — after which the setup is invalid]
Kill-switch:       [what cancels this setup BEFORE entry triggers — be specific]
Confidence:        [1–5] — provide 2–3 explicit reasons
What changes mind: [2 concrete, observable conditions that would invalidate the thesis]
Missing info:      [declare any gaps in available data that limit precision]
WAIT reason:       [enum only if Decision = WAIT]
Re-entry if:       [only if WAIT — what must happen]

Always include what would prove the idea wrong.
Always respect the minimum R:R parameter above.
If Decision = WAIT and no trade is recommended, explain clearly what would change that.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;

  document.getElementById('outputText').textContent = prompt;
  document.getElementById('outputTicketId').textContent = state.ticketID;

  // Attach checklist
  const attachEl = document.getElementById('attachChecklist');
  attachEl.textContent = [
    ['htf', '4H/1H CLEAN'],
    ['m15', '15M CLEAN'],
    ['m5', '5M CLEAN'],
    ['m15overlay', '15M ICT OVERLAY'],
    ['m15structure', '15M STRUCTURE OVERLAY'],
    ['m15trendline', '15M TRENDLINE OVERLAY'],
    ['customoverlay', 'CUSTOM OVERLAY'],
  ].map(([key, label]) => {
    const name = state.uploads[key];
    return `${name ? '✓' : '○'}  ${label.padEnd(22)} — ${name || '(not uploaded)'}`;
  }).join('\n');
}

export { buildPrompt };
