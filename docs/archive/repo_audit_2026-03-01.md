# Repository audit (2026-03-01)

## Scope

This audit reviewed:
- Regression health of both shipped surfaces:
  - Browser app (`node --test tests/*.js`)
  - Python analyst pipeline (`cd ai_analyst && pytest -q`)
- Current roadmap alignment based on `docs/V3_master_plan.md`.

## Current health snapshot

### 1) Browser app test surface
- **PASS**: `node --test tests/*.js`
- Result: **75 passed, 0 failed**.
- Existing coverage includes deterministic scoring/gates, migrations, dashboard metrics, bridge contract behavior, and export/report generation.

### 2) Python analyst test surface
- **PASS**: `cd ai_analyst && pytest -q`
- Result: **117 passed, 0 failed**.
- Existing coverage includes CLI integration, arbiter rules, lens contracts, prompt builders, async graph behavior, retry logic, and schema validation.

## Roadmap status review

`docs/V3_master_plan.md` indicates:
- Track A (Browser app): **G11 in progress** (bridge + operator dashboard evolution).
- Track B (Python pipeline): **v1.4 next** (prompt library v1.2 and lens tuning).
- Track C (integration hardening) depends on schema/API stability and bridge contract maturity.

This aligns with the current repository state: test baseline is healthy, so the highest-value next work should now target execution risk reduction in G11 + v1.4 rather than new unrelated features.

## Next best steps for progression (prioritized)

### Step 1 — Lock release gates in CI (highest leverage)
1. Add/confirm mandatory CI checks for:
   - `node --test tests/*.js`
   - `cd ai_analyst && pytest -q`
2. Fail merges when either gate is red.
3. Add a short contributor checklist in README/CONTRIBUTING for local pre-push parity.

**Why now:** both suites are green today; codifying them as required checks prevents silent regression during G11/v1.4 parallel work.

### Step 2 — Finish G11 with contract-first validation
1. Freeze and document a strict request/response contract for `POST /analyse` as consumed by `app/scripts/api_bridge.js`.
2. Add explicit compatibility tests for browser→API payload mapping and verdict-card rendering edge cases.
3. Add timeout/retry/error-state UX assertions for bridge failures.

**Why now:** G11 is in progress and sits on the runtime boundary where integration defects are most likely.

### Step 3 — Execute v1.4 prompt-lens upgrade with measurable acceptance criteria
1. Create `prompt_library/v1.2/` and keep v1.1 intact for rollback.
2. Add lens metadata + examples as already planned.
3. Define objective checks before promotion (e.g., JSON-valid response rate, forbidden-terminology violations, arbiter parse success).
4. Add version-selection coverage in lens loader tests.

**Why now:** this is the next planned Track B milestone and can improve output quality without destabilizing app UX.

### Step 4 — Prepare Track C schema bridge incrementally
1. Draft a `ticket_draft` mapping spec from `FinalVerdict` → ticket schema fields.
2. Add contract fixtures under tests to validate deterministic mapping.
3. Keep feature flagged until mapping reliability is proven.

**Why now:** this derisks v2.0 integration while G11 and v1.4 mature.

## Suggested 2-week execution order

1. **Week 1:** CI gate enforcement + G11 contract tests.
2. **Week 2:** Prompt library v1.2 implementation + lens loader versioning tests.
3. **Parallel low-risk:** Draft `ticket_draft` mapping fixtures/spec.

## Readiness call

- **Repository stability:** ✅ Healthy baseline (all primary suites green).
- **Best immediate progression target:** ✅ Complete G11 bridge hardening with contract tests, then move directly into v1.4 lens/prompt tuning.
