# Arbiter → PineKraft Bridge

**name:** chart-analysis-bridge-pinekraft  
**description:** Converts Arbiter synthesis into a script-ready spec for PineKraft (indicator/strategy suggestion). This does not write Pine code directly; it produces a clean, minimal “Script Spec” that PineKraft can implement.

## When to Run
- Only run after Arbiter synthesis is complete.
- Only include this section if:
  - User asked for PineScript / indicator / automation, OR
  - System is configured to always suggest tooling.

## Core Principle
- PineKraft receives **only arbiter-level conclusions**, never raw lens outputs.
- If Arbiter confidence is Low OR No-Trade gate triggered:
  - Default to “Do Not Script Yet” or “Script Only Observability Tools” (e.g., marking detected zones) rather than trade entries.

## Script Spec Output (Embedded inside Arbiter final block, under a dedicated heading)
### PineKraft Script Spec (Optional)
**Intent:** (observability / alerting / backtest strategy / dashboard)  
**Active Method:** (Market Structure / ICT / Trendlines / ICC-CCT)  
**Key Objects to Draw:**  
- e.g., Swing points, BOS/MSS markers, FVG boxes, OB zones, rails/channel lines, liquidity levels

**Definitions to Encode (strict):**
- BOS rule: body close beyond swing in trend direction
- MSS/CHoCH rule: body close + displacement beyond opposing swing
- FVG rule: 3-candle, wick-to-wick gap (A/C), status = fresh/partial/invalidated
- OB rule: last opposing candle before displacement + BOS
- Rails rule: parallel channel during correction
(Include only definitions relevant to active lenses.)

**Inputs (Minimal):**
- Pivot sensitivity (left/right)
- Lookback window
- FVG strictness toggle (wick-to-wick only)
- OB strictness toggle (requires BOS + displacement)
- Session overlay toggle (NY time)
- Alerts: BOS/MSS/FVG tap/OB tap/rail break

**Non-Repaint Constraints:**
- Confirm pivots only after rightBars
- No lookahead in HTF calls
- Avoid per-bar object spam; use persistent handles

**Alert Conditions (Optional):**
- BOS confirmed
- MSS confirmed
- Price enters fresh FVG zone
- Price taps OB zone (first mitigation)
- Rail reclaim/acceptance signal

**Do-Not-Script Conditions:**
- If contested points remain unresolved AND confidence <= Medium:
  - produce observability-only script, no strategy entries

## Mapping Table (Arbiter → Script)
- High-probability zone → box/line objects with labels
- Invalidation level → horizontal line + alert
- Contested points → optional debug table (on-chart)

## Output Discipline
- Keep Script Spec under ~25 lines.
- No Pine code in this section.
- PineKraft implementation is triggered separately using PineKraft SKILL.md.
