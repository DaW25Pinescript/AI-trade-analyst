# AI Trade Analyst — Audit Tranche 2: Projection Core Module

**Status:** ⏳ Spec drafted — implementation pending
**Date:** 28 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Review level:** Standard
**Justification for Standard review:** Backend-only refactor within a single package (`ai_analyst/api/services/`). No cross-layer contract changes, no frontend. One bounded behavior correction: centralizing `persona_to_roster_id` fixes detail's blind-prefix bug for non-persona roster IDs — this is intentional, diagnostically verified, and tightly contained to cases where a bare artifact name is already a valid roster ID. All other changes are structural — extracting public APIs from existing working code. Tests cover the primary correctness properties; the diagnostic protocol includes before/after output comparison to guard the behavior correction boundary.

---

## 1. Purpose

- **After:** Audit Tranche 1 complete (contract alignment repair, 21 ACs, 509 backend tests)
- **Question this phase answers:** Can the private roster constant coupling between trace/detail projection services and the roster service be eliminated so that each service depends only on public read APIs?
- **FROM:** `ops_trace.py` and `ops_detail.py` both import `_GOVERNANCE_LAYER`, `_OFFICER_LAYER`, `_DEPARTMENTS`, `_RELATIONSHIPS` (underscore-prefixed private constants) directly from `ops_roster.py`. Both have their own `_persona_to_roster_id()` implementations with divergent behavior. Both build their own entity lookup mechanisms. Internal roster refactors can silently break trace/detail.
- **TO:** `ops_roster.py` exposes three new public read APIs. Trace and detail consume only public APIs. Persona-to-roster-ID mapping is centralized in one function with invariant tests. No private constant is imported outside `ops_roster.py`.

---

## 2. Scope

### In scope

- Add three public read functions to `ops_roster.py`: `get_entity_lookup()`, `get_relationships()`, `persona_to_roster_id()`
- Remove `_get_roster_lookup()` and `_persona_to_roster_id()` from `ops_trace.py` — replace with calls to new public roster APIs
- Remove `_get_roster_entity()`, `_build_dependencies()` direct `_RELATIONSHIPS` access, and `_persona_to_roster_id()` from `ops_detail.py` — replace with calls to new public roster APIs
- Remove all private constant imports (`_GOVERNANCE_LAYER`, `_OFFICER_LAYER`, `_DEPARTMENTS`, `_RELATIONSHIPS`) from trace and detail services
- Add tests for the new public roster APIs (invariant tests for `persona_to_roster_id`, entity lookup completeness, relationships exposure)
- Update existing detail tests that import `_build_dependencies` directly

### Out of scope (hard list)

- No changes to the private constants themselves — `_GOVERNANCE_LAYER`, `_OFFICER_LAYER`, `_DEPARTMENTS`, `_RELATIONSHIPS` remain as the internal data store inside `ops_roster.py`
- No changes to `ops_health.py` — it already uses only `get_all_roster_ids()` (public)
- No changes to reflect, suggestion, run browser, or market data services — they don't import roster internals
- No frontend changes
- No contract doc changes
- No observability trust fixes (Findings 4, 5, 6) — Tranche 3
- No resilience / scale work (Findings 9, 10, 11) — Tranche 4
- No changes to roster data shape, entity definitions, or relationship definitions
- No SQLite or database layer introduced
- No new top-level module

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|-----------|
| Roster service | `ops_roster.py` is the single module that owns entity definitions. Private constants are the internal data store — they stay private, but callers must use public APIs |
| Trace coupling | `ops_trace.py` lazy-imports `_GOVERNANCE_LAYER`, `_OFFICER_LAYER`, `_DEPARTMENTS` inside `_get_roster_lookup()` (deferred import, not module-level). Has its own `_persona_to_roster_id()` that checks existing roster ID then tries `persona_` prefix |
| Detail coupling | `ops_detail.py` imports `_GOVERNANCE_LAYER`, `_OFFICER_LAYER`, `_DEPARTMENTS`, `_RELATIONSHIPS` at module level. Has its own `_get_roster_entity()`, `_build_dependencies()`, and `_persona_to_roster_id()` that blindly prefixes `persona_` |
| Behavior divergence | The two `_persona_to_roster_id` implementations differ: trace checks if `bare_name` is already a roster ID before prefixing; detail always prefixes. The centralized version must use trace's richer logic |
| Test surface | `test_ops_detail_endpoints.py` imports `_build_dependencies` directly as a test target. This import must be updated when the function moves/changes |
| Health service | `ops_health.py` uses only `get_all_roster_ids()` — already clean, no changes needed |

