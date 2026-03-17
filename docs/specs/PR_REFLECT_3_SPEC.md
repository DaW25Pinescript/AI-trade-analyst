# AI Trade Analyst — PR-REFLECT-3: Integration Bridge + Rules-Based Suggestions v0 Spec

**Revision History:** Version 1.2 — Post-Second Gate Review
**Status:** ⏳ Spec draft locked — implementation blocked on §8 Step 2 field-name verification
**Date:** 17 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Branch:** `pr-reflect-3-integration`
**Phase:** PR-REFLECT-3 (Phase 8 — final PR)
**Depends on:** PR-CHART-2 complete, PR-REFLECT-2 complete

---

## Pre-Spec Grain Check

| Check | Answer |
|-------|--------|
| **Mutation owner** | None. PR-REFLECT-3 is entirely read-side. No config writes, no parameter changes, no system behavior modification. All suggestions are advisory text rendered in the UI. |
| **Contract surface** | Backend: extends `/reflect/persona-performance` and `/reflect/pattern-summary` with `suggestions[]`. Adds `navigable_entity_id` to `PersonaStats` only if mapping resolution requires it. Frontend: renders suggestions on Reflect Overview; adds cross-workspace navigation from Reflect persona rows to Agent Ops Detail via `#/ops?entity_id={id}&mode=detail`; consumes params once, then clears them with router replace to `#/ops`; hardens Chart ↔ Trace selected-run coherence. |
| **Deletion comfort** | **1 — trivial.** Removing PR-REFLECT-3 means dropping `suggestions[]`, removing `navigable_entity_id` if present, removing `SuggestionPanel`, removing row navigation, removing URL param consumption, and reverting any state-only coherence fixes. No prior PR contract depends on this layer. |

---

## 1. Purpose

After PR-RUN-1, PR-CHART-1, PR-REFLECT-1, PR-REFLECT-2, and PR-CHART-2, the major Phase 8 surfaces exist independently. This phase connects them into a coherent operator workflow without introducing any mutation path or cross-service write coupling.

**From → To**

- **From:** Reflect shows persona and pattern summaries with boolean flags but no actionable guidance text. Persona rows do not lead anywhere. Agent Ops Run mode and chart surfaces consume selected-run context, but coherence under edge conditions has not been explicitly validated and hardened.
- **To:** Reflect Overview surfaces fixed-template, rules-based operator suggestions derived from already-computed aggregate metrics. Persona rows deep-link into Agent Ops Detail mode with preselection. Chart and trace stay coherent on selected-run changes and return to clean state on Run-mode return. Enumerated Phase 8 surfaces have explicit loading/empty/error handling coverage.

> **Scope note:** PR-REFLECT-3 is a convergence and advisory PR. "Influence" analysis is not part of this phase. This phase ships suggestions v0 only.

---

## 2. Scope

### In scope

- **Backend: Suggestion engine v0** — rules-based suggestion computation added to existing reflect aggregation flow
- **Backend: Two rule categories only**
  - persona override frequency
  - instrument × session NO_TRADE concentration
- **Backend: Navigation identifier field** — if mapping resolution requires it, add `navigable_entity_id: string | null` to `PersonaStats`
- **Frontend: Suggestion rendering** — `SuggestionPanel` on Reflect Overview
- **Frontend: Reflect → Agent Ops navigation bridge** — persona row click navigates to `#/ops?entity_id={id}&mode=detail`
- **Frontend: Agent Ops preselection** — params consumed once on mount, then cleared using router replace to `#/ops`
- **Frontend: Chart ↔ Trace coherence hardening** — validate and fix edge-state gaps defined in §6.6
- **Frontend: Polish pass** — loading/empty/error audit only for enumerated Phase 8 surfaces in §6.7

### Out of scope

- No per-analyst chart annotations or overlays
- No new chart rendering features or overlay semantics
- No ML, statistical inference, embeddings, or training
- No config mutation or auto-remediation
- No new persistence
- No new top-level module
- No new backend endpoints
- No changes to `run_record.json`
- No changes to existing ops/runs/trace/detail/roster/health endpoint payloads
- No changes to MDO or market-data pipelines
- No WebSocket/SSE/live push
- No generic advisory framework
- No suggestions in Reflect Run detail
- No filter controls on suggestions
- No "influence," stance-alignment, or confidence-calibration rules
- No retrofitting non-Phase-8 workspaces
- No layout redesigns for Reflect or Agent Ops
- No suggestion categories beyond the two listed in §6.3
- No freeform advisory language beyond fixed templates in §6.4
- No fixes outside the enumerated surfaces in §6.7; such findings are logged only

---

## 3. Repo-Aligned Assumptions

| Area | Assumption | Confidence |
|------|-----------|------------|
| Persona-performance response | `PersonaPerformanceResponse` contains `personas: PersonaStats[]` | Confirmed |
| Pattern-summary response | `PatternSummaryResponse` contains `buckets: PatternBucket[]` | Confirmed |
| Reflect adapter | `reflectAdapter.ts` normalizes reflect responses to view models | Confirmed |
| Reflect hooks | `usePersonaPerformance`, `usePatternSummary` exist | Confirmed |
| Agent Ops routing | `#/ops` renders Agent Ops page with mode selection | Confirmed |
| Chart in Run mode | Chart receives selected-run-derived context | Confirmed |
| Selected-run owner | Agent Ops page owns selected-run state | Confirmed |
| Persona identifier in Reflect | Reflect grouping key is persona-derived identity | Confirmed |
| Agent Ops entity selector | Agent Ops uses profile-registry-backed entity identity | Needs diagnostic mapping verification |

---

## 4. Response Fields Used by This Phase

The field names below are **provisional placeholders** sourced from PR-REFLECT-1 spec §6.2–6.3. **Implementation is blocked** until §8 Step 2 verifies these names against the current `ai_analyst/api/models/reflect.py` source and §13 records the verified names. If any name differs, the spec tables below must be amended before coding begins.

### 4.1 PersonaStats fields (provisional)

| Field (provisional) | Type | Used for |
|---------------------|------|----------|
| `persona_id` | `string` | row identity, mapping source |
| `display_name` | `string` | suggestion message text |
| `participation_count` | `number` | eligibility gate, evidence |
| `override_count` | `number` | trigger evidence |
| `override_rate` | `number \| null` | rule input |
| `flagged` | `boolean` | existing shipped indicator |
| `navigable_entity_id` | `string \| null` | navigation target (always present — see §5) |

### 4.2 PatternBucket fields (provisional)

| Field | Type | Used for |
|-------|------|----------|
| `instrument` | `string` | suggestion message text |
| `session` | `string` | suggestion message text |
| `run_count` | `number` | evidence, threshold gate |
| `threshold_met` | `boolean` | existing bucket eligibility gate |
| `no_trade_rate` | `number \| null` | rule input |
| `flagged` | `boolean` | existing shipped indicator |
| `verdict_distribution` | `VerdictCount[] \| null` | NO_TRADE count derivation |

