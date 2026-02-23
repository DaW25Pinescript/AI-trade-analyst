## AI Trade Analyst — V3 Master Plan (Final Refined)

---

### SECTION A — Form Inputs

**A1. Setup & Session**

- Auto-timestamp (date/time + timezone, auto-populated on form load)
- Auto-generate Ticket ID: `XAUUSD_YYYYMMDD_HHMM`
- Broker/Platform dropdown: TradingView / MT5 / cTrader / Other
- Candle type: Normal / Heikin Ashi / Renko (affects how AI interprets screenshots)
- HTF context field: At POI / Mid-range / At extremes / Extended
- "Price now" field (optional, user-overridable — helps when screenshots obscure current price)
- Chart timezone field (broker time vs NY time — critical for scoring accuracy)
- Screenshot cleanliness: 3-state toggle — Clean / Light drawings / Heavy drawings (AI prompt adapts: "use drawings" vs "ignore drawings")
- Correlation context: optional note + confidence (Low / Med / High) — injected as secondary confirmation only, never primary justification
- Preferred minimum R:R + exception policy toggle (Strict / Allow exception with one-sentence justification)
- Max stop distance ($ or pips)
- Spread/slippage assumption (small but essential for accurate scoring)
- Session time-in-force: NY AM only / This session / 24H / Custom

**A2. Pre-Ticket Checklist (mandatory gate — radio button groups, enum-enforced)**

All six must be completed before ticket section is shown. Forced clean data for metrics.

- HTF State: Trending / Ranging / Transition
- HTF Location: At POI / Mid-range / At extremes
- LTF Alignment: Aligned / Counter-trend / Mixed
- Liquidity Context: Near highs or lows / Equilibrium / None identified
- Volatility/News risk: Normal / Elevated
- Execution Quality: Clean / Messy / Chop

Logic gate: if Execution quality = Messy/Chop AND No-trade OK = YES → default WAIT unless specific conditional trigger exists.

