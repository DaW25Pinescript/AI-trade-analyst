# AI Trade Analyst — Audit Tranche 3: Trust Integrity

**Status:** ✅ Complete — implemented 28 March 2026
**Date:** 28 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Review level:** Full
**Justification for Full review:** This tranche changes operator-visible semantics across health and trace surfaces. The changes affect what the operator *believes* about system state — not just what data renders, but what trust level that data implies. "Passes tests but misleads the operator" is a realistic failure mode. Full review is mandatory for any change where the difference between correct and incorrect is a semantic judgment about evidence provenance, not a structural assertion about field names.

---

## Governing Rule

**Do not claim more than the artifacts prove.**

This rule drives all three findings in this tranche:
- Override attribution must be evidence-grounded or clearly labeled heuristic (Finding 4)
- Governance health must distinguish runtime evidence from proxy-derived inference (Finding 5)
- Projection quality must let the operator tell "fresh and complete" from "fresh but partial / inferred / degraded" (Finding 6)

Every field added, every label changed, and every semantic decision in this spec is tested against this rule. If a projection cannot prove its claim from source artifacts, it must say so.

---

## 1. Purpose

- **After:** Audit Tranche 2 complete (projection core module, 15 ACs, 523 backend tests). Module boundaries are clean — trace and detail consume public roster APIs only.
- **Question this phase answers:** Can the health and trace operator trust surfaces be made honest about evidence provenance so that operators can distinguish proven facts from inferred claims? (Detail surface is not changed in this tranche — it consumes health and trace data downstream, so trust metadata added here will be available to detail consumers in future work.)
- **FROM:** Health marks governance entities as `"live"` based on proxy signals. Override attribution is a heuristic presented as fact. `data_state` conflates freshness with completeness — operators cannot distinguish "fresh and complete" from "fresh but partially inferred."
- **TO:** Every projected claim carries its evidence basis. Health entities are tagged with how their health was determined. Override attribution is labeled as heuristic. Trace responses expose projection quality metadata so operators can assess fidelity.

---

## 2. Scope

### In scope

**Finding 4 — Override attribution honesty:**
- Add `evidence_class` field to `ParticipantContribution` model: `"artifact" | "heuristic" | "default"`
- Tag the current override detection logic as `evidence_class: "heuristic"` in trace projection
- When no override assessment is possible (no audit log), tag as `evidence_class: "default"`
- Add `evidence_class` to frontend `ParticipantContribution` type (additive, no rendering change)
- Update contract doc §6.7 to include `evidence_class`

**Finding 5 — Health evidence provenance:**
- Add `evidence_basis` field to `AgentHealthItem` model: `"runtime_event" | "derived_proxy" | "none"`
- Tag each health item with how its health_state was determined:
  - `feeder_ingest`, `mdo_scheduler`: `"runtime_event"` (derived from actual feeder bridge state)
  - `market_data_officer`, `macro_risk_officer`: `"derived_proxy"` (mirrors subsystem health)
  - `arbiter`, `governance_synthesis` (when feeder_context exists): `"derived_proxy"` (inferred from context presence)
  - Default entities (no observability evidence): `"none"`
- `health_state` values remain unchanged — no downgrading from `"live"` to `"degraded"`
- Add `evidence_basis` to frontend `AgentHealthItem` type (additive, no rendering change)
- Update contract doc §5.5 to include `evidence_basis`

**Finding 6 — Projection quality metadata:**
- Add `projection_quality` field to trace `AgentTraceResponse`: `"partial" | "heuristic"` (v1 contract — `"full"` is reserved for future pipeline work and not emitted in this version)
- Add `missing_fields` list to trace `AgentTraceResponse`: string array of field categories that are either **unavailable** (data absent) or **not directly artifact-evidenced** (data present but heuristic-derived). Both cases represent gaps in direct evidence.
- Derivation logic:
  - `"heuristic"`: audit log present but override attribution is heuristic (always true in v1)
  - `"partial"`: audit log absent — stance, confidence, and override data unavailable
  - (`"full"` is reserved for future use when the pipeline produces explicit override metadata — not emitted or tested in v1)
