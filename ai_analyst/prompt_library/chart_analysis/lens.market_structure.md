# Market Structure Lens

**name:** chart-analysis-lens-market-structure  
**description:** Strict HH/HL/LH/LL + BOS/MSS/CHoCH definitions with pivot rules.

## Strict Definitions
- **Swing High/Low**: Confirmed fractal pivot (default left/right bars = 5/5 on 15m+, adjust for TF). Anchor at bar_index of the confirmed pivot.  
- **Bullish Structure**: Series of Higher Highs + Higher Lows.  
- **Bearish Structure**: Lower Highs + Lower Lows.  
- **BOS (Break of Structure)**: Candle **body close** beyond the most recent swing point **in the direction of the prevailing trend**. Confirms continuation.  
- **MSS / CHoCH (Market Structure Shift / Change of Character)**: Candle **body close + clear displacement** (range-expansion candle) beyond the most recent opposing swing point. Signals potential reversal.

## Analysis Steps
1. State current trend state machine (e.g., “HTF Bullish, last MSS on 1H”).  
2. Locate most recent BOS and last MSS/CHoCH.  
3. Classify current leg (impulse vs retracement).  
4. Note internal structure breaks if visible.