### Current likely state

The coupling has existed since PR-OPS-4a/4b (14-15 March 2026). It has not caused a runtime bug because the roster constants have not changed since initial definition. The risk is latent — it materializes when roster definitions evolve (e.g., adding a new persona, restructuring departments). The duplicate `_persona_to_roster_id` implementations are a live behavior difference: a bare name that's already a valid roster ID would be handled differently by trace (passed through) vs detail (blindly re-prefixed as `persona_persona_...`).

---

## 4. Key File Paths

| Role | Path | Change type |
|------|------|-------------|
| Roster service (API additions) | `ai_analyst/api/services/ops_roster.py` | Add 3 public functions |
| Trace service (consumer update) | `ai_analyst/api/services/ops_trace.py` | Remove private imports + local functions, use public APIs |
| Detail service (consumer update) | `ai_analyst/api/services/ops_detail.py` | Remove private imports + local functions, use public APIs |
| Roster/health tests | `tests/test_ops_endpoints.py` | Add tests for new public APIs |
| Trace tests | `tests/test_ops_trace_endpoints.py` | Verify no regression |
| Detail tests | `tests/test_ops_detail_endpoints.py` | Update `_build_dependencies` import, verify no regression |

---

## 5. Current State Audit Hypothesis

### What is already true
- Roster service defines all entity constants and exposes `get_all_roster_ids()` and `project_roster()` as public APIs
- Trace service works correctly — its `_get_roster_lookup()` and `_persona_to_roster_id()` produce correct results
- Detail service works correctly — its `_get_roster_entity()`, `_build_dependencies()`, and `_persona_to_roster_id()` produce correct results
- 509 backend tests pass (3 pre-existing failures in `test_import_stability.py`)

### What likely remains incomplete
- No public API exists for individual entity lookup, relationships, or persona mapping
- Private constant imports create invisible coupling — no test catches "imported private changed"
- The two `_persona_to_roster_id` implementations have divergent behavior that could produce different results for edge-case inputs
- `test_ops_detail_endpoints.py` imports `_build_dependencies` directly — will need updating

### Core phase question
"Can we replace private constant imports with public read APIs without changing any observable behavior of trace/detail projection?"

---

## 6. Design — New Public Roster APIs

### 6.1 `get_entity_lookup() -> dict[str, AgentSummary]`

Returns all roster entities keyed by entity ID. This replaces:
- Trace's `_get_roster_lookup()` (which builds `{id: {display_name, type, department}}`)
- Detail's `_get_roster_entity()` (which iterates all layers to find one entity)

```python
def get_entity_lookup() -> dict[str, AgentSummary]:
    """Return all roster entities keyed by entity ID.
    
    Callers use this for bulk lookups (trace projection) or single-entity
    lookups (detail projection). The dict is rebuilt on each call — 
    callers may cache locally if performance matters.
    """
    lookup: dict[str, AgentSummary] = {}
    for agent in _GOVERNANCE_LAYER:
        lookup[agent.id] = agent
    for agent in _OFFICER_LAYER:
        lookup[agent.id] = agent
    for agents in _DEPARTMENTS.values():
        for agent in agents:
            lookup[agent.id] = agent
    return lookup
```

**Trace consumption change:**
```python
# Before (in ops_trace.py):
roster = _get_roster_lookup()  # returns {id: {display_name, type, department}}
info = roster.get(entity_id, {})
info.get("display_name", ...)
info.get("type", ...)

# After:
from ai_analyst.api.services.ops_roster import get_entity_lookup
roster = get_entity_lookup()  # returns {id: AgentSummary}
agent = roster.get(entity_id)
agent.display_name if agent else ...
agent.type if agent else ...
```

**Detail consumption change:**
```python
# Before (in ops_detail.py):
agent = _get_roster_entity(entity_id)  # iterates all layers

# After:
from ai_analyst.api.services.ops_roster import get_entity_lookup
roster = get_entity_lookup()
agent = roster.get(entity_id)
```

### 6.2 `get_relationships() -> list[EntityRelationship]`

Exposes the relationships list through a public API. This replaces detail's direct `_RELATIONSHIPS` access.