- `missing_fields` examples: `["analyst_stances", "confidence_scores", "override_attribution"]` when audit log absent; `["explicit_override_metadata"]` when audit log present but overrides are heuristic
- Add both fields to frontend `AgentTraceResponse` type (additive, no rendering change)
- Update contract doc §6.4 to include both fields

**Frontend type additions (additive only — no rendering changes):**
- `ParticipantContribution.evidence_class` in `ops.ts`
- `AgentHealthItem.evidence_basis` in `ops.ts`
- `AgentTraceResponse.projection_quality` and `AgentTraceResponse.missing_fields` in `ops.ts`
- Frontend test fixtures updated to include new fields
- No component rendering changes — fields exist in types for future rendering work

### Out of scope (hard list)

- No `health_state` value changes — governance entities keep `"live"` when feeder_context exists. The `evidence_basis` field communicates the provenance; the operator decides what to do with it
- No pipeline changes — override metadata remains heuristic until the analysis pipeline produces explicit per-analyst override records
- No frontend rendering changes — new fields are additive in types only. Rendering is a future UI pass
- No changes to roster, run browser, market data, reflect, or suggestion services
- No resilience / scale work (Findings 9–12) — Tranche 4 / Backlog
- No SQLite or database layer introduced
- No new top-level module; prefer changes to existing service files

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|-----------|
| Health service | `ops_health.py` constructs `AgentHealthItem` objects inline. Adding `evidence_basis` is a field addition to each constructor call — no structural change |
| Health model | `AgentHealthItem` is a Pydantic `BaseModel` in `ops.py`. Adding an optional field with a default does not break existing consumers |
| Trace models | `ParticipantContribution` and `AgentTraceResponse` are Pydantic models in `ops_trace.py`. Adding optional fields with defaults is backward-compatible |
| Trace service | Override attribution logic is in `project_trace()` around line 200. The heuristic is self-contained — tagging it does not require restructuring |
| Frontend types | `ops.ts` was fully aligned in Tranche 1. New fields are additive — existing components will compile without changes because new fields are optional |
| Contract doc | `AGENT_OPS_CONTRACT.md` §5.5 and §6.4/6.7 are the sections to update |
| Test baseline | Backend: 523 passed, 3 failed (pre-existing). Frontend: 389 passed, 17 failed (pre-existing — classification needed in diagnostic) |

### Current likely state

The health service has no concept of evidence provenance — every health item is projected as if equally trustworthy. The trace service applies override heuristics silently — the output looks authoritative even when the attribution is inferred. `data_state` on trace responses distinguishes only "audit log exists" from "audit log absent" — it does not encode whether the trace is fully evidence-grounded or partially heuristic. After T1 and T2, the contract surface and module boundaries are clean — this tranche adds provenance metadata on a stable foundation.

---

## 4. Key File Paths

| Role | Path | Change type |
|------|------|-------------|
| Health model | `ai_analyst/api/models/ops.py` | Add `evidence_basis` to `AgentHealthItem` |
| Trace models | `ai_analyst/api/models/ops_trace.py` | Add `evidence_class` to `ParticipantContribution`, `projection_quality` + `missing_fields` to `AgentTraceResponse` |
| Health service | `ai_analyst/api/services/ops_health.py` | Tag each health item with `evidence_basis` |
| Trace service | `ai_analyst/api/services/ops_trace.py` | Tag override attribution with `evidence_class`, compute `projection_quality` + `missing_fields` |
| Health tests | `tests/test_ops_endpoints.py` | Add tests for `evidence_basis` on health items |
| Trace tests | `tests/test_ops_trace_endpoints.py` | Add tests for `evidence_class`, `projection_quality`, `missing_fields` |
| Frontend types | `ui/src/shared/api/ops.ts` | Add new fields to types (additive) |
| Frontend tests | `ui/tests/ops.test.tsx` | Update fixtures to include new fields |
| Contract doc | `docs/ui/AGENT_OPS_CONTRACT.md` | Update §5.5, §6.4, §6.7 |

---

## 5. Current State Audit Hypothesis