---

## 5. Navigation Identifier Contract

The backend is the source of truth for row navigability.

### Resolution outcomes

**Regardless of outcome, `navigable_entity_id: string | null` is always present on `PersonaStats`.** This locks one external contract shape. The outcome determines only how the value is computed:

| Outcome | Condition | How `navigable_entity_id` is set | Frontend navigation target |
|---------|-----------|----------------------------------|---------------------------|
| **A: Direct match** | Agent Ops selector uses the same string as Reflect `persona_id` | Set to `persona_id` (identity copy) | `entity_id={navigable_entity_id}` |
| **B: Mapping required** | Agent Ops selector uses a different identifier | Computed via profile registry lookup; null when no mapping | `entity_id={navigable_entity_id}` |

### Deterministic mapping rule

If Outcome B applies, `navigable_entity_id` must be computed on the backend.

### Tie-break rules

| Condition | Behavior |
|-----------|----------|
| One persona maps to one entity | Use that entity |
| Multiple personas map to same entity | Valid; each row points to the same entity |
| Multiple entities match one persona | Backend chooses the first match sorted alphabetically by `entity_id` |
| No entity match | `navigable_entity_id = null` |

The alphabetical tie-break is a deterministic backend-only fallback for consistency, not a semantic preference. If Outcome B occurs, log this tie-break rule to technical debt for review when entity identity is formalized.

The frontend must not implement mapping logic or tie-break logic.

### Post-diagnostic update requirement

After the diagnostic resolves Outcome A or B, the resolved path must be written back into this section (§5) and recorded in §13 **before implementation begins**. The spec must not proceed with both outcomes still open — one must be struck and the other confirmed with evidence.

---

## 6. Design

### 6.1 Operating rules

1. **Aggregation only.** No ML or inference.
2. **Advisory only.** No mutation path.
3. **Minimum threshold.** Suggestions only emit when eligibility rules are met.
4. **Read-side only.** No persistence.

### 6.2 Derived eligibility logic

**Persona eligibility**

Persona suggestions do not use `threshold_met`.

Define:

```
is_eligible_for_suggestion = (participation_count >= 10)
```

This rule is the sole eligibility gate for persona suggestions.

**Pattern eligibility**

Pattern suggestions continue to use the already-shipped bucket gate:

```
is_eligible_for_suggestion = threshold_met
```

### 6.3 Suggestion engine v0

Pure function inside reflect aggregation. It reads existing computed metrics and emits `Suggestion[]`.

### 6.4 Suggestion model

All fields are required.

```typescript
type Suggestion = {
  rule_id: "OVERRIDE_FREQ_HIGH" | "NO_TRADE_CONCENTRATION";
  severity: "warning";
  category: "persona" | "pattern";
  target: string;
  message: string;
  evidence: {
    metric_name: "override_rate" | "no_trade_rate";
    metric_value: number;
    threshold: number;
    sample_size: number;
  };
};
```

### 6.5 Rule definitions

**Rule 1 — OVERRIDE_FREQ_HIGH**

| Field | Value |
|-------|-------|
| Trigger | `override_rate > 0.5` AND `override_rate` is not null AND `participation_count >= 10` |
| Category | `"persona"` |
| Target | `display_name` |
| Evidence metric | `override_rate` |
| Evidence threshold | `0.5` |
| Evidence sample size | `participation_count` |

**Rule 2 — NO_TRADE_CONCENTRATION**

| Field | Value |
|-------|-------|
| Trigger | `no_trade_rate > 0.8` AND `no_trade_rate` is not null AND `threshold_met` is true |
| Category | `"pattern"` |
| Target | `"{instrument} × {session}"` |
| Evidence metric | `no_trade_rate` |
| Evidence threshold | `0.8` |
| Evidence sample size | `run_count` |

### 6.6 Threshold constants

```python
OVERRIDE_RATE_THRESHOLD = 0.5
NO_TRADE_RATE_THRESHOLD = 0.8
PERSONA_MIN_PARTICIPATION = 10
```

### 6.7 Ordering and deduplication

**Ordering**

- Within each endpoint response: descending `evidence.metric_value`, then ascending `target`
- Frontend merged panel: persona suggestions first, pattern suggestions second, preserving internal endpoint order

**Deduplication**

Each `(rule_id, target)` pair must be unique per response. If duplicates occur, keep the one with the higher `evidence.sample_size`.

### 6.8 Fixed message templates

**OVERRIDE_FREQ_HIGH**

```
"{display_name} was overridden in {override_count} of {participation_count} recent runs (override rate {override_rate_pct}%) — consider reviewing its analysis focus or prompt configuration"
```

**NO_TRADE_CONCENTRATION**

```
"{instrument} {session} session produced NO_TRADE in {no_trade_count} of {run_count} recent runs ({no_trade_rate_pct}%) — confidence threshold may be too high for this instrument/session combination"
```

Only variable substitution is allowed.

**Template variable derivation rules**

| Variable | Source | Derivation |
|----------|--------|------------|
| `{no_trade_count}` | `verdict_distribution` array | Sum of `count` where `verdict == "NO_TRADE"`. If `verdict_distribution` is null, the suggestion must not be emitted. If `verdict_distribution` is present but contains no `NO_TRADE` entry, `no_trade_count = 0` — the trigger condition (`no_trade_rate > 0.8`) will not fire, so no suggestion is emitted via the normal rule gate. |
| `{override_rate_pct}` | `override_rate` | `round(override_rate * 100)` |
| `{no_trade_rate_pct}` | `no_trade_rate` | `round(no_trade_rate * 100)` |

**Backend emission guard:** If any required template variable cannot be resolved (e.g., `verdict_distribution` is null when `no_trade_count` is needed, or `override_count` is null), the backend must not emit that suggestion item. Structurally malformed `verdict_distribution` (e.g., not an array, entries missing required fields) is treated the same as null — the suggestion is suppressed. Partially-populated suggestions are never emitted.

**`run_count > 0` invariant:** `threshold_met` is expected to be true only when `run_count >= threshold` (minimum 10), which guarantees `run_count > 0` when pattern suggestions fire. The diagnostic (§8 Step 1) must verify this derivation rule against the shipped reflect model/service. Once verified, record the exact source reference in §13 and treat it as part of the locked contract — not just supporting evidence.

### 6.9 Response extensions

| Response | New field | Default | Presence |
|----------|-----------|---------|----------|
| `PersonaPerformanceResponse` | `suggestions: Suggestion[]` | `[]` | Always |
| `PatternSummaryResponse` | `suggestions: Suggestion[]` | `[]` | Always |
| `PersonaStats` | `navigable_entity_id: string \| null` | `null` | Always (both Outcome A and B) |

Use `Field(default_factory=list)` for suggestions. `navigable_entity_id` is always present regardless of mapping outcome — the value changes, the field does not.