**New — A2 additions:**
- 7th mandatory field: "My personal edge on this setup" (dropdown, user-definable over time): High-probability pullback / Liquidity grab / FVG reclaim / Structure BOS / Range boundary / Other. Tracks *your own* setup performance vs AI's — separates trader edge from AI edge.
- Confluence score slider 1–10 (user's gut-feel before AI response). Later correlates with actual outcomes → personal calibration score. Reveals whether your pre-trade conviction predicts results.
- "Time horizon for re-evaluation" if WAIT (e.g. re-check in 2H) — enables re-entry condition tracking

**A3. Test / Prediction Mode Card**

- Decision mode: Long / Short / Wait / Conditional
- If WAIT:
  - Wait reason code (enum): Chop/range noise / HTF-LTF conflict / No POI or poor R:R / News risk or volatility / Already moved or late trend
  - Re-entry condition (text): "Switch from WAIT to LONG/SHORT if…" — makes WAIT testable
  - Time horizon for re-evaluation (e.g. 2H)
- Ticket type: Zone ticket (default) / Exact ticket
- Entry type: Market / Limit / Stop
- Entry trigger type (enum): Close above/below level / Break + retest / Sweep + reclaim / Pullback to zone / Momentum shift (MSS/BOS)
- Confirmation timeframe (enum): 1m / 5m / 15m / 1H
- Stop logic (enum): Below swing low or above swing high / Below zone / ATR-based / Structure-based + buffer
- Time-in-force: Next 1H / This session / 24H / Custom
- Max entry attempts: 1 / 2
- Auto-invalidate toggle: if not triggered by X time → scratch
- "Ask for missing info before giving a trade" toggle

**A4. Journal / Risk Card**

- "Generate Journal Record" toggle
- Risk stored as R (primary)
- Optional: Fixed $ risk + account size (sizing output only shown if enabled)
- Expected R pre-trade
- Persona override field (optional): ICT purist / SMC + Volume Profile / Pure price action / Other — lets advanced users switch analyst style

---

### SECTION B — Generated Prompt

**B1. Pre-Ticket Checklist Block (always injected)**

```
PRE-TICKET READ:
HTF State:           [Trending / Ranging / Transition]
HTF Location:        [At POI / Mid-range / At extremes]
LTF Alignment:       [Aligned / Counter-trend / Mixed]
Liquidity Context:   [Near highs/lows / EQ / None]
Volatility Risk:     [Normal / Elevated]
Exec Quality:        [Clean / Messy / Chop]
Personal Edge Tag:   [user's enum]
Confluence Score:    [1–10 user pre-score]
→ Proceed to ticket / Default WAIT (state reason)
```

**B2. Chart Narrative Block (new — mandatory grounding mechanism)**

```
CHART NARRATIVE (describe exactly what you see — no assumptions):
HTF:  [what is visible — trend, key levels, structure]
Mid:  [what is visible]
LTF:  [what is visible]
Exec: [what is visible]
```

This forces the AI to prove it actually read the images before committing to a ticket. Acts as an audit trail for AAR — you can compare what the AI claimed to see vs what actually played out.

**B3. Structured Trade Ticket Block (enum-enforced)**

```
TRADE TICKET [ID]:
Decision:            LONG / SHORT / WAIT / CONDITIONAL
Setup Type:          Pullback / Breakout / Reversal / Range / Other
Entry:               [zone or exact]
Entry Trigger:       [enum]
Confirmation TF:     [1m / 5m / 15m / 1H]
Stop:                [level]
Stop Logic:          [enum] — reason why that level
TP1:                 [level] — rationale
TP2:                 [level] — rationale
R:R (TP1 / TP2):    [calculated]
Time Validity:       [session or time-bound]
Kill-switch:         [what cancels before entry triggers]
Confidence:          [1–5] — max 3 bullet reasons
What changes mind:   [2 concrete observable conditions]
Missing info:        [if ask-first toggle ON]
WAIT reason:         [enum — only if WAIT]
Re-entry condition:  [only if WAIT]
```

One primary ticket. One conditional alternative only if materially different. No ticket spam.

**B4. System Prompt Persona (injected at top of every prompt)**

> "You are a ruthless, zero-ego 20-year prop trader. You would rather say WAIT than force a low-quality ticket. Never sugar-coat. Precision over comfort. If the chart narrative doesn't justify the ticket, say so explicitly."

Persona adapts if persona override is set in A4.

**B5. Prompt Meta-Injections (auto)**
- Timestamp + Ticket ID in header
- R:R minimum + exception policy
- Correlation context as secondary confirmation note only
- HTF context + "Price now" if provided
- Chart timezone
- Spread/slippage assumption
- Candle type + broker platform (so AI adapts interpretation)
- Screenshot cleanliness state (adapt instruction: use/ignore drawings)

---

### SECTION C — After-Action Review Module

*The feature that makes the system compound. Every completed AAR makes the next analysis smarter.*

**C1. AAR Input Form**
- Load by Ticket ID (manual or select from saved)
- Outcome (enum): Win / Loss / Scratch / Did Not Trigger / Still Open
- First touch: did price reach entry zone? Yes / No
- Would-have-won: if entry not taken, did TP hit before SL would have? Yes / No (scores WAIT accuracy)
- Actual entry price
- Actual exit price
- R achieved (numeric)
- Exit reason (enum): TP1 hit / TP2 hit / SL hit / Manual exit / Time invalidation / Did not trigger / Kill-switch triggered
- Kill-switch triggered? Yes / No
- Failure reason codes (enum, multi-select): Early entry / Late entry / SL too tight / Target too ambitious / Ignored kill-switch / HTF level misread / News spike / Chop regime misclassified / Re-entry condition triggered but missed
- Psychological note (enum — new): Executed cleanly / Hesitated / Revenge trade / FOMO entry / Sized incorrectly / Overrode the plan. Surfaces behavioural patterns in metrics over time.
- AI vs Trader checklist comparison (new — auto-generated): highlights where trader's pre-ticket checklist differed from AI's output. Pure learning signal.
- Actual trade screenshot upload (optional — entry/exit marked, stored as base64)
- Free text notes

**C2. AAR — AI Review Prompt (generated)**

Structured second prompt sent to Claude containing:
- Full original ticket + pre-ticket checklist
- Chart narrative (what AI said it saw)
- All AAR fields
- Ask Claude to assess:
  - Was the chart narrative accurate? Where did the read break down?
  - Was HTF/LTF structural read correct?
  - Was confidence rating appropriate in hindsight? Revised score 1–5?
  - Better entry/SL/TP given what charts actually showed?
  - Was stop logic enum appropriate or was a different type more suitable?
  - Pattern flag: is this a recurring failure type? Cross-reference reason codes.
  - Behavioural flag: did the psychological tag indicate a pattern worth noting?
  - What to look for differently next time? (concrete, not generic)

**New — "Revised Ticket" button:** after AAR submission, one-click pre-fills a new ticket with AI's hindsight suggestions. Builds a "what I should have done" record alongside the actual trade record.

**C3. Journal Metrics (computed from all stored tickets + AARs)**

Per-ticket:
- R achieved vs R expected
- Confluence score vs outcome correlation
- Structured verdict (enum): Analysis correct / Analysis wrong / Setup valid but execution off / External event invalidated / WAIT correct / WAIT incorrect

Running metrics:
- Win rate overall + by setup type + by session
- Average R per trade
- Expectancy: (win rate × avg win) − (loss rate × avg loss)
- WAIT accuracy rate
- Most common failure reason code
- Most common psychological tag
- Confluence calibration: does score 8–10 outperform 1–3?
- Confidence calibration: does 4–5 actually outperform 1–2?
- Personal edge tag performance: which setups are actually working for you?
- Days since last similar setup (spot clustering)
- Edge Score per ticket (0–100): R:R × Confidence × Confluence × historical setup win rate

**New — Weekly Review Prompt (one button):** feeds last 7 days of tickets + AARs into Claude for a structured performance debrief. Identifies patterns, behavioural flags, and setup recommendations for the coming week.

**New — Recurring Pattern Detector:** after 20+ tickets, surface insights like "68% win rate on 4H pullbacks to HTF POI after NY open" automatically from the stored data.

---

### SECTION D — Data Model

Define now. Prevents rewrites. CSV + export become trivial.

**Ticket object:**
```json
{
  "id": "XAUUSD_20260223_1524",
  "timestamp": "",
  "timezone": "",
  "chartTimezone": "",
  "asset": "",
  "broker": "",
  "candleType": "",
  "session": "",
  "regime": "",
  "horizons": {},
  "noTradeOK": true,
  "priceNow": "",
  "screenshotsEmbedded": [],
  "screenshotCleanliness": "",
  "preTicketChecklist": {},
  "userEdgeTag": "",
  "confluenceScore": 0,
  "ticketFields": {},
  "rMin": 0,
  "rMinException": "",
  "maxStop": 0,
  "spreadAssumption": 0,
  "correlationNote": "",
  "correlationConfidence": "",
  "htfContext": "",
  "persona": "",
  "prompt": "",
  "chartNarrative": ""
}
```

**AAR object:**
```json
{
  "ticketId": "",
  "outcomeEnum": "",
  "firstTouch": false,
  "wouldHaveWon": false,
  "actualEntry": 0,
  "actualExit": 0,
  "rAchieved": 0,
  "exitReasonEnum": "",
  "killSwitchTriggered": false,
  "failureReasonCodes": [],
  "psychologicalTag": "",
  "verdictEnum": "",
  "revisedConfidence": 0,
  "checklistDelta": {},
  "tradeScreenshot": "",
  "revisedTicket": {},
  "notes": "",
  "aarPrompt": ""
}
```

---

### SECTION E — Export & Persistence

**E1. Persistence**
- localStorage for V3 (fast to ship, good enough for <50 tickets)
- Auto-export JSON backup button (critical safety net)
- Migrate to IndexedDB at V3.1+ when ticket volume grows (localStorage caps at 5–10MB)
- "Import Journal" (restore from JSON backup)

**E2. Exports**
- V3: window.print() + self-contained HTML (stable, ships fast)
- PDF/HTML: includes Ticket ID, timestamp, pre-ticket checklist, chart narrative, full ticket, R:R
- AAR export: links to original ticket by ID, includes verdict + reason codes + revised ticket
- CSV export: one row per ticket + one row per AAR (enables Excel/Sheets analysis)
- Full Journal JSON export/import (backup + restore)
- V3.1+: html2canvas + jsPDF once schema fully stabilizes

**E3. Clipboard**
- "Copy full brief": prompt + all metadata as structured markdown
- Compatible with Notion / Obsidian

---

### SECTION F — UX / Flow

**F1. Form Gates**
- Pre-ticket checklist must be fully completed before ticket section renders
- Soft gate Step 2: prominent warning if zero screenshots before advancing
- Asset field required before prompt generation
- WAIT decision visually distinct (amber treatment, not buried)

**F2. Navigation**
- 5 steps: Setup / Charts / Context / Test Mode / Output
- 6th mode: AAR (accessible from header, not a step — it's a separate workflow)
- Step indicator shows done state clearly
- Clone Ticket button (great for same asset, similar setup next session)

**F3. Mini Dashboard (header dropdown)**

Once journal has entries, show:
- Current expectancy
- Win rate last 20 trades
- Confidence calibration bar (simple)
- Top 3 failure reason codes
- Confluence score calibration

**F4. Keyboard Shortcuts**
- Ctrl/Cmd+K: search tickets
- Ctrl+Enter: generate prompt
- Ctrl+J: open journal/AAR mode

**F5. Dark Theme PDF Fix**
- Fix @media print CSS to preserve dark theme variables
- Use color-scheme: dark + explicit variable overrides

---

### SECTION G — Build Order

| Phase | What | Why |
|---|---|---|
| G1 | B1 + B2 + B3 + B4 — full prompt engine with enums, narrative, persona | Highest immediate value, no new UI required |
| G2 | A2 + A3 — pre-ticket checklist (radio enums) + Test Mode card | Small UI, massive prompt and scoring impact |
| G3 | Section D data model + localStorage save on ticket generate | Must be stable before storing anything |
| G4 | A1 remaining fields + A4 Journal card | Completes intake form |
| G5 | C1 — AAR input form | V3 signature feature begins |
| G6 | C2 — AAR prompt generator + Revised Ticket button | Closes the learning loop |
| G7 | C3 — metrics engine + weekly review prompt + pattern detector | Turns journal into edge-tracking system |
| G8 | E1 — JSON export/import backup | Safety net before volume builds |
| G9 | E2 — CSV export + AAR-linked PDF/HTML | External audit capability |
| G10 | F — UX gates, dashboard, clone ticket, keyboard shortcuts | Polish |
| G11 | E1 upgrade — IndexedDB migration | When volume demands it |
| G12 | E2 upgrade — html2canvas + jsPDF | After schema fully stable |

---

### SECTION H — V3.1 / V4 Horizon

- Edge Score (0–100) per ticket: R:R × Confidence × Confluence × historical setup win rate
- Recurring Pattern Detector: after 20+ tickets surface statistical edges automatically
- Weekly Review Prompt: one button, full 7-day debrief via Claude
- Broker API integration (read-only): auto-populate actual entry/exit into AAR
- Multi-asset performance comparison dashboard
- "Shadow mode": run AI analysis without taking the trade, score it anyway — builds data without capital risk

---

The single non-negotiable principle across every section: **enums and deterministic scoring rules everywhere possible.** That is what separates a prompt generator from a genuine edge-measurement and compounding system.

Ready to build. Suggest starting at G1.