```python
def get_relationships() -> list[EntityRelationship]:
    """Return all roster entity relationships.
    
    Returns a copy to prevent callers from mutating the internal list.
    """
    return list(_RELATIONSHIPS)
```

**Detail consumption change:**
```python
# Before (in ops_detail.py _build_dependencies):
for rel in _RELATIONSHIPS:
    ...

# After:
from ai_analyst.api.services.ops_roster import get_relationships
for rel in get_relationships():
    ...
```

### 6.3 `persona_to_roster_id(bare_name: str) -> str`

Centralized persona name → roster ID mapping. Uses trace's richer logic (check if already a roster ID, then try prefix). This replaces both services' `_persona_to_roster_id()`.

`persona_to_roster_id()` belongs in `ops_roster.py` because it resolves external artifact identity into canonical roster IDs using roster-owned entity membership; it is not trace-specific or detail-specific logic. The function depends on `get_all_roster_ids()` — a roster primitive — making roster the natural owner.

```python
def persona_to_roster_id(bare_name: str) -> str:
    """Map a bare persona name from run artifacts to roster entity ID.
    
    e.g. "default_analyst" → "persona_default_analyst"
    
    If bare_name is already a valid roster ID, returns it unchanged.
    If persona_{bare_name} is a valid roster ID, returns the prefixed form.
    Otherwise returns bare_name as-is (caller handles unknown IDs).
    """
    roster_ids = get_all_roster_ids()
    if bare_name in roster_ids:
        return bare_name
    prefixed = f"persona_{bare_name}"
    if prefixed in roster_ids:
        return prefixed
    return bare_name
```

**Behavior alignment note:** Detail's current `_persona_to_roster_id` blindly prefixes — it would turn `"arbiter"` into `"persona_arbiter"` (wrong). The centralized version correctly returns `"arbiter"` unchanged because it's already a valid roster ID. This is a **behavior correction**, not just a refactor.

**Correction boundary (locked):** The correction only affects cases where a bare artifact name is already a valid roster ID (non-persona entities: arbiter, officers, subsystems). For actual persona names like `"default_analyst"`, both implementations produce the same result (`"persona_default_analyst"`). The correction surface is therefore limited to non-persona roster IDs passed through detail's `_persona_to_roster_id`. The diagnostic must verify: (a) which non-persona IDs would diverge, (b) whether any existing detail test relies on the blind-prefix behavior for these cases.

### 6.4 Impact on trace's global cache

Trace currently caches the roster lookup in a module-level global `_ROSTER_LOOKUP` with lazy initialization. After the refactor, trace will call `get_entity_lookup()` which rebuilds the dict on each call.

Two options:
- **Option A:** Trace keeps a local cache (same pattern, just calls public API instead of private constants)
- **Option B:** `get_entity_lookup()` itself caches internally

**Recommendation: Option A** — trace caches locally, roster stays stateless. This keeps the roster API simple and predictable. The lookup is small (12 entities) and projection calls are infrequent, so the performance difference is negligible.

### 6.5 Impact on detail's `_build_dependencies`

After the refactor, `_build_dependencies` will use `get_relationships()` and `get_entity_lookup()` instead of direct `_RELATIONSHIPS` and `_get_roster_entity()` access. The function stays in `ops_detail.py` — it computes a detail-specific derived view, not a roster primitive.