### 6.10 Suggestion rendering

A new `SuggestionPanel` appears on Reflect Overview above the existing tables.

**SuggestionPanel states**

| State | Behavior |
|-------|----------|
| Both endpoints loading | Panel hidden |
| Both endpoints return empty suggestions | Panel hidden |
| One or more valid suggestions | Panel shown |
| One endpoint errors, other has suggestions | Panel shown with inline partial-results warning |
| One endpoint errors, other has no suggestions | Panel hidden; failed table shows normal error state |
| Both endpoints error | Panel hidden; tables show normal error states |
| One source stale, one fresh | Stale indication stays local to source table; not duplicated on panel |
| All suggestions malformed | Panel hidden; normal table error/loading states remain authoritative |

### 6.11 Defensive handling

**Multiple `entity_id` params**

If multiple `entity_id` params are present, the first one wins.

**Multiple `mode` params**

If multiple `mode` params are present, the first one wins.

**Unknown extra params**

Unknown params are ignored.

**Empty-string param values**

An empty `entity_id` (`?entity_id=&mode=detail`) is treated as absent — Detail mode opens with no entity selected. An empty `mode` (`?entity_id=X&mode=`) falls back to default mode behavior.

**Below-threshold personas**

Personas with `participation_count < 10` may still display metrics and existing table data, but they must never emit suggestions.

**Total malformed suggestions**

If all suggestion items are malformed after adapter validation, the panel stays hidden. Existing endpoint/table loading and error states remain unchanged.

**Backend validity**

Backend must only emit fully valid Suggestion objects. If any required template variable (§6.8) cannot be resolved — for example, `verdict_distribution` is null when `no_trade_count` is needed, or `override_count` is null — that suggestion must not be emitted. Frontend malformed-item dropping is defensive hardening, not a normal data path.

### 6.12 Reflect → Agent Ops navigation

**Route format**

Exact deep-link:

```
#/ops?entity_id={resolved_id}&mode=detail
```

**Param consumption policy**

This phase uses the **Clear Params** policy.

1. Read params once on mount
2. Apply mode/entity selection
3. Clear params using router replace to `#/ops`
4. Do not persist param binding

Because params are cleared after consumption, bookmarks saved after navigation will preserve only the base `#/ops` state.

**Router replace requirement:** Clearing must use the router's `replace()` method (or equivalent that replaces the current history entry rather than pushing a new one). If the diagnostic determines that router-native replace is not feasible under the current HashRouter setup, **implementation is blocked pending spec amendment** — manual `window.location.hash` mutation is not an acceptable substitute because it breaks React Router's internal state.

**Refresh/history semantics**

| Scenario | Behavior |
|----------|----------|
| Navigate from Reflect row click | App lands on parameterized URL, consumes params, then `replace()` to `#/ops` |
| Refresh before params are cleared | Params are re-consumed |
| Refresh after params are cleared | Base `#/ops` state only |
| Bookmark after params are cleared | Base `#/ops` state only |
| Back button after consume | Returns according to replaced history entry; no duplicate param replay |
| `#/ops` with no params | Default behavior |
| `#/ops?mode=detail` | Detail mode with no entity selected |
| `#/ops?entity_id=X` | Default mode; ignore entity-only deep-link |

**Unknown entity handling**

If resolved `entity_id` is not found, Detail mode shows:

> "Entity not found — it may no longer be in the active roster."

This state must reuse the existing Detail shell and remain text-only.

### 6.13 Chart ↔ Trace selected-run coherence

This is state hardening only. No new chart rendering features.

**Locked conditions**

| ID | Condition | Required behavior |
|----|-----------|-------------------|
| C-1 | Run selected | Chart marker/annotation and trace both update |
| C-2 | Run cleared | Chart returns to no-marker state; trace shows no-run state |
| C-3 | Run no longer on disk | Both degrade gracefully; no crash |
| C-4 | Instrument mismatch | Chart switches to the run's instrument; if unavailable, show chart no-data state and suppress marker |
| C-5 | Rapid run changes | Last selection wins |
| C-6 | Leave Run mode, return | Selected run must be cleared on return |

**C-6 is fixed.** Preservation is not allowed in this phase.

### 6.14 Enumerated polish surfaces

Only these surfaces are in scope for state-audit completion:

| Surface | Loading | Empty | Error | Stale |
|---------|---------|-------|-------|-------|
| Run Browser | ⬜ | ⬜ | ⬜ | N/A |
| Chart: TF discovery | ⬜ | ⬜ | ⬜ | N/A |
| Chart: candle fetch | ⬜ | ⬜ | ⬜ | N/A |
| Chart: run marker state | N/A | ⬜ | N/A | N/A |
| Reflect: persona perf | ✅ | ✅ | ✅ | ✅ |
| Reflect: pattern summary | ✅ | ✅ | ✅ | ✅ |
| Reflect: run detail | ✅ | ✅ | ✅ | ✅ |
| Reflect: suggestions | §6.10 | §6.10 | §6.10 | §6.10 |

---

## 7. Acceptance Criteria

### 7.1 Backend — suggestion engine

| ID | Acceptance condition | Status |
|----|---------------------|--------|
| AC-1 | `GET /reflect/persona-performance` includes `suggestions: Suggestion[]` | ⏳ Pending |
| AC-2 | `GET /reflect/pattern-summary` includes `suggestions: Suggestion[]` | ⏳ Pending |
| AC-3 | Persona rule fires when `override_rate > 0.5` and `participation_count >= 10` | ⏳ Pending |
| AC-4 | Persona rule does not fire when `override_rate > 0.5` but `participation_count < 10` | ⏳ Pending |
| AC-5 | Persona rule does not fire when `override_rate` is null | ⏳ Pending |
| AC-6 | Pattern rule fires when `no_trade_rate > 0.8` and `threshold_met` is true | ⏳ Pending |
| AC-7 | Pattern rule does not fire when `threshold_met` is false | ⏳ Pending |
| AC-8 | Pattern rule does not fire when `no_trade_rate` is null | ⏳ Pending |
| AC-9 | Pattern rule: when `verdict_distribution` is present but has no `NO_TRADE` entry, `no_trade_count` derives as 0 and the rule does not fire | ⏳ Pending |
| AC-10 | Pattern rule: when `verdict_distribution` is structurally malformed (not an array, entries missing fields), suggestion is suppressed — same as null | ⏳ Pending |
| AC-11 | No triggers produces `suggestions: []` | ⏳ Pending |
| AC-12 | Multiple triggers produce multiple suggestions | ⏳ Pending |
| AC-13 | Every suggestion object matches full schema and enums | ⏳ Pending |
| AC-14 | Messages conform exactly to fixed templates | ⏳ Pending |
| AC-15 | Ordering follows §6.7 | ⏳ Pending |
| AC-16 | Deduplication follows §6.7 | ⏳ Pending |
| AC-17 | Adding `suggestions[]` does not alter existing field serialization | ⏳ Pending |
| AC-18 | No write path or config mutation exists | ⏳ Pending |
| AC-19 | If Outcome B applies, `navigable_entity_id` is computed backend-side | ⏳ Pending |
| AC-20 | If multiple entities match one persona, backend picks alphabetically first `entity_id` | ⏳ Pending |
| AC-21 | If no entity maps, `navigable_entity_id` is null | ⏳ Pending |

