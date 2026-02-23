# AI Trade Analyst V3 Master Plan

## Status

This document consolidates the V3 planning notes from:

- `V3 plan ideas.txt`
- `V3 - G1 draft.txt`
- `V3 - G2.txt`

V3 is considered **ship-ready** with a phased implementation approach. The core direction is a professional-grade trading performance workflow: structured intake, AI analysis output, after-action review, and compounding performance metrics.

## Core Product Direction

- Eliminate ambiguity through enum-driven inputs and structured output.
- Preserve an audit trail from chart narrative to final ticket and AAR outcomes.
- Track psychology and behavior leakage as first-class metrics.
- Support iterative improvement loops via revised ticketing and weekly review.

## Recommended Enhancements from Final Review

### A. Form Inputs

1. Add **Allow counter-trend ideas?** (Strict HTF-only / Mixed / Full counter-trend OK).
2. Support optional **live/auto-filled Price now** from latest screenshot metadata.
3. Add mandatory **Conviction level before AI** selector.
4. For **Conditional** decisions, reveal a secondary mini-ticket block.

### B. Prompt Generation

1. Extend chart narrative with:
   - `Overall bias from charts only (before any user bias injected): Bullish / Bearish / Neutral / Range`
2. Add explicit scoring rule text in the system prompt persona (R:R assumptions and confidence interpretation).

### C. After-Action Review (AAR)

1. Add **AI Edge Score vs Actual Outcome** field.
2. Add **Trade Journal Photo** upload with Ticket ID + timestamp watermarking.
3. Add **Psychological Leakage R** metric (average R lost on trades tagged with behavioral errors).
4. Backlog item: **Shadow Mode** for no-capital, automated review loops.

### D. Data Model Additions

```json
{
  "rawAIReadBias": "",
  "psychologicalLeakR": 0,
  "edgeScore": 0
}
```

### E. Persistence and Export

1. Auto-save timestamped JSON backups in Downloads.
2. Keep exports self-contained by embedding screenshots (base64).

### F. UX and Dashboard

1. Add setup-type × session heatmap.
2. Improve dark-theme print reliability with explicit print color scheme and forced variables.

## Build Order

Recommended implementation order:

`G1 -> G2 -> G3 -> G4 (A1 + A4) -> G5 -> G6 -> G7 -> G8 -> G9 -> G10 -> G11 -> G12`

## Phase Notes

### G1 Draft Baseline

The G1 draft defines a polished dark-theme multi-step UI prototype with:

- Setup, chart uploads, context, checklist gates, and prompt output flow.
- Design system foundation (tokens, card UI, stepper, upload previews).
- Early V3 controls including additional radio/enum style inputs.

### G2 Additions

G2 layers on top of G1 with:

- Dedicated **Test / Prediction Mode** step.
- Structured trade-ticket enums (decision, ticket type, entry, trigger, stop logic, timing, attempts).
- Conditional scenario support and prompt auto-population from form state.
- Navigation expansion from 5 to 6 steps with updated gate interactions.

## Final Verdict

The planning set indicates no major strategic gaps. Remaining work is execution sequencing, data persistence hardening, and dashboard/reporting completion.