### What is already true
- Health service works correctly for its current scope — entities get appropriate `health_state` values
- Trace service produces honest data for direct-evidence fields (stances from audit log, arbiter verdict from run_record)
- Override heuristic is internally consistent — it just doesn't announce that it's a heuristic
- `data_state` correctly distinguishes "audit log present" from "audit log absent"
- Module boundaries are clean post-T2 — no private coupling to navigate

### What likely remains incomplete
- No evidence provenance on any projected field
- Operator has no way to distinguish runtime evidence from proxy inference on health items
- Override `was_overridden` looks authoritative but is a best-effort heuristic
- `data_state: "live"` on a trace tells you the audit log exists, not whether the trace is fully evidence-grounded

### Core phase question
"Can we add evidence provenance metadata to health and trace projections without changing existing field values or breaking any consuming surface?"

---

## 6. Design — Trust Metadata

### 6.1 `evidence_class` on `ParticipantContribution`

New field on the existing `ParticipantContribution` model.

**Scope:** `evidence_class` refers specifically to the provenance of the **override-assessment subfields** (`was_overridden`, `override_reason`), not to the provenance of `stance`/`confidence`/`summary` generally. When the audit log is present, stance and confidence are artifact-derived, but the override assessment is always heuristic in v1. The field name is kept general (`evidence_class` rather than `override_evidence_class`) to allow future extension to other provenance-tracked subfields without renaming.

```python
class ParticipantContribution(BaseModel):
    # ... existing fields ...
    evidence_class: Literal["artifact", "heuristic", "default"] = "default"
```

**Semantics (applies to override-assessment provenance):**
| Value | Meaning | When used |
|-------|---------|-----------|
| `"artifact"` | Claim is directly evidenced by run artifacts | Future — when pipeline produces explicit override metadata |
| `"heuristic"` | Claim is inferred by a read-side heuristic | Current override detection (risk_override_applied + stance + NO_TRADE) |
| `"default"` | No evidence available — field carries its default value | No audit log, or participant did not reach arbiter |

**Trace service changes:**

Where `was_overridden` is currently set to `True`:
```python
# Current:
was_overridden = True
override_reason = "Risk override applied — ..."

# After:
was_overridden = True
override_reason = "Risk override applied — ..."
evidence_class = "heuristic"
```

Where `was_overridden` remains `False` with audit log present:
```python
evidence_class = "heuristic"  # still heuristic — absence of override is also inferred
```

Where no audit log exists:
```python
evidence_class = "default"  # no evidence to assess
```

**Why `"heuristic"` even when was_overridden=False:** The *absence* of override is also an inference. The heuristic says "if stance is directional and arbiter said NO_TRADE, then overridden." Not meeting that condition doesn't prove the analyst wasn't overridden — it just means the heuristic didn't fire. Until the pipeline produces explicit override records, both the positive and negative assessments are heuristic.

### 6.2 `evidence_basis` on `AgentHealthItem`

New field on the existing `AgentHealthItem` model:

```python
class AgentHealthItem(BaseModel):
    # ... existing fields ...
    evidence_basis: Literal["runtime_event", "derived_proxy", "none"] = "none"
```

**Semantics:**
| Value | Meaning | Entities |
|-------|---------|----------|
| `"runtime_event"` | Health derived from actual runtime signals (feeder ingestion, scheduler execution) | `feeder_ingest` (when feeder data available), `mdo_scheduler` (when scheduler data available). On unavailable branches (no data received), these entities get `"none"` — not `"runtime_event"` — because no runtime signal was observed |
| `"derived_proxy"` | Health mirrored from another entity's evidence or inferred from context presence | `market_data_officer` (mirrors mdo_scheduler), `macro_risk_officer` (mirrors feeder_ingest), `arbiter` (feeder_context exists), `governance_synthesis` (feeder_context exists) |
| `"none"` | No observability evidence available — entity gets default health | All personas, any entity without evidence signals |

**Health service changes:**

Each `AgentHealthItem` constructor call gets `evidence_basis=` added:

```python
# feeder_ingest — direct runtime evidence (when data available)
evidence_items["feeder_ingest"] = AgentHealthItem(
    entity_id="feeder_ingest",
    ...,
    evidence_basis="runtime_event",  # or "none" on unavailable branch
)

# market_data_officer — mirrors mdo_scheduler
evidence_items["market_data_officer"] = AgentHealthItem(
    entity_id="market_data_officer",
    ...,
    health_summary="Mirrors MDO scheduler status",
    evidence_basis="derived_proxy",
)

# arbiter — inferred from feeder_context presence
evidence_items["arbiter"] = AgentHealthItem(
    entity_id="arbiter",
    ...,
    health_summary="Arbiter available with macro context",
    evidence_basis="derived_proxy",
)

# default (no evidence)
def _default_health_item(entity_id: str) -> AgentHealthItem:
    return AgentHealthItem(
        entity_id=entity_id,
        ...,
        evidence_basis="none",
    )
```

### 6.3 `projection_quality` and `missing_fields` on `AgentTraceResponse`

New fields on the existing `AgentTraceResponse` model:

```python
class AgentTraceResponse(ResponseMeta):
    # ... existing fields ...
    projection_quality: Literal["partial", "heuristic"] = "partial"
    missing_fields: list[str] = Field(default_factory=list)
```

**Semantics:**
| Value | Meaning | Condition |
|-------|---------|-----------|
| `"heuristic"` | Audit log present, but override-assessment fields are heuristic-derived | Audit log present (always in v1) |
| `"partial"` | Audit log absent — key enrichment fields unavailable | No audit log |

`"full"` is reserved for future pipeline work (explicit per-analyst override metadata). It is not emitted, not tested, and not included in the v1 enum. It will be added to the contract when the pipeline makes it reachable.

**`missing_fields` vocabulary (locked for v1):**

`missing_fields` lists categories where direct artifact evidence is either absent or not available. This covers both truly missing data and data that is present but only heuristic-derived.

| Field key | Gap type | Meaning | When included |
|-----------|----------|---------|---------------|
| `"analyst_stances"` | Unavailable | Per-analyst stance data absent | Audit log absent |
| `"confidence_scores"` | Unavailable | Per-analyst confidence absent | Audit log absent |
| `"override_attribution"` | Unavailable | Override assessment absent | Audit log absent |
| `"explicit_override_metadata"` | Not artifact-evidenced | Override attribution present but heuristic-derived | Audit log present (always in v1) |

**Trace service changes:**

At the end of `project_trace()`, before constructing the response:

```python
# Compute projection quality
missing: list[str] = []
if not has_audit:
    quality = "partial"
    missing = ["analyst_stances", "confidence_scores", "override_attribution"]
else:
    quality = "heuristic"
    missing = ["explicit_override_metadata"]
# "full" is not reachable in v1 — reserved for when pipeline emits explicit overrides
```

### 6.4 Backward compatibility

All new fields have defaults:
- `evidence_class` defaults to `"default"` — safe for any consumer that doesn't read it
- `evidence_basis` defaults to `"none"` — safe for any consumer that doesn't read it
- `projection_quality` defaults to `"partial"` — conservative default
- `missing_fields` defaults to `[]` — empty list is safe

Existing test fixtures will pass without modification because the defaults are valid. New fixtures must include the new fields explicitly.

### 6.5 Frontend type additions

All additive — no existing field changes, no rendering changes:

```typescript
// ParticipantContribution — add:
evidence_class?: "artifact" | "heuristic" | "default";

// AgentHealthItem — add:
evidence_basis?: "runtime_event" | "derived_proxy" | "none";

// AgentTraceResponse — add:
projection_quality?: "partial" | "heuristic";  // v1 contract — "full" reserved for future
missing_fields?: string[];
```