### 7.2 Frontend — suggestion rendering

| ID | Acceptance condition | Status |
|----|---------------------|--------|
| AC-22 | `SuggestionPanel` renders when at least one valid suggestion exists | ⏳ Pending |
| AC-23 | `SuggestionPanel` is hidden when merged suggestions are empty | ⏳ Pending |
| AC-24 | Merged panel order is persona first, pattern second | ⏳ Pending |
| AC-25 | Evidence accessible via hover tooltip showing metric name, value, threshold, and sample size | ⏳ Pending |
| AC-26 | No action buttons exist | ⏳ Pending |
| AC-27 | Mixed-success state shows partial-results warning and valid suggestions | ⏳ Pending |
| AC-28 | Invalid suggestion items are dropped with `console.warn` | ⏳ Pending |
| AC-29 | If all suggestions are malformed, panel stays hidden and normal endpoint/table states remain authoritative | ⏳ Pending |
| AC-30 | Below-threshold personas still render table metrics but emit no suggestion UI | ⏳ Pending |
| AC-31 | When both endpoints succeed and suggestions exist, no partial-results warning is shown | ⏳ Pending |

### 7.3 Cross-workspace navigation

| ID | Acceptance condition | Status |
|----|---------------------|--------|
| AC-32 | Clicking a navigable persona row produces `#/ops?entity_id={id}&mode=detail` | ⏳ Pending |
| AC-33 | Agent Ops consumes params on mount and opens Detail mode with selected entity | ⏳ Pending |
| AC-34 | Unknown entity shows text-only entity-not-found state inside Detail shell | ⏳ Pending |
| AC-35 | Null navigation identifier makes row non-clickable | ⏳ Pending |
| AC-36 | Navigable rows show pointer/hover affordance; non-navigable rows do not | ⏳ Pending |
| AC-37 | If multiple `entity_id` params exist, first one wins | ⏳ Pending |
| AC-38 | If multiple `mode` params exist, first one wins | ⏳ Pending |
| AC-39 | Unknown extra params are ignored | ⏳ Pending |
| AC-40 | Empty-string `entity_id` is treated as absent | ⏳ Pending |
| AC-41 | Empty-string `mode` falls back to default mode behavior | ⏳ Pending |
| AC-42 | `?mode=detail` with no entity opens Detail mode with no entity selected | ⏳ Pending |
| AC-43 | `?entity_id=X` with no mode leaves page in default mode and ignores entity-only param | ⏳ Pending |
| AC-44 | After param consumption, app uses router replace to clear URL to `#/ops` | ⏳ Pending |
| AC-45 | Browser history does not retain a second replayable parameterized state after consume/clear | ⏳ Pending |
| AC-46 | Zero-param Agent Ops initialization behaves exactly as before | ⏳ Pending |
| AC-47 | Non-Reflect entry into `#/ops` (e.g., from nav bar) is unaffected by param-consumption logic | ⏳ Pending |
| AC-48 | Existing non-Reflect entry into Detail mode (e.g., clicking an entity in the roster) is unaffected | ⏳ Pending |

### 7.4 Chart ↔ Trace coherence

| ID | Acceptance condition | Status |
|----|---------------------|--------|
| AC-49 | C-1: both chart and trace update on selected run | ⏳ Pending |
| AC-50 | C-2: clearing run clears both surfaces | ⏳ Pending |
| AC-51 | C-3: stale/deleted run degrades without crash | ⏳ Pending |
| AC-52 | C-4: chart never shows marker on wrong instrument; unavailable instrument yields no-data state and suppressed marker | ⏳ Pending |
| AC-53 | C-5: rapid changes resolve to last selection only | ⏳ Pending |
| AC-54 | C-6: leaving Run mode and returning yields a clean state with selected run cleared | ⏳ Pending |

### 7.5 Polish and containment

| ID | Acceptance condition | Status |
|----|---------------------|--------|
| AC-55 | Run Browser has loading, empty, and error states present | ⏳ Pending |
| AC-56 | Chart TF discovery has loading, empty, and error states present | ⏳ Pending |
| AC-57 | Chart candle fetch has loading, empty, and error states present | ⏳ Pending |
| AC-58 | Chart run marker has empty/no-run state present | ⏳ Pending |
| AC-59 | SuggestionPanel states match §6.10 definitions | ⏳ Pending |
| AC-60 | Any gap found in a non-enumerated surface is logged in §13 as non-blocking, not fixed | ⏳ Pending |
| AC-61 | Every shared-component edit is named in §13 with the enumerated surface it serves | ⏳ Pending |
| AC-62 | No changes to non-Phase-8 workspace internals | ⏳ Pending |
| AC-63 | No new persistence | ⏳ Pending |
| AC-64 | No new top-level module | ⏳ Pending |
| AC-65 | `run_record.json` format unchanged | ⏳ Pending |
| AC-66 | No new chart rendering features, props, or visual elements | ⏳ Pending |
| AC-67 | Pre-existing backend test failure count unchanged | ⏳ Pending |
| AC-68 | Pre-existing frontend test failure count unchanged | ⏳ Pending |
| AC-69 | No existing endpoint payload contracts changed (Agent Ops UI state handling changes expected and regression-tested via AC-46/47/48) | ⏳ Pending |
| AC-70 | Persona row navigation is mouse-click only in v0 — keyboard activation deferred and logged as tech debt. Existing keyboard behavior must not regress. | ⏳ Pending |
| AC-71 | Backend never emits a suggestion with unresolvable template variables (§6.8 derivation rules) | ⏳ Pending |

---

## 8. Pre-Code Diagnostic Protocol

**Do not implement until this diagnostic is completed and reviewed.**

### Step 1 — Suggestion engine insertion point

**Inspect:**
- `ai_analyst/api/services/reflect_aggregation.py`
- `ai_analyst/api/models/reflect.py`
- `tests/test_reflect_endpoints.py`

**Report:**
- Where current `flagged` logic is computed
- Whether `Field(default_factory=list)` is required
- Whether strict response-shape assertions exist in backend tests
- Whether frontend adapters or tests reject additive response fields (strict-key guards in `reflectAdapter.ts` or `reflect.test.tsx`)
- Exact derivation path for `no_trade_count`: which field in `verdict_distribution`, what filter value, what happens when `verdict_distribution` is null
- Shipped `threshold_met` derivation rule: verify that `threshold_met == true` implies `run_count >= threshold` (record the exact source line)

### Step 2 — Field-name verification against source

