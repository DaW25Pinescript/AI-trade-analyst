# Chart Analysis Runtime Orchestrator (v1.0)

**name:** chart-analysis-orchestrator  
**description:** Single entry point that automatically loads Base + selected lenses + Arbiter when a TradingView screenshot is provided.

## Activation Trigger
Any user message containing a chart image/screenshot OR explicit request to "analyze this chart", "what do you see?", "bias on this setup", etc.

## Runtime Flow (MANDATORY — never deviate)
1. **Load base.md**  
2. **Run lens.auto_detect.md (non-binding)**  
3. **Resolve final lens set**  
   • User-specified lenses override detection  
   • Market Structure ON by default  
4. **Run each selected lens independently (parallel allowed)**  
5. **Run arbiter.md**  
6. **Output ONLY Arbiter synthesis**

## Output Format (enforced)
**ARBITER SYNTHESIS**  
Lenses active: [comma-separated list]  
Overall Bias: Bullish / Bearish / Ranging (Confidence: High/Med/Low)  

**Evidence Ledger** (bullet summary)  
**Narrative**  
**High-Probability Zones** (with PD arrays or levels)  
**Trade Plan** (entries, invalidation, RR) — only if user asked  
**No-Trade Conditions** (if triggered)  
**Contested Points**  
**Visual Limitations** (if any)

## Guardrails
- Never output raw lens outputs to user — only Arbiter final block.  
- If no lenses selected or image too low quality → output Base limitations only + “Please clarify lenses or upload clearer screenshot.”  
- Preserve all PineKraft compatibility for downstream scripting.
- If user did not specify lenses, include a brief line in Arbiter output: “Lenses: Auto-detected from chart elements (user override available).”
