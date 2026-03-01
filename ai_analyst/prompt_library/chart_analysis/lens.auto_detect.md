# Auto Lens Detection — Heuristics (Non-Binding)

**name:** chart-analysis-lens-detect  
**description:** Suggests likely lenses to activate based on visible elements in a TradingView screenshot. These are heuristics only. User request always overrides. Arbiter remains authoritative.

## Core Principle
- Detection produces **Suggested Lenses** + **Evidence**.
- Detection must **never** assert bias, trend, or setup quality.
- Detection must **never** force a lens if user explicitly disables it.
- If uncertain, suggest fewer lenses and lower confidence.

## Output Template (Detector Output Only — Not Shown to User)
Suggested Lenses:
- Market Structure: ON (default)
- Trendlines: ON/OFF (Confidence: High/Med/Low) — Evidence: …
- ICT/SMC: ON/OFF (Confidence: High/Med/Low) — Evidence: …
- ICC/CCT: ON/OFF (Confidence: High/Med/Low) — Evidence: …

Detector Notes:
- Any ambiguity, screenshot limitations, or reasons to avoid auto-enabling.

## Detection Signals (Heuristics)

### Always-On Default
- **Market Structure lens** is ON by default unless user explicitly disables it.

### Trendlines Lens — Enable When
High confidence signals:
- Visible diagonal lines connecting swing highs/lows.
- Multiple trendlines / channels manually drawn (parallel lines).
- Price reacting repeatedly at a diagonal boundary.

Medium confidence signals:
- Clearly visible “connect-the-dots” swing geometry even if lines are not drawn.

Disable / low confidence:
- No clear diagonals, or chart clutter prevents seeing anchor points.

### ICT/SMC Lens — Enable When
High confidence signals:
- Rectangular zones labeled or resembling FVG / imbalance boxes.
- OB boxes/zones, supply/demand rectangles, “breaker” labels.
- Clear equal highs/lows markings, liquidity pool labels, raid/sweep annotations.
- Session boxes (Asia/London/NY), killzone shading, or time-window highlights.

Medium confidence signals:
- Clear displacement candles + gaps suggestive of FVGs (only if visually obvious).
- Multiple horizontal S/R-like zones that appear to be PD arrays.

Disable / low confidence:
- Candles too small to verify 3-candle FVG definition.
- No PD array markings and no clear liquidity annotations.

### ICC/CCT Lens — Enable When
High confidence signals:
- Parallel rails / correction channels drawn.
- Notations suggesting “reclaim”, “acceptance”, “rails”, “correction leg”.
- Visual pattern of impulse → channelled pullback → continuation attempt (only if clear).

Medium confidence signals:
- Clean ABC-style correction legs with symmetry, even without rails drawn.

Disable / low confidence:
- Choppy range with no clean legs.
- No clear channel/rails and no reclaim/acceptance features.

## User Overrides (Hard Rule)
- If user says: “analyze with ICT + trendlines” → enable those regardless of detection.
- If user says: “no ICT lens” → do NOT enable ICT lens even if detected.

## Safety / Conservatism
- Prefer false negatives over false positives.
- If image quality is low, suggest fewer lenses with Low confidence.
