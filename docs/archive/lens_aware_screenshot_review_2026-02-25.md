# Lens-Aware Screenshot Architecture Review (2026-02-25)

## Scope
Reviewed implementation status of the "Lens-Aware Screenshot Architecture" specification across:
- Backend schema and validation
- API ingestion and screenshot metadata enforcement
- Prompt/analysis phase isolation
- Arbiter input/weighting logic
- Front-end sloting and gating

## Verdict
**Partially implemented.**

The core backend architecture (typed evidence metadata, conditional 15M overlay slot, two-phase isolated analysis, and arbiter weighting instructions) is in place. Several hard constraints from the specification are not fully enforced yet, especially in API/UI validation and the alternate CLI execution path.

## Implemented

1. **Typed screenshot evidence metadata exists and is validated.**
   - `ScreenshotMetadata` enforces `price_only` + `lens=NONE` for clean charts and validates required overlay claims for `indicator_overlay`.

2. **Hard screenshot cap and 15M ICT overlay binding are implemented in backend models.**
   - `GroundTruthPacket` enforces max total screenshots and overlay constraints (M15 only, ICT lens only, overlay metadata required, M15 clean required when overlay exists).

3. **Two-phase clean-first + overlay-delta architecture is implemented with isolated calls.**
   - Prompt builder has Phase 1 clean analysis and Phase 2 overlay delta analysis split.
   - Graph pipeline routes to overlay delta phase only if `m15_overlay` is present.

4. **Delta report schema requires all four fields.**
   - `OverlayDeltaReport` requires `confirms`, `refines`, `contradicts`, and `indicator_only_claims`.

5. **Arbiter receives text-only evidence and includes overlay weighting rules.**
   - Arbiter prompt builder injects overlay delta reports and explicit agreement/refinement/contradiction/indicator-only/risk override/no-trade priority rules.

6. **Automated tests cover these architecture elements.**
   - Pydantic and arbiter rule tests pass and include overlay-specific scenarios.

## Gaps / Non-compliance vs Spec

1. **API does not enforce mandatory clean chart stack (three clean charts).**
   - API currently accepts *at least one* clean chart, while the specification requires clean charts for HTF, M15, and M5.

2. **`settings_locked` is documented as required for comparability, but not enforced as `true`.**
   - Overlay metadata accepts `settings_locked=False` currently.

3. **CLI `ExecutionRouter` path does not run Phase 2 overlay-delta nor pass overlay signals into arbiter prompt.**
   - Router calls Phase 1 analysts and arbiter without overlay delta reports/flags.

4. **Front-end wiring appears incomplete for overlay toggle.**
   - HTML calls `toggleOverlaySlot(...)`, but `main.js` does not export that function onto `window`.

5. **Front-end prompt generator still references legacy screenshot keys (`mid`, `ltf`, `exec`) instead of lens-aware keys (`m15`, `m5`, `m15overlay`).**
   - This suggests the UI prompt output path is not fully aligned with new screenshot architecture.

## Test Evidence
- Ran targeted architecture tests:
  - `pytest ai_analyst/tests/test_pydantic_schemas.py ai_analyst/tests/test_arbiter_rules.py -q`
  - Result: **55 passed**.

## Recommended Next Fixes
1. Enforce exact clean stack requirements at API/model boundary:
   - Require M15 + M5 and one HTF slot (H4 or H1), with explicit cardinality rules.
2. Enforce `settings_locked == true` when overlay is provided.
3. Update `ExecutionRouter` to run overlay delta phase and pass `overlay_delta_reports` + `overlay_was_provided` to arbiter builder.
4. Fix front-end binding for `toggleOverlaySlot` in `main.js`.
5. Update prompt generator screenshot sections to use new keys and metadata language.