Fields are optional in frontend types because existing API responses from older backends won't include them. Components that render these fields (future work) must handle `undefined`.

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | Evidence class: heuristic tag | When audit log is present, `ParticipantContribution.evidence_class` is `"heuristic"` for all participants that receive a `ParticipantContribution` object in the serialized response (both overridden and non-overridden). This labels override-assessment provenance, not stance/confidence provenance | ✅ Pass |
| AC-2 | Evidence class: default tag | When audit log is absent, `ParticipantContribution.evidence_class` is `"default"` for all participants that receive a `ParticipantContribution` object in the serialized response | ✅ Pass |
| AC-3 | Evidence class: model field | `evidence_class` field exists on `ParticipantContribution` Pydantic model with correct type and default | ✅ Pass |
| AC-4 | Health: runtime_event | `feeder_ingest` and `mdo_scheduler` health items have `evidence_basis: "runtime_event"` when feeder data is available. When feeder data is unavailable (`feeder_ingested_at is None`), these entities get `evidence_basis: "none"` — the basis describes observed evidence, not entity category | ✅ Pass |
| AC-5 | Health: derived_proxy (officers) | `market_data_officer` and `macro_risk_officer` health items have `evidence_basis: "derived_proxy"` | ✅ Pass |
| AC-6 | Health: derived_proxy (governance) | `arbiter` and `governance_synthesis` health items have `evidence_basis: "derived_proxy"` when feeder_context is present | ✅ Pass |
| AC-7 | Health: none | Default health items (no evidence) have `evidence_basis: "none"` | ✅ Pass |
| AC-8 | Health: model field | `evidence_basis` field exists on `AgentHealthItem` Pydantic model with correct type and default | ✅ Pass |
| AC-9 | Projection quality: heuristic | When audit log is present, `projection_quality` is `"heuristic"` and `missing_fields` contains `"explicit_override_metadata"` | ✅ Pass |
| AC-10 | Projection quality: partial | When audit log is absent, `projection_quality` is `"partial"` and `missing_fields` contains `"analyst_stances"`, `"confidence_scores"`, `"override_attribution"` | ✅ Pass |
| AC-11 | Projection quality: model fields | `projection_quality` and `missing_fields` fields exist on `AgentTraceResponse` Pydantic model with correct types and defaults | ✅ Pass |
| AC-12 | Negative: no health_state changes | No existing `health_state` values change — governance entities remain `"live"` when feeder_context exists. The `evidence_basis` field is additive only | ✅ Pass |
| AC-13 | Negative: no override logic changes | The override detection heuristic is unchanged — `was_overridden` and `override_reason` are computed identically. Only the `evidence_class` tag is added | ✅ Pass |
| AC-14 | Negative: no data_state changes | `data_state` derivation logic is unchanged on both health and trace responses | ✅ Pass |
| AC-15 | Frontend types: additive | `evidence_class`, `evidence_basis`, `projection_quality`, `missing_fields` added to frontend types as optional fields. No existing field changes | ✅ Pass |
| AC-16 | Frontend tests: no regression | Frontend test count ≥ diagnostic baseline. Diagnostic Step 1 must classify all 17 failures by surface; if any are in ops (health/trace/detail) tests, record them as pre-existing in-scope failures and require no worsening. All ops-surface tests that were passing before T3 must remain passing | ✅ Pass |
| AC-17 | Backend tests: no regression | Backend test count ≥ 523 (T2 baseline) + new tests; zero new failures from this tranche | ✅ Pass |
| AC-18 | Contract doc: §5.5 updated | `AgentHealthItem` field table includes `evidence_basis` with type, semantics, and per-entity assignment | ✅ Pass |
| AC-19 | Contract doc: §6.4 + §6.7 updated | `AgentTraceResponse` includes `projection_quality` + `missing_fields`; `ParticipantContribution` includes `evidence_class`. All field definitions, enums, and examples match the backend serialized payload | ✅ Pass |
| AC-20 | Governing rule test | Route-level test that verifies: audit-log-present trace has `evidence_class: "heuristic"` on all participants and `projection_quality: "heuristic"`; audit-log-absent trace has `evidence_class: "default"` and `projection_quality: "partial"` | ✅ Pass |
| AC-21 | No frontend rendering or adapter changes | Zero changes to any component or adapter/view-model file under `ui/src/workspaces/`. Only type definitions and test fixtures updated. If diagnostics prove type sync requires adapter changes, flag before proceeding | ✅ Pass |
| AC-22 | Health provenance route test | Route-level or projection-level test that proves `evidence_basis` appears in serialized health responses with the correct assignment for at least one `runtime_event` entity, one `derived_proxy` entity, and one `none`/default entity | ✅ Pass |

---

## 8. Pre-Code Diagnostic Protocol

**Do not implement until this list is reviewed.**

### Step 1: Classify all 17 frontend test failures by surface