The test import `from ai_analyst.api.services.ops_detail import _build_dependencies` remains valid — the function still exists, it just calls public roster APIs internally.

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | Public API: entity lookup | `get_entity_lookup()` returns a dict keyed by entity ID with all roster entities as `AgentSummary` objects. Dict has exactly `len(get_all_roster_ids())` entries | ⏳ Pending |
| AC-2 | Public API: relationships | `get_relationships()` returns all relationships from the roster. Result is a copy (mutation-safe) | ⏳ Pending |
| AC-3 | Public API: persona mapping | `persona_to_roster_id("default_analyst")` returns `"persona_default_analyst"`. `persona_to_roster_id("arbiter")` returns `"arbiter"` (already valid). `persona_to_roster_id("unknown_xyz")` returns `"unknown_xyz"` (passthrough) | ⏳ Pending |
| AC-4 | Negative: no private imports in trace | `ops_trace.py` does NOT import `_GOVERNANCE_LAYER`, `_OFFICER_LAYER`, `_DEPARTMENTS`, or `_RELATIONSHIPS` from any module | ⏳ Pending |
| AC-5 | Negative: no private imports in detail | `ops_detail.py` does NOT import `_GOVERNANCE_LAYER`, `_OFFICER_LAYER`, `_DEPARTMENTS`, or `_RELATIONSHIPS` from any module | ⏳ Pending |
| AC-6 | Negative: no local persona mapping | Neither `ops_trace.py` nor `ops_detail.py` defines its own `_persona_to_roster_id` function | ⏳ Pending |
| AC-7 | Negative: no local entity lookup | `ops_trace.py` does not define `_get_roster_lookup`. `ops_detail.py` does not define `_get_roster_entity` | ⏳ Pending |
| AC-8 | Trace regression | All existing trace tests pass. `project_trace()` output is contract-equivalent for the same fixture inputs (same field values, same ordering where contract-relevant, no contract-visible regressions) | ⏳ Pending |
| AC-9 | Detail regression | All existing detail tests pass. `project_detail()` output is contract-equivalent for the same entity IDs, except where the centralized persona mapping intentionally corrects blind-prefix behavior for non-persona roster IDs (e.g., `"arbiter"` no longer becomes `"persona_arbiter"`). Diagnostics must confirm this correction and prove no existing test relies on the blind-prefix behavior | ⏳ Pending |
| AC-10 | Health unaffected | `ops_health.py` imports unchanged. All health tests pass | ⏳ Pending |
| AC-11 | Persona mapping invariants | Invariant tests cover: already-valid roster ID passthrough, bare persona name → prefixed, unknown name passthrough, all known persona names map correctly | ⏳ Pending |
| AC-12 | Entity lookup completeness | Test asserts `set(get_entity_lookup().keys()) == get_all_roster_ids()` | ⏳ Pending |
| AC-13 | Relationships copy safety | Test asserts `get_relationships() is not get_relationships()` (different list object) and `len(get_relationships()) == len(expected)` | ⏳ Pending |
| AC-14 | Backend test count | 509+ passed (diagnostic baseline), zero new failures from this tranche | ⏳ Pending |
| AC-15 | No frontend changes | Zero changes to any file under `ui/` | ⏳ Pending |

---

## 8. Pre-Code Diagnostic Protocol

**Do not implement until this list is reviewed.**

### Step 1: Confirm private constant imports

```bash
cd "C:\Users\david\OneDrive\Documents\GitHub\AI trade analyst"
grep -rn "_GOVERNANCE_LAYER\|_OFFICER_LAYER\|_DEPARTMENTS\|_RELATIONSHIPS" ai_analyst/api/services/ --include="*.py" | grep -v "^ai_analyst/api/services/ops_roster.py"
```

**Expected:** Hits in `ops_trace.py` and `ops_detail.py` only. No other service file.

**Report:** Full list. Any unexpected file must be added to the change surface.

### Step 2: Confirm `_persona_to_roster_id` implementations

```bash
grep -rn "def _persona_to_roster_id\|def persona_to_roster_id" ai_analyst/api/services/ --include="*.py"
```

