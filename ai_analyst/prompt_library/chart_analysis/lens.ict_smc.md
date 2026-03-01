# ICT/SMC Lens

**name:** chart-analysis-lens-ict-smc  
**description:** Liquidity, PD Arrays, displacement, sessions.

## Liquidity Concepts
- **BSL**: above EQH, old highs, bearish trendlines.  
- **SSL**: below EQL, old lows, bullish trendlines.  
- **Sweep / Purge**: wick through liquidity pool without body close → often precedes CHoCH.

## PD Arrays
- **FVG**: 3-candle imbalance. Only call if **visually clear** gap between bodies/wicks. State fresh / partially mitigated / invalidated.  
- **Order Block**: last opposing candle before impulsive displacement + BOS that leaves FVG.  
- **Breaker Block**: failed OB that price closed through with momentum.

## Session Logic (NY time, DST-aware)
- Asian Range → London Killzone (Judas Swing) → NY Killzone (distribution).

## Analysis Steps
1. Map obvious BSL/SSL pools and recent sweeps.  
2. Identify fresh PD arrays with confluence (liquidity sweep + FVG + OB).  
3. Note displacement strength.