```bash
cd "C:\Users\david\OneDrive\Documents\GitHub\AI trade analyst\ui"
npx vitest run --reporter=verbose 2>&1 | grep -E "FAIL|×|✗" | head -30
```

**Expected:** 17 failures across multiple test files. Classify each by surface: journey, ops (health/trace/detail), reflect, analysis-run, triage, chart, other.

**Report:** Full table: test file | test name | surface. Flag any failures in health, trace, or detail tests — these are the surfaces T3 modifies and must be accounted for in the regression baseline.

### Step 2: Confirm current `AgentHealthItem` model shape

```bash
cd "C:\Users\david\OneDrive\Documents\GitHub\AI trade analyst"
python -c "
from ai_analyst.api.models.ops import AgentHealthItem
import json
print(json.dumps(AgentHealthItem.model_json_schema(), indent=2))
"
```

**Expected:** No `evidence_basis` field present. Confirm adding an optional field with default will be backward-compatible.

**Report:** Current field list. Confirm no existing field named `evidence_basis`.

### Step 3: Confirm current `ParticipantContribution` model shape

```bash
python -c "
from ai_analyst.api.models.ops_trace import ParticipantContribution
import json
print(json.dumps(ParticipantContribution.model_json_schema(), indent=2))
"
```

**Expected:** No `evidence_class` field present.

**Report:** Current field list. Confirm no existing field named `evidence_class`.

### Step 4: Confirm current `AgentTraceResponse` model shape

```bash
python -c "
from ai_analyst.api.models.ops_trace import AgentTraceResponse
import json
schema = AgentTraceResponse.model_json_schema()
top_fields = [k for k in schema.get('properties', {}).keys()]
print('Top-level fields:', top_fields)
"
```

**Expected:** No `projection_quality` or `missing_fields` present.

**Report:** Current top-level field list.

### Step 5: Confirm health service constructor sites

```bash
grep -n "AgentHealthItem(" ai_analyst/api/services/ops_health.py
```

**Expected:** Multiple constructor calls — each needs `evidence_basis=` added.

**Report:** Line numbers and count. Each is one edit site.

### Step 6: Confirm trace override heuristic location

```bash
grep -n "was_overridden\|override_reason\|risk_override_applied" ai_analyst/api/services/ops_trace.py
```

**Expected:** Override heuristic concentrated in one block (~lines 195-210). Each participant builder near there needs `evidence_class=` added.

**Report:** Line numbers. Confirm the heuristic is self-contained.

### Step 7: Run baseline backend test suite

```bash
python -m pytest tests/ -x --tb=short -q 2>&1 | tail -5
```

**Expected:** 523 passed, 3 failed (pre-existing).

**Report:** Exact counts.

### Step 8: Report smallest patch set

**Report:** Files, one-line description, estimated line delta per file.

---

## 9. Implementation Constraints

### 9.1 General rule

**Do not claim more than the artifacts prove.** Every new field must accurately reflect the evidence basis of its corresponding claim. When in doubt, label as `"heuristic"` or `"none"` — never inflate. The governing principle is that an operator reading these fields can trust them to honestly describe the system's confidence in its own output.

### 9.1b Implementation Sequence

1. **Backend models** — add `evidence_class` to `ParticipantContribution`, `evidence_basis` to `AgentHealthItem`, `projection_quality` + `missing_fields` to `AgentTraceResponse`. All with defaults. Run backend tests — all existing tests must pass unchanged because defaults are backward-compatible.
   - Gate: 523+ passed, zero new failures

2. **Health service** — add `evidence_basis=` to every `AgentHealthItem` constructor call in `ops_health.py`. Add tests to `test_ops_endpoints.py` for AC-4 through AC-8.
   - Gate: all health tests pass, new evidence_basis tests green

3. **Trace service** — add `evidence_class=` to every `ParticipantContribution` constructor in `project_trace()`. Compute `projection_quality` + `missing_fields` at end of projection. Add tests to `test_ops_trace_endpoints.py` for AC-1, AC-2, AC-9, AC-10, AC-20.
   - Gate: all trace tests pass, new trust tests green

4. **Frontend types** — add new optional fields to `ops.ts`. Update test fixtures in `ops.test.tsx`. No component changes.
   - Gate: TypeScript compiles clean; frontend test count ≥ diagnostic baseline