**Expected:** Two implementations — one in `ops_trace.py`, one in `ops_detail.py`. Zero in `ops_roster.py` (the new one doesn't exist yet).

**Report:** Line numbers. Confirm behavioral difference: trace checks existing roster ID first; detail blindly prefixes.

### Step 3: Confirm test imports of private helpers

```bash
grep -rn "_build_dependencies\|_get_roster_entity\|_get_roster_lookup\|_persona_to_roster_id" tests/ --include="*.py"
```

**Expected:** `test_ops_detail_endpoints.py` imports `_build_dependencies`. Possibly other private helpers.

**Report:** Full list of test files importing private helpers that will be affected.

### Step 4: Run baseline test suite

```bash
python -m pytest tests/ -x --tb=short -q 2>&1 | tail -5
```

**Expected:** 509 passed, 3 failed (pre-existing).

**Report:** Exact counts. Any deviation from Tranche 1 completion baseline is a blocker.

### Step 5: Verify roster entity count

```bash
python -c "
from ai_analyst.api.services.ops_roster import get_all_roster_ids
ids = get_all_roster_ids()
print(f'Roster entities: {len(ids)}')
for eid in sorted(ids):
    print(f'  {eid}')
"
```

**Expected:** 12 entities (2 governance + 2 officer + 3 tech analysis + 3 risk challenge + 1 review governance + 2 infra health — adjusted from diagnostic if different).

**Report:** Entity count and full ID list. The new `get_entity_lookup()` must return exactly this set.

### Step 6: Test the behavioral difference in persona mapping

```bash
python -c "
# Simulate detail's blind-prefix behavior
def detail_map(bare): return f'persona_{bare}'

# Simulate trace's check-first behavior  
from ai_analyst.api.services.ops_roster import get_all_roster_ids
roster_ids = get_all_roster_ids()
def trace_map(bare):
    if bare in roster_ids: return bare
    prefixed = f'persona_{bare}'
    if prefixed in roster_ids: return prefixed
    return bare

# Test cases that differ
test_cases = ['arbiter', 'market_data_officer', 'governance_synthesis', 'mdo_scheduler', 'feeder_ingest']
for tc in test_cases:
    d = detail_map(tc)
    t = trace_map(tc)
    diff = '*** DIFFERS ***' if d != t else ''
    print(f'{tc}: detail={d}, trace={t} {diff}')
"
```

**Expected:** Divergence for non-persona roster IDs (arbiter, officers, subsystems). The centralized version must use trace's behavior.

**Report:** Full diff table. Confirm no existing detail test relies on blind-prefix behavior for these cases.

### Step 7: Report smallest patch set

**Report:** Files, one-line description, estimated line delta per file.

---

## 9. Implementation Constraints

### 9.1 General rule

This is a structural refactor, not a behavior change. The observable output of `project_trace()` and `project_detail()` must not change for any input. The only behavioral correction is `persona_to_roster_id` — detail's blind-prefix behavior is a latent bug that this tranche fixes by adopting trace's richer logic. The diagnostic must confirm no existing test relies on the blind-prefix behavior.

### 9.1b Implementation Sequence

1. **Add public APIs to `ops_roster.py`** — `get_entity_lookup()`, `get_relationships()`, `persona_to_roster_id()`. Add tests to `test_ops_endpoints.py`. Run backend tests.
   - Gate: 509+ passed, new API tests green

2. **Update `ops_trace.py`** — remove `_ROSTER_LOOKUP` global, `_get_roster_lookup()`, `_persona_to_roster_id()`. Replace with calls to `get_entity_lookup()` and `persona_to_roster_id()`. Keep a local cache for the entity lookup within `project_trace()`. Remove private constant imports.
   - Gate: `grep -c "_GOVERNANCE_LAYER\|_OFFICER_LAYER\|_DEPARTMENTS" ai_analyst/api/services/ops_trace.py` returns 0. All trace tests pass.

3. **Update `ops_detail.py`** — remove `_get_roster_entity()`, `_persona_to_roster_id()`. Update `_build_dependencies()` to use `get_relationships()` + `get_entity_lookup()`. Remove private constant imports. Update test file if `_build_dependencies` import path changed.
   - Gate: `grep -c "_GOVERNANCE_LAYER\|_OFFICER_LAYER\|_DEPARTMENTS\|_RELATIONSHIPS" ai_analyst/api/services/ops_detail.py` returns 0. All detail tests pass.

4. **Full regression** — run complete backend test suite.
   - Gate: 509+ passed (adjusted for new tests), 3 failed (pre-existing), zero new failures

### 9.2 Code change surface

| File | Role |
|------|------|
| `ai_analyst/api/services/ops_roster.py` | Add 3 public functions — PRIMARY CHANGE |
| `ai_analyst/api/services/ops_trace.py` | Remove private imports + local helpers, use public APIs |
| `ai_analyst/api/services/ops_detail.py` | Remove private imports + local helpers, use public APIs |
| `tests/test_ops_endpoints.py` | Add tests for new public APIs |
| `tests/test_ops_detail_endpoints.py` | Update if `_build_dependencies` import changes |

**No changes expected to:**
- `ai_analyst/api/services/ops_health.py` (already clean)
- `ai_analyst/api/services/reflect_aggregation.py` (no roster imports)
- `ai_analyst/api/services/suggestion_engine.py` (no roster imports)
- `ai_analyst/api/services/ops_run_browser.py` (no roster imports)
- `ai_analyst/api/services/market_data_read.py` (no roster imports)
- `ai_analyst/api/models/` (model definitions unchanged)
- `ui/` (frontend unchanged)
- `docs/` (no contract changes)

**If any of the above require changes, flag before proceeding.**

### 9.3 Out of scope (repeat)

- No private constant changes (they stay private inside roster)
- No roster data shape changes
- No frontend changes
- No contract doc changes
- No observability trust fixes
- No SQLite, no new top-level module

---

## 10. Success Definition

Tranche 2 is done when: `ops_roster.py` exposes `get_entity_lookup()`, `get_relationships()`, and `persona_to_roster_id()` as public read APIs with invariant tests; neither `ops_trace.py` nor `ops_detail.py` imports any private constant (`_GOVERNANCE_LAYER`, `_OFFICER_LAYER`, `_DEPARTMENTS`, `_RELATIONSHIPS`) from any module; neither service defines its own `_persona_to_roster_id`; all 509+ backend tests pass with zero new failures; and zero frontend or contract doc changes have been made.

---

## 11. Why This Phase Matters

| Without | With |
|---------|------|
| Roster internal refactor silently breaks trace + detail | Trace and detail depend only on stable public APIs |
| Two `_persona_to_roster_id` implementations with divergent behavior | One centralized function with invariant tests |
| Every consumer builds its own entity lookup by iterating private lists | One public lookup function, consumed uniformly |
| `_RELATIONSHIPS` accessed directly — no encapsulation | Public `get_relationships()` returns a copy — mutation-safe |
| Adding a persona requires checking two services for hardcoded assumptions | Public APIs abstract the underlying data structure |
| Tranche 3 (trust fixes) would need to navigate the same coupling | Tranche 3 starts from clean module boundaries |

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 8 (PR-REFLECT-3) | Suggestions v0, cross-workspace nav, coherence | ✅ Done |
| Audit Tranche 1 | Contract alignment repair (Findings 1, 2, 3) | ✅ Done — 21 ACs |
| Audit Tranche 2 | Projection core module (Findings 7, 8) | ⏳ Spec drafted — implementation pending |
| Audit Tranche 3 | Trust integrity (Findings 4, 5, 6) | 💭 Planned — spec after T2 closes |
| Audit Tranche 4 / Backlog | Resilience + test infra (Findings 9–12) | 💭 Backlog |
| Phase 9 candidates | Filter controls, Chart Indicators, ML Pattern Detection | 💭 Concept — after audit tranches |

---

## 13. Diagnostic Findings

*To be populated after running the pre-code diagnostic protocol (Section 8).*

---

## 14. Appendix — Recommended Agent Prompt

```
# REPO: C:/Users/david/OneDrive/Documents/GitHub/AI trade analyst

Read `docs/specs/PR_AUDIT_T2_PROJECTION_CORE_SPEC.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 8 and report findings
before changing any code:

1. Confirm private constant imports — which files, which constants
2. Confirm _persona_to_roster_id implementations — count and behavioral differences
3. Confirm test imports of private helpers — which test files import what
4. Run baseline backend test suite — report exact counts
5. Verify roster entity count and full ID list
6. Test behavioral difference in persona mapping — divergence table
7. Propose smallest patch set: files, one-line description, estimated line delta

Hard constraints:
- Observable output of project_trace() and project_detail() must not change for any existing fixture inputs (except the persona mapping behavior correction)
- Private constants stay private inside ops_roster.py — do not expose, rename, or restructure them
- The centralized persona_to_roster_id must use trace's richer logic (check existing ID, then prefix) — not detail's blind-prefix behavior
- No frontend changes, no contract doc changes
- No SQLite, no new top-level module
- Deterministic tests only — no live provider dependency in CI

Do not change any code until the diagnostic report is reviewed and the
patch set is approved.

On completion, close the spec and update docs per Workflow E:
1. `docs/specs/PR_AUDIT_T2_PROJECTION_CORE_SPEC.md` — mark ✅ Complete, flip all AC cells,
   populate §13 Diagnostic Findings with: private import list, persona mapping divergence table,
   entity count, test import list, any surprises
2. `docs/AI_TradeAnalyst_Progress.md` — dashboard-aware update per Workflow E.2:
   update header (current phase), add Recent Activity row for Audit T2,
   update Phase Status Overview, update Phase Index, add test count row,
   update Roadmap, update debt register if applicable
3. Cross-document sanity check: no contradictions, no stale phase refs
4. Return Phase Completion Report

Commit all doc changes on the same branch as the implementation.
```