Inspect `ai_analyst/api/models/reflect.py` and verify the exact current field names for:
- `persona_id`
- `display_name`

**Report:**
- Exact source-defined field names
- Whether spec names match implementation
- Any required spec correction before coding

### Step 3 — Persona → entity mapping

**Inspect:**
- Agent Ops page selection state
- Roster service
- Persona/profile registry
- Reflect aggregation sources

**Report prominently:**
- Whether Outcome A or Outcome B applies
- Exact mapping table

**Required output table:**

| Source field (Reflect) | Transform | Destination field (Agent Ops) | Sample values | Collision possible? |
|------------------------|-----------|-------------------------------|---------------|---------------------|

### Step 4 — URL param feasibility

**Inspect:**
- Agent Ops page
- Router setup
- Any existing search-param usage

**Report:**
- Whether router-native search params work under current HashRouter
- Whether manual hash parsing is required
- Exact mechanism for consume and clear
- Whether clearing uses router replace rather than direct location mutation
- Whether router-level changes are required

### Step 5 — Entity-not-found, row interaction, and tooltip primitive

**Inspect:**
- Existing Detail-mode empty/not-found handling
- Reflect tests for row interactivity assumptions
- Whether a reusable tooltip primitive exists in the shared component library (to avoid accidental UI-component scope creep during SuggestionPanel work)

**Report:**
- Whether entity-not-found state already exists
- Whether new text-only state is required
- Which tests must change due to rows becoming clickable
- Whether an existing tooltip component can be used for suggestion evidence, or whether a new one is needed (and if so, estimated scope)
- Confirm that the frontend adapter's malformed-item dropping behavior can be tested against realistic bad payloads (missing fields, wrong types, unknown rule_id). Note any test infrastructure needed.

### Step 6 — Chart ↔ Trace coherence audit

Validate C-1 through C-6 using component tests, manual repro, or code inspection with reasoning.

For each condition report:
- Method used
- Observed outcome
- Pass/fail
- Repro steps if failing

### Step 7 — Phase 8 state audit

Audit only surfaces in §6.14.

**Report:**
- Loading/empty/error/stale coverage per surface
- Any missing state
- Whether missing states are blocking or non-blocking

### Step 8 — Baseline tests

**Report:**
- Backend test counts and pre-existing failures
- Frontend test counts and pre-existing failures

### Step 9 — Smallest patch set

**Report:**
- Files to create
- Files to modify
- Estimated line deltas
- Outcome A vs B impact
- Any scope flags

---

## 9. Implementation Constraints

### General rule

Every change must be minimal, additive, and independently removable.

### Sequence

1. Backend suggestion model and engine
2. Backend tests
3. Frontend SuggestionPanel
4. Persona row navigation
5. Agent Ops consume-and-clear param handling
6. Entity-not-found state if required
7. Coherence fixes for C-1 through C-6
8. Enumerated polish only
9. New tests
10. Doc closure

### Containment constraints

- Router-level changes are permitted only if needed for exact deep-link support
- Any entity-not-found UI must reuse existing Detail shell and remain text-only
- Any chart changes must be state-only coherence fixes
- Frontend mapping logic is prohibited
- Unknown polish outside §6.14 must be logged, not fixed

---

## 10. Success Definition

PR-REFLECT-3 is complete when:
- Reflect Overview shows suggestion output for exactly two rules using fixed templates
- Persona rows navigate into Agent Ops Detail mode through the exact deep-link format
- Params are consumed once and cleared using router replace
- Bookmarks after consume preserve only base `#/ops` state
- Backend mapping is deterministic when Outcome B applies
- Below-threshold personas never emit suggestions
- Chart and trace satisfy all six coherence conditions, including required clear-on-return behavior
- Enumerated Phase 8 surfaces are audited and any gaps are fixed or logged
- No mutation path, persistence, new rendering features, or Phase 6/7 expansion is introduced
- Test baselines remain stable

**Implementation-blocking prerequisites:** This PR cannot proceed if (a) §8 Step 2 field-name verification is incomplete, (b) §5 Outcome A/B is unresolved, or (c) the diagnostic determines router-native replace is unavailable under the current routing architecture (§6.12).

---

## 11. Why This Phase Matters

| Without this phase | With this phase |
|--------------------|-----------------|
| Reflect flags are passive | Reflect provides auditable operator guidance |
| Persona rows are dead ends | Persona rows bridge directly to entity inspection |
| Run-state coherence is assumed | Run-state coherence is verified and hardened |
| Surface state coverage is unevenly proven | Phase 8 surfaces have explicit audit coverage |
| Workspaces feel disconnected | Operator loop becomes navigable and coherent |

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| PR-RUN-1 | Run Browser | ✅ Done |
| PR-CHART-1 | OHLCV seam + chart | ✅ Done |
| PR-REFLECT-1 | Aggregation endpoints | ✅ Done |
| PR-REFLECT-2 | Reflect frontend | ✅ Done |
| PR-CHART-2 | Run context overlay + multi-TF | ✅ Done |
| **PR-REFLECT-3** | **Integration + suggestions v0** | **⏳ Spec draft locked** |

---

## 13. Diagnostic Findings

*Populated by §8 diagnostic run — 17 March 2026.*

### 13.1 Field-name verification (§8 Step 2)

**Source:** `ai_analyst/api/models/reflect.py` lines 21–31

| Spec §4.1 provisional name | Actual field in `PersonaStats` | Match? | Action |
|----------------------------|-------------------------------|--------|--------|
| `persona_id` | `persona` (str, line 22) | **NO** | Rename spec field to `persona` |
| `display_name` | **Does not exist** | **NO** | Backend uses `persona` as both grouping key and display text. Spec must substitute `persona` for `display_name` in message templates. |
| `participation_count` | `participation_count` (int, line 23) | ✅ | — |
| `override_count` | `override_count` (int, line 27) | ✅ | — |
| `override_rate` | `override_rate` (Optional[float], line 28) | ✅ | — |
| `flagged` | `flagged` (bool, line 31) | ✅ | — |

**PatternBucket fields** (lines 46–53): All match spec §4.2 exactly — `instrument`, `session`, `run_count`, `threshold_met`, `verdict_distribution`, `no_trade_rate`, `flagged`.

**Frontend type mirror** (`ui/src/shared/api/reflect.ts` lines 11–22): Matches backend model. Field is `persona: string`, not `persona_id`.

**Correction required before coding:** §4.1 must change `persona_id` → `persona` and strike `display_name` (use `persona` in templates instead). The OVERRIDE_FREQ_HIGH template becomes: `"{persona} was overridden in {override_count} of {participation_count} recent runs (override rate {override_rate_pct}%) — consider reviewing its analysis focus or prompt configuration"`

### 13.2 Outcome A vs B resolution (§8 Step 3)

**OUTCOME B — mapping required.**