5. **Contract doc** — update `AGENT_OPS_CONTRACT.md` §5.5 (health evidence_basis), §6.4 (trace projection_quality + missing_fields), §6.7 (contribution evidence_class). Field definitions, enums, and examples must match backend serialized payload.
   - Gate: manual review — every updated section matches backend output

6. **Full regression** — run backend and frontend test suites.
   - Gate: backend 523+ passed (adjusted for new tests); frontend ≥ diagnostic baseline; zero new failures from this tranche

### 9.2 Code change surface

| File | Role |
|------|------|
| `ai_analyst/api/models/ops.py` | Add `evidence_basis` to `AgentHealthItem` |
| `ai_analyst/api/models/ops_trace.py` | Add `evidence_class` to `ParticipantContribution`, `projection_quality` + `missing_fields` to `AgentTraceResponse` |
| `ai_analyst/api/services/ops_health.py` | Tag each health item constructor |
| `ai_analyst/api/services/ops_trace.py` | Tag each participant, compute projection quality |
| `tests/test_ops_endpoints.py` | Add health evidence_basis tests |
| `tests/test_ops_trace_endpoints.py` | Add evidence_class + projection quality tests |
| `ui/src/shared/api/ops.ts` | Add optional fields to types |
| `ui/tests/ops.test.tsx` | Update fixtures |
| `docs/ui/AGENT_OPS_CONTRACT.md` | Update §5.5, §6.4, §6.7 |

