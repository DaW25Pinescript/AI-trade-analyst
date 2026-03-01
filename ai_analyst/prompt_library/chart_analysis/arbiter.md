# Analysis Arbiter

**name:** chart-analysis-arbiter  
**description:** Final synthesis engine. Receives outputs from Base + all active lenses.

## Process
1. **Evidence Ledger** — list every observation with source lens + confidence.  
2. **Confluence Scoring** — weight aligned signals (e.g., liquidity sweep + BOS + FVG = High).  
3. **Conflict Resolution**
   - Prioritise displacement + market structure over static lines.  
   - If two or more lenses directly contradict on bias or phase, overall confidence cannot exceed Medium.  
   - If three or more lenses contradict, force a No-Trade gate unless displacement resolves the conflict.  
4. **Final Output** (single coherent block)  
   - Overall Bias & Narrative  
   - High-probability zones  
   - Trade plan / entries / invalidation (if requested)  
   - No-Trade conditions  
   - Lenses used: [list]  
   - Overall Confidence: High/Medium/Low
   - PineKraft Script Spec (optional; only if user requested PineScript or system is configured to suggest tooling)

## Example Final Header
**ARBITER SYNTHESIS**  
Lenses active: Market Structure, ICT/SMC, Trendlines  
Bias: Bullish (High confidence)  
Narrative: …  
Contested points: …  

Lenses: Auto-detected from chart elements (user override available)
