export function buildWeeklyPrompt() {
  const now    = new Date().toISOString().replace('T', ' ').slice(0, 10);
  const asset  = document.getElementById('asset')?.value || 'Portfolio';

  return `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 WEEKLY REVIEW PROMPT — V3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Week ending:     ${now}
Focus asset:     ${asset || 'All assets'}

─── HOW TO USE ────────────────────────────
1. Export each closed ticket from this session using "Save JSON Backup".
2. Fill in the TRADE LOG rows below with data from those exports.
3. Paste this entire block into Claude for AI-assisted weekly review.

─── TRADE LOG ─────────────────────────────
One row per closed ticket. Use data from your JSON backup exports.

Format:
  TicketID | Asset | Decision | Outcome | R | ConfPre(1-10) | ConfPost(1-5) | EdgeTag | GateStatus | Notes

Example:
  XAUUSD_260224_0930 | XAUUSD | LONG | WIN | +1.5R | 8 | 4 | Liquidity grab | PROCEED | Clean entry, TP1 hit
  XAUUSD_260224_1430 | XAUUSD | SHORT | LOSS | -1R | 5 | 2 | Pullback | CAUTION | Entered early, SL taken
  EURUSD_260225_1000 | EURUSD | WAIT | MISSED | 0R | 6 | 3 | FVG reclaim | WAIT | Gate fired, skipped — setup triggered without me

[PASTE YOUR TRADE ROWS HERE]

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