**Evidence:**
- Reflect backend grouping key: `PersonaStats.persona` populated via `_persona_key()` → values are bare `PersonaType` enum strings (from `ai_analyst/models/persona.py`): `"default_analyst"`, `"risk_officer"`, `"prosecutor"`, `"ict_purist"`, `"skeptical_quant"`
- Agent Ops entity IDs: defined in `ai_analyst/api/services/ops_roster.py` with `"persona_"` prefix: `"persona_default_analyst"`, `"persona_risk_officer"`, `"persona_prosecutor"`, `"persona_ict_purist"`, `"persona_skeptical_quant"`, plus `"persona_technical_structure"`, `"persona_execution_timing"`

**Mapping table:**

| Source field (Reflect `persona`) | Transform | Destination field (Agent Ops `id`) | Sample values | Collision possible? |
|----------------------------------|-----------|-------------------------------------|---------------|---------------------|
| `"default_analyst"` | prepend `"persona_"` | `"persona_default_analyst"` | Reflect: `"default_analyst"` → Ops: `"persona_default_analyst"` | No |
| `"ict_purist"` | prepend `"persona_"` | `"persona_ict_purist"` | Reflect: `"ict_purist"` → Ops: `"persona_ict_purist"` | No |
| `"risk_officer"` | prepend `"persona_"` | `"persona_risk_officer"` | Reflect: `"risk_officer"` → Ops: `"persona_risk_officer"` | No |
| `"prosecutor"` | prepend `"persona_"` | `"persona_prosecutor"` | Reflect: `"prosecutor"` → Ops: `"persona_prosecutor"` | No |
| `"skeptical_quant"` | prepend `"persona_"` | `"persona_skeptical_quant"` | Reflect: `"skeptical_quant"` → Ops: `"persona_skeptical_quant"` | No |

**Transform rule:** `navigable_entity_id = f"persona_{persona}"` — deterministic, collision-free.

**Tie-break:** Not needed. Each PersonaType maps to exactly one ops roster ID. Logged as tech debt in case future persona aliasing creates ambiguity.

### 13.3 `threshold_met` derivation rule (§8 Step 1)

**PersonaPerformanceResponse:**
- `reflect_aggregation.py` line 171: `if len(runs) < _THRESHOLD:` → returns `threshold_met=False` (line 177)
- `reflect_aggregation.py` line 283: `threshold_met=True` (reached only when `len(runs) >= _THRESHOLD`)
- `_THRESHOLD = 10` (line 27)

**PatternBucket:**
- `reflect_aggregation.py` line 313: `if len(items) < _THRESHOLD:` → `threshold_met=False` (line 318)
- `reflect_aggregation.py` line 338: `threshold_met=True` (reached only when `len(items) >= _THRESHOLD`)

**Verified rule:** `threshold_met == True` ⟹ `run_count >= 10` ⟹ `run_count > 0`. This guarantees no division-by-zero when computing rates. **Locked as contract.**

### 13.4 `no_trade_count` derivation path (§8 Step 1)

**Source:** `reflect_aggregation.py` lines 325–341

1. `verdicts: dict[str, int] = defaultdict(int)` — accumulates verdict counts from runs
2. Line 327: `v = str(run["arbiter"].get("verdict") or "UNKNOWN").upper()` → verdict string
3. Line 330: `no_trade = verdicts.get("NO_TRADE", 0)` — if no NO_TRADE entry, defaults to 0
4. Line 331: `no_trade_rate = no_trade / len(items)` — always safe since `len(items) >= _THRESHOLD >= 10`

**Confirmed derivation for suggestion engine:**
- Extract `no_trade_count` from `verdict_distribution` array: sum `count` where `verdict == "NO_TRADE"`
- `verdict_distribution` present with no `NO_TRADE` entry → `no_trade_count = 0` → `no_trade_rate = 0` → rule does not fire ✓
- `verdict_distribution` is null → suggestion suppressed (backend model declares `list[VerdictCount]` not Optional; null would only occur from malformed external data — treated same as null per spec) ✓
- Structurally malformed `verdict_distribution` → treated same as null, suggestion suppressed ✓

### 13.5 URL param mechanism (§8 Step 4)

**Router:** `createHashRouter` from `react-router-dom ^6.28.0` (`ui/src/app/router.tsx` line 7)

**Existing precedent:** `AnalysisRunPage.tsx` (line 28) already uses `useSearchParams()` with hash-based URLs: `#/analysis?asset=SYMBOL`

**Mechanism:**
1. `useSearchParams()` reads params from hash URL — confirmed working with `createHashRouter`
2. `useNavigate()` returns navigate function
3. `navigate("/ops", { replace: true })` replaces current history entry — equivalent to `router.replace()`
4. `<Navigate to="/triage" replace />` already used in router config (line 20) — confirms `replace` support

**Router-native replace: FEASIBLE.** Implementation is **not blocked** per §6.12.

**`URLSearchParams.get()` returns first value when duplicates exist** — satisfies AC-37/38 natively.

### 13.6 Entity-not-found state (§8 Step 5)

**Existing:** Agent Ops Detail uses `AgentDetailSidebar` (shown when `selectedId !== null && mode !== "run"`, line 162). The sidebar renders entity details from roster data but has **no entity-not-found fallback** — it assumes selectedId always maps to a roster entry.

**Required:** New text-only not-found state inside the existing detail sidebar shell. Estimated: ~8 lines of JSX. Reuses existing `AgentDetailSidebar` container; no layout change.

### 13.7 Tooltip primitive (§8 Step 5)

**Audit:** Searched `ui/src/` for `tooltip`, `Tooltip`, radix, shadcn, headless-ui. Found only `DataStateBadge` using native HTML `title` attribute (line 28).

**Result:** No reusable tooltip component exists. Two options:
1. Use native HTML `title` attribute for evidence display (zero scope, but limited formatting)
2. Create a minimal `<Tooltip>` component (~30 lines) for richer evidence display

**Recommendation:** Use native `title` attribute for v0 (fixed text format: "metric_name: value, threshold: threshold, sample: sample_size"). Log custom tooltip as enhancement debt. This avoids UI-component scope creep.

### 13.8 Strict-key assertion audit (§8 Step 1)

**Backend tests** (`tests/test_reflect_endpoints.py`): Assert specific field values (e.g., `assert data["threshold_met"] is False`) but do NOT assert exhaustive key sets. Additive fields like `suggestions[]` will not cause test failures. Pydantic models do not use `model_config = ConfigDict(extra="forbid")`.

**Frontend types** (`ui/src/shared/api/reflect.ts`): TypeScript types are structural — extra fields from JSON responses are silently accepted. No runtime schema validation or strict-key guards.

**Frontend adapter** (`reflectAdapter.ts`): Pure destructuring — picks known fields, ignores extras. Adding `suggestions[]` to responses will not break existing adapter functions.

**Frontend tests** (`ui/tests/reflect.test.tsx`): Fixture factories use spread overrides (`...overrides`) — extra fields pass through without assertion failures.

