const CLOSED_OUTCOMES = new Set(['WIN', 'LOSS', 'BREAKEVEN', 'SCRATCH']);

function _fmtR(r) {
  const n = Number(r);
  if (!Number.isFinite(n)) return '—';
  return n >= 0 ? `+${n.toFixed(2)}` : n.toFixed(2);
}

function _buildTradeRows(entries) {
  if (!entries.length) return '[No trade data loaded — paste trade rows manually]';
  return entries.map(({ ticket, aar }) => {
    const id        = ticket?.ticketId || '—';
    const asset     = (ticket?.ticketId || '').split('_')[0] || '—';
    const decision  = ticket?.decisionMode || '—';
    const outcome   = aar?.outcomeEnum || '—';
    const r         = _fmtR(aar?.rAchieved);
    const confPre   = ticket?.checklist?.confluenceScore ?? '—';
    const confPost  = aar?.revisedConfidence ?? '—';
    const edgeTag   = ticket?.checklist?.edgeTag || '—';
    const gate      = ticket?.gate?.status || '—';
    const notes     = (aar?.notes || '').replace(/\n/g, ' ').slice(0, 60) || '—';
    return `  ${id} | ${asset} | ${decision} | ${outcome} | ${r}R | ${confPre} | ${confPost} | ${edgeTag} | ${gate} | ${notes}`;
  }).join('\n');
}

function _buildQuickStats(entries) {
  const closed  = entries.filter(({ aar }) => CLOSED_OUTCOMES.has(aar?.outcomeEnum));
  if (!closed.length) return '';
  const closedR = closed.map(({ aar }) => Number(aar?.rAchieved ?? 0));
  const wins    = closed.filter(({ aar }) => Number(aar?.rAchieved ?? 0) > 0);
  const winRate = (wins.length / closed.length * 100).toFixed(1);
  const avgR    = (closedR.reduce((a, b) => a + b, 0) / closedR.length).toFixed(2);
  const netR    = closedR.reduce((a, b) => a + b, 0).toFixed(2);
  const sign    = (n) => Number(n) >= 0 ? `+${n}` : `${n}`;
  return `Closed: ${closed.length} | Win rate: ${winRate}% | Avg R: ${sign(avgR)} | Net R: ${sign(netR)}`;
}

/**
 * G8: Build the weekly review prompt.
 * @param {Array<{ticket: object, aar: object}>} entries - loaded journal entries (from dashboard)
 */
export function buildWeeklyPrompt(entries = []) {
  const now     = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const nowStr  = now.toISOString().replace('T', ' ').slice(0, 10);
  const asset   = document.getElementById('asset')?.value || 'Portfolio';

  // Filter to last 7 days; entries without a date are included
  const weekEntries = entries.filter(({ ticket }) => {
    const d = ticket?.createdAt ? new Date(ticket.createdAt) : null;
    return !d || d >= weekAgo;
  });

  const tradeRows  = _buildTradeRows(weekEntries);
  const quickStats = _buildQuickStats(weekEntries);
  const countLine  = weekEntries.length > 0
    ? `Trades loaded:   ${weekEntries.length} (last 7 days)`
    : 'Trades loaded:   0 — paste rows manually below';

  const statsBlock = quickStats
    ? `─── PRE-COMPUTED STATS ────────────────────\n${quickStats}\n\n`
    : '';

  return `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 WEEKLY REVIEW PROMPT — V3 · G8
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Week ending:     ${nowStr}
Focus asset:     ${asset || 'All assets'}
${countLine}

${statsBlock}─── TRADE LOG ─────────────────────────────
Format: TicketID | Asset | Decision | Outcome | R | ConfPre(1-10) | ConfPost(1-5) | EdgeTag | GateStatus | Notes

${tradeRows}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM PERSONA (weekly review mode — obey strictly):

You are a ruthless prop trading performance coach reviewing a full week of trades.
Analysis must be data-driven — patterns and numbers, not anecdote.
Separate process quality from outcome quality throughout.

Please provide:

1. WEEKLY PERFORMANCE SUMMARY
   Total trades | Wins | Losses | Breakeven | Missed/No-fill
   Win rate (closed trades only) | Average R won | Average R lost | Net R for week
   Expectancy = (winRate × avgWin) − (lossRate × avgLoss)
   Best trade and why | Worst trade and why

2. PATTERN BREAKDOWN
   Which edge tags produced the best win rate this week?
   Which decision modes (LONG/SHORT/WAIT/CONDITIONAL) were most accurate?
   Were WAIT decisions correct in hindsight (would they have triggered/won)?
   Any recurring setup types that failed — identify the structural reason.

3. CALIBRATION CHECK
   Compare pre-AI confluence scores (1–10) vs actual outcomes.
   Is conviction well-calibrated? (high score → higher win rate?)
   Compare post-trade confidence (1–5) vs pre-AI score — flag any large gaps.
   Flag overconfidence: high pre-AI score, loss outcome.
   Flag missed conviction: low pre-AI score, strong winner.

4. PROCESS ADHERENCE
   Were any gate-override trades taken (CAUTION or WAIT gate → entered anyway)?
   Were kill-switch conditions respected on losing trades?
   Flag all process violations — regardless of outcome.
   Count and grade: PLAN_FOLLOWED vs PLAN_VIOLATION vs PROCESS_GOOD vs PROCESS_POOR.

5. NEXT WEEK ADJUSTMENTS
   Based only on observed patterns above — list exactly 3 concrete rule adjustments.
   Each rule must be:
     - Specific (not "be more patient" — give an exact trigger or condition)
     - Measurable (observable in real-time)
     - Time-boxed (applies next week, to be reviewed again after)
   Example format: "No LONG entries in [asset] during [session] until LTF alignment is Aligned — not Mixed."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;
}
