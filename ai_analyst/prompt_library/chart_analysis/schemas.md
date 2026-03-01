# Chart Analysis Schemas (Optional)

## Lens Output Schema (internal)
- lens_name: string
- context_bias: string
- observations: [ { claim: string, confidence: High|Medium|Low } ]
- confluence_notes: string
- key_levels: [ { level_or_zone: string, type: string } ]
- limitations: string
- contested_points: [string]

## Arbiter Evidence Ledger Schema (internal)
- claim: string
- source_lens: string
- confidence: High|Medium|Low

## Arbiter Final Schema (user-facing)
- lenses_active: [string]
- overall_bias: Bullish|Bearish|Ranging
- overall_confidence: High|Medium|Low
- evidence_ledger: [string]
- narrative: string
- zones: [string]
- trade_plan: string|null
- no_trade_conditions: [string]
- contested_points: [string]
- visual_limitations: [string]
- pinekraft_script_spec: string|null