**No changes expected to:**
- `ai_analyst/api/services/ops_roster.py` (no trust metadata on roster)
- `ai_analyst/api/services/ops_detail.py` (detail is downstream of health/trace — it consumes trust metadata from those sources. Adding trust provenance to detail's own projections is deferred to a future pass if needed)
- `ai_analyst/api/services/reflect_aggregation.py` (no trust metadata on reflect)
- `ui/src/workspaces/` (no component rendering changes)
- Any analysis pipeline, arbiter, or persona code

**If any of the above require changes, flag before proceeding.**

### 9.3 Out of scope (repeat)

- No health_state value changes
- No override detection logic changes
- No data_state derivation changes
- No frontend component rendering changes
- No pipeline changes
- No SQLite, no new top-level module

---

## 10. Success Definition

Tranche 3 is done when: every `ParticipantContribution` carries an `evidence_class` that honestly labels whether its override-assessment provenance is artifact-evidenced, heuristic-inferred, or defaulted; every `AgentHealthItem` carries an `evidence_basis` that distinguishes runtime events from proxy-derived inference; every `AgentTraceResponse` carries `projection_quality` (v1: `"partial"` or `"heuristic"` only) and `missing_fields` that tell the operator how much of the trace is directly evidenced vs inferred; frontend types include all new fields as optional additions; contract doc reflects all new fields with correct semantics; all backend and frontend tests pass with zero new failures from this tranche (ops-surface frontend tests individually tracked); and the governing rule — **do not claim more than the artifacts prove** — is testable via route-level contract tests on both trace (AC-20) and health (AC-22) surfaces.

---

## 11. Why This Phase Matters

| Without | With |
|---------|------|
| Override `was_overridden=True` looks like proven fact | `evidence_class: "heuristic"` tells operator it's inferred |
| Governance health `"live"` looks like runtime evidence | `evidence_basis: "derived_proxy"` tells operator it's context-inferred |
| `data_state: "live"` suggests full trust | `projection_quality: "heuristic"` + `missing_fields` tells operator exactly what's inferred |
| Operator cannot distinguish "complete" from "partial but renders clean" | Operator has explicit metadata to assess fidelity |
| Future rendering work has no provenance data to show | Future UI can render trust badges, confidence indicators, warning banners from this metadata |
| "Do not claim more than the artifacts prove" is a principle | "Do not claim more than the artifacts prove" is testable via `evidence_class`, `evidence_basis`, `projection_quality` |

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 8 (PR-REFLECT-3) | Suggestions v0, cross-workspace nav, coherence | ✅ Done |
| Audit Tranche 1 | Contract alignment repair (Findings 1, 2, 3) | ✅ Done — 21 ACs |
| Audit Tranche 2 | Projection core module (Findings 7, 8) | ✅ Done — 15 ACs |
| Audit Tranche 3 | Trust integrity (Findings 4, 5, 6) | ✅ Done — 22 ACs |
| Audit Tranche 4 / Backlog | Resilience + test infra (Findings 9–12) | 💭 Backlog |
| Phase 9 candidates | Filter controls, Chart Indicators, ML Pattern Detection | 💭 Concept — after audit tranches |

---

## 13. Diagnostic Findings

*Populated from diagnostic report — 28 March 2026.*

### Frontend failure classification
17 failures, 389 passing. **Zero failures in ops-surface tests.** All 17 are in journey (5), chart (6), analysis-run (3), journal-review (2), and triage (1). T3's modified surfaces (health + trace) have a clean regression baseline.

### Model schemas confirmed clean
- `AgentHealthItem`: no `evidence_basis` field — adding optional with default is backward-compatible
- `ParticipantContribution`: no `evidence_class` field
- `AgentTraceResponse`: no `projection_quality` or `missing_fields`

### Health constructor sites
10 sites across 5 functions. Two unavailable branches (feeder_ingest line 42, mdo_scheduler line 86) clarified: these get `evidence_basis: "none"` (not `"runtime_event"`) because no runtime signal was observed. Spec §6.2 and AC-4 updated to lock this.

### Trace override heuristic
Self-contained block at lines 249–261. `evidence_class` determined once per participant (based on `has_audit`), passed to 4 `ParticipantContribution` constructors.

### Backend baseline
523 passed, 3 failed (pre-existing). Confirmed.

### Patch set
~206 lines across 9 files. Well under cap.

---

## 14. Appendix — Recommended Agent Prompt

```
# REPO: C:/Users/david/OneDrive/Documents/GitHub/AI trade analyst

Read `docs/specs/PR_AUDIT_T3_TRUST_INTEGRITY_SPEC.md` in full before starting.
Treat it as the controlling spec for this pass.

Governing rule: DO NOT CLAIM MORE THAN THE ARTIFACTS PROVE.

First task only — run the diagnostic protocol in Section 8 and report findings
before changing any code:

1. Classify all 17 frontend test failures by surface (journey, ops, reflect, etc.)
2. Confirm AgentHealthItem model has no existing evidence_basis field
3. Confirm ParticipantContribution model has no existing evidence_class field
4. Confirm AgentTraceResponse model has no existing projection_quality / missing_fields
5. Confirm health service constructor call sites — count and line numbers
6. Confirm trace override heuristic location — line numbers
7. Run baseline backend test suite — report exact counts
8. Propose smallest patch set: files, one-line description, estimated line delta

Hard constraints:
- Governing rule applies to every field addition: if the system cannot prove a claim, the field must say so
- No health_state value changes — evidence_basis is additive, health_state stays the same
- No override detection logic changes — evidence_class tags the existing heuristic, does not modify it
- No data_state derivation changes
- No frontend component rendering changes — type additions only
- evidence_class "heuristic" applies to ALL participants when audit log present (both overridden and non-overridden), because absence of override is also inferred
- No SQLite, no new top-level module
- Deterministic tests only — no live provider dependency in CI

Do not change any code until the diagnostic report is reviewed and the
patch set is approved.

On completion, close the spec and update docs per Workflow E:
1. `docs/specs/PR_AUDIT_T3_TRUST_INTEGRITY_SPEC.md` — mark ✅ Complete, flip all AC cells,
   populate §13 Diagnostic Findings with: frontend failure classification, model schema
   confirmations, constructor site counts, override heuristic location, any surprises
2. `docs/AI_TradeAnalyst_Progress.md` — dashboard-aware update per Workflow E.2:
   update header (current phase), add Recent Activity row for Audit T3,
   update Phase Status Overview, update Phase Index, add test count row,
   update Roadmap, update debt register if applicable
3. Review `AGENT_OPS_CONTRACT.md` — this IS a primary doc change for this phase
4. Cross-document sanity check: no contradictions, no stale phase refs
5. Return Phase Completion Report

Commit all doc changes on the same branch as the implementation.
```