**Conclusion:** No strict-key rejection on either side. Additive `suggestions[]` and `navigable_entity_id` fields are safe.

### 13.9 Reflect row interaction test impact (§8 Step 5)

**Current state:** `PersonaPerformanceTable` renders rows as `<tr>` elements. Tests assert text content (`screen.getByText("default_analyst")`) and row count, but no tests assert click handlers or navigation behavior on persona rows.

**Impact:** Making rows clickable (mouse-click-only per AC-70) will require:
- Adding `onClick` handlers to navigable persona `<tr>` elements
- Adding pointer/hover affordance CSS for navigable rows
- No existing test breakage expected — tests don't assert that rows are non-interactive
- New tests needed: row click triggers navigation, null navigable_entity_id row is non-clickable

### 13.10 Malformed suggestion frontend testability (§8 Step 5)

**Confirmed testable.** The adapter pattern (pure function in → view model out) supports direct unit testing against arbitrary payloads:
- Missing fields: pass `{ rule_id: "OVERRIDE_FREQ_HIGH" }` (no message, no evidence)
- Wrong types: pass `{ rule_id: 123, severity: null }`
- Unknown rule_id: pass `{ rule_id: "UNKNOWN_RULE", ... }`
- Empty array: pass `[]`
- Non-array: pass `"not an array"`

Vitest + existing test infrastructure fully supports this. No new test tooling needed.

### 13.11 Chart ↔ Trace coherence C-1 through C-6 (§8 Step 6)

| ID | Condition | Method | Observed | Pass/Fail |
|----|-----------|--------|----------|-----------|
| C-1 | Run selected → both update | Code inspection: `AgentOpsPage.tsx` lines 142–152 sets `selectedRunId` + `selectedInstrument` + `selectedRunTimestamp` + `selectedRunVerdict`. Chart receives timestamp/verdict props (line 301–302); Trace receives runId (line 310). | Both surfaces receive updated props on run selection. | **PASS** |
| C-2 | Run cleared → both clean | Code inspection: `handleSelectRun(null)` sets all to null. Chart: `selectedRunTimestamp=null` → `useMarkerState` returns `{ type: "no-run" }` → markers cleared (line 286). Trace: `selectedRunId=null` → `RunTracePanel` not rendered (line 310 conditional). | Both surfaces reset. | **PASS** |
| C-3 | Run no longer on disk | Code inspection: `RunTracePanel` line 32–44 handles query error with `ErrorState`. Chart: if candle data unavailable, shows error/empty state. | Graceful degradation, no crash. | **PASS** |
| C-4 | Instrument mismatch | Code inspection: Chart `instrument` prop comes from `selectedInstrument` which is set from the run's instrument on row click (line 149). Chart always renders for the run's instrument. If OHLCV unavailable, chart shows `chart-empty` or `chart-error` state. | Chart switches to run's instrument; unavailable yields no-data state. | **PASS** |
| C-5 | Rapid run changes | Code inspection: React `useState` setter batching. Each `handleSelectRun` call sets state synchronously. React renders with latest state. | Last selection wins (React guarantees). | **PASS** |
| C-6 | Leave Run mode, return → cleared | Code inspection: `handleModeChange` (line 137–140) calls `setMode(newMode)` only — does NOT clear `selectedRunId`, `selectedInstrument`, `selectedRunTimestamp`, `selectedRunVerdict`. | **Selected run persists across mode switches.** | **FAIL** |

**C-6 fix required:** `handleModeChange` must clear `selectedRunId`, `selectedInstrument`, `selectedRunTimestamp`, and `selectedRunVerdict` when the new mode is not `"run"`, or unconditionally when entering Run mode. Per spec §6.13: "C-6 is fixed. Preservation is not allowed."

**Proposed fix (AgentOpsPage.tsx line 137–140):**
```typescript
const handleModeChange = useCallback((newMode: OpsMode) => {
  if (mode === "run" && newMode !== "run") {
    setSelectedRunId(null);
    setSelectedInstrument(null);
    setSelectedRunTimestamp(null);
    setSelectedRunVerdict(null);
  }
  setMode(newMode);
}, [mode]);
```

### 13.12 Phase 8 state audit (§8 Step 7)

| Surface | Loading | Empty | Error | Stale | Evidence |
|---------|---------|-------|-------|-------|----------|
| Run Browser | ✅ `run-browser-loading` | ✅ `run-browser-empty` | ✅ `run-browser-error` | N/A | `RunBrowserPanel.tsx` lines 82–116 |
| Chart: TF discovery | ✅ `tf-loading` | ✅ `tf-no-timeframes` | ✅ `tf-discovery-failed` | N/A | `AgentOpsPage.tsx` lines 284–298 |
| Chart: candle fetch | ✅ `chart-loading` | ✅ `chart-empty` | ✅ `chart-error` | N/A | `CandlestickChart.tsx` lines 317–367 |
| Chart: run marker | N/A | ✅ `no-run` → markers cleared | N/A | N/A | `CandlestickChart.tsx` line 286 |
| Reflect: persona perf | ✅ | ✅ | ✅ | ✅ | Already shipped (PR-REFLECT-2) |
| Reflect: pattern summary | ✅ | ✅ | ✅ | ✅ | Already shipped (PR-REFLECT-2) |
| Reflect: run detail | ✅ | ✅ | ✅ | ✅ | Already shipped (PR-REFLECT-2) |
| Reflect: suggestions | — | — | — | — | New (§6.10 governs) |

**All enumerated surfaces have full state coverage.** No blocking gaps. The only new surface (SuggestionPanel) will be implemented per §6.10.

### 13.13 Baseline test counts (§8 Step 8)

**Backend:**
- 155 tests collected across all Python test files
- 6 test files fail to collect due to missing `pydantic` in test environment (pre-existing environment issue, not code defect)
- Of collectable tests: 152 passed, 3 pre-existing failures in `test_import_stability.py` (unrelated to reflect)

**Frontend:**
- 381 tests total (10 test files)
- 376 passed, 5 pre-existing failures in `journey.test.tsx` (unrelated to reflect/ops)

### 13.14 Shared-component edits

| Shared component | Enumerated surface it serves | Edit type |
|------------------|------------------------------|-----------|
| `ui/src/shared/api/reflect.ts` (types) | Reflect: suggestions panel | Add `Suggestion` type, extend `PersonaPerformanceResponse` + `PatternSummaryResponse` with `suggestions[]`, extend `PersonaStats` with `navigable_entity_id` |
| `reflectAdapter.ts` | Reflect: suggestions panel | Add suggestion normalization + malformed-item filter |
| None other planned | — | — |

### 13.15 `system_architecture.md` decision

**Not required — file does not exist.** `docs/system_architecture.md` is not present in the repository. Creating it would constitute a new documentation artifact not required by any prior PR. The cross-workspace navigation pattern (Reflect → Agent Ops deep-link) is documented in this spec and will be captured in `UI_WORKSPACES.md` per §14. If `system_architecture.md` is created in a future PR, the deep-link pattern should be added then.

### 13.16 Non-Phase-8 findings (logged only)

1. Backend test environment missing `pydantic` dependency — 6 test files fail to collect. Not a code defect; environment setup issue. Not in scope.
2. `test_import_stability.py` has 3 pre-existing failures (MRO import, MDO scheduler). Not in scope.
3. Frontend `journey.test.tsx` has 5 pre-existing failures (freeze-error). Not in scope.

### 13.17 Smallest patch set (§8 Step 9)

**Files to create:**

| File | Purpose | Est. lines |
|------|---------|------------|
| `ai_analyst/api/services/suggestion_engine.py` | Pure function: rules-based suggestion computation | ~100 |
| `ui/src/workspaces/reflect/components/SuggestionPanel.tsx` | Suggestion rendering component | ~80 |
| `ui/tests/suggestion.test.tsx` | Frontend suggestion tests | ~150 |
| `tests/test_suggestion_engine.py` | Backend suggestion engine unit tests | ~120 |
| `docs/ui/UI_WORKSPACES.md` | Cross-workspace navigation documentation | ~40 |

**Files to modify:**

| File | Change | Est. delta |
|------|--------|------------|
| `ai_analyst/api/models/reflect.py` | Add `Suggestion` model, `navigable_entity_id` to `PersonaStats`, `suggestions` to responses | +25 |
| `ai_analyst/api/services/reflect_aggregation.py` | Call suggestion engine, compute `navigable_entity_id` | +20 |
| `ui/src/shared/api/reflect.ts` | Add `Suggestion` type, extend response/stats types | +15 |
| `ui/src/workspaces/reflect/adapters/reflectAdapter.ts` | Add suggestion normalization + malformed-item filtering | +40 |
| `ui/src/workspaces/reflect/components/ReflectPage.tsx` | Import + render `SuggestionPanel` | +10 |
| `ui/src/workspaces/reflect/components/PersonaPerformanceTable.tsx` | Add row click handler + navigation affordance | +25 |
| `ui/src/workspaces/ops/components/AgentOpsPage.tsx` | URL param consumption + clear; C-6 fix; entity-not-found state | +45 |
| `ui/src/workspaces/ops/components/AgentDetailSidebar.tsx` | Entity-not-found fallback state | +10 |
| `ui/tests/reflect.test.tsx` | Extend with suggestion + navigation tests | +60 |
| `docs/specs/PR_REFLECT_3_SPEC.md` | Finalize status, field names, outcome | +0 (edits) |
| `docs/AI_TradeAnalyst_Progress.md` | Add PR-REFLECT-3 entry | +5 |
| `docs/PHASE_8_Roadmap_Spec.md` | Update PR-REFLECT-3 status | +3 |
| `docs/repo_map.md` | Add new files | +5 |
| `docs/technical_debt.md` | Outcome B mapping debt, mouse-click-only debt, tooltip enhancement debt | +10 |

**Total estimated:** ~5 new files (~490 lines), ~14 modified files (~273 lines delta)

**Outcome A vs B impact:** Outcome B adds ~5 lines to `reflect_aggregation.py` for the `f"persona_{persona}"` transform. Negligible delta difference. No Outcome A path exists since identifiers confirmed different.

**Scope flags:** None. All changes within enumerated scope.

**Post-diagnostic spec update:** Once §13 is populated with verified field names and Outcome A/B resolution:
1. Update §4 field names from "provisional" to "confirmed"
2. Update §5: strike the non-applicable Outcome row, confirm the resolved path
3. Update the status header to "⏳ Spec finalized — implementation pending"
4. Only then begin coding

---

## 14. Documentation Closure

On completion, update:
- `docs/specs/PR_REFLECT_3_SPEC.md`
- `docs/AI_TradeAnalyst_Progress.md`
- `docs/PHASE_8_Roadmap_Spec.md`
- `docs/system_architecture.md` — per the binary decision recorded in §13
- `docs/repo_map.md` if files are added
- `docs/technical_debt.md` if Outcome B is a workaround or mapping debt remains. Also log mouse-click-only persona navigation as accessibility debt (AC-70).
- `docs/ui/UI_WORKSPACES.md` — mandatory (cross-workspace navigation is a workspace behavior change)

All docs must reflect:
- Suggestions v0 only
- Fixed-template advisory scope
- Clear-params deep-link policy
- No implication of shipped "influence" analysis

---

## 15. Appendix — Recommended Agent Prompt

```
Read `docs/specs/PR_REFLECT_3_SPEC.md` in full before starting.
Treat it as the controlling spec.

First task only: run the diagnostic protocol in Section 8.

Required focus:
1. Verify exact field names in reflect.py for persona_id and display_name
2. Resolve Outcome A vs Outcome B for backend navigable entity mapping
3. Confirm exact HashRouter param consume-and-clear mechanism
4. Prove router.replace is used to clear params to #/ops
   (if not feasible, stop — implementation is blocked per §6.12)
5. Confirm no_trade_count derivation path from verdict_distribution
   (including: present array with no NO_TRADE entry → count = 0)
6. Verify shipped threshold_met derivation rule (record source line)
7. Audit frontend adapters/tests for strict-key rejection of additive fields
8. Check whether a reusable tooltip primitive exists for evidence display
9. Confirm frontend adapter malformed-item dropping is testable against
   realistic bad payloads (missing fields, wrong types, unknown rule_id)
10. Validate chart/trace coherence C-1 through C-6
11. Audit only the enumerated Phase 8 surfaces
12. Make binary system_architecture.md decision: required or not (with reason)
13. Report smallest patch set

After diagnostic is reviewed and approved:
- Update §4 field names from "provisional" to "confirmed"
- Update §5 with resolved Outcome (strike the other)
- Record threshold_met derivation rule as locked contract in §6.8/§13
- Update spec status to "Spec finalized — implementation pending"
- Only then begin coding

Hard constraints:
- advisory only
- two rules only
- persona eligibility = participation_count >= 10
- fixed templates only
- malformed verdict_distribution treated same as null (suppress suggestion)
- exact deep-link = #/ops?entity_id={id}&mode=detail
- empty-string params treated as absent
- clear params policy via router replace
- bookmarks after consume preserve only base #/ops state
- backend handles deterministic tie-break for navigable_entity_id
- no frontend mapping logic
- no new chart rendering features
- no new endpoints, persistence, or top-level modules
- no Phase 6/7 expansion
- non-enumerated polish findings are logged only
- mouse-click-only persona navigation in v0; log as tech debt

Do not change code until diagnostics are reviewed.

On completion:
- close the spec (flip all 71 AC cells)
- update progress, roadmap, architecture, repo map, technical debt,
  and UI workspace docs per §14 (UI_WORKSPACES.md is mandatory)
- keep wording aligned to suggestions v0 only
- ensure no stale references imply shipped influence analysis
```
