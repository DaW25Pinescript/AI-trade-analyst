# PR-AE-3 — Claude Code Agent Prompt

**Branch:** `feature/pr-ae-3-snapshot-builder`
**Spec:** `docs/ANALYSIS_ENGINE_SPEC_v1.2.md` (controlling document)
**Depends on:** PR-AE-1 and PR-AE-2 merged — `LensBase`, `LensOutput`, `StructureLens`, `TrendLens`, `MomentumLens` proven
**Acceptance criteria:** AC-5, AC-6, AC-7, AC-8, AC-9, AC-10

---

## Context

PR-AE-1 shipped the base contract and Structure Lens.
PR-AE-2 shipped Trend Lens + Momentum Lens.
P1 compute is now complete.

PR-AE-3 is the **shared truth layer** for the Analysis Engine:
- Lens registry
- Evidence Snapshot Builder
- Failure-aware meta
- Derived alignment/conflict signals
- Snapshot identity (`snapshot_id`)

This is the **Gate 1 closer** for P1. It defines the immutable snapshot contract that all downstream persona and governance work will read.

Do not redesign anything.
Do not add features.
Do not reinterpret the spec.

The spec is explicit:
- Snapshot combines active lens outputs into a single immutable object
- Failed lenses are recorded in `meta.failed_lenses` and `meta.lens_errors`
- Inactive lenses are recorded in `meta.inactive_lenses` and omitted from `lenses.*`
- `alignment_score` and `conflict_score` are deterministic
- `snapshot_id` is a hash of content
- `run_status` is determined at the Snapshot Builder stage, not by governance later

**Regression baseline: verify exact count before starting** (expected ~653+ — confirm with `python -m pytest ai_analyst/ -q`).

---

## Hard Rules

- Do not modify any persona code
- Do not modify governance code
- Do not wire into the graph/pipeline yet unless the spec explicitly requires it for this PR
- Do not add new lenses
- Do not add new top-level modules outside `ai_analyst/`
- Do not create a separate `ai_analyst/models/evidence_snapshot.py` — snapshot is a plain `dict`, not a typed model
- Do not use live provider data in tests
- Tests must use frozen, deterministic fixtures only
- Snapshot Builder must be deterministic and pure from its inputs
- No partial snapshot corruption: failed lens outputs go to meta, not half-written namespaced data

---

## Spec Contract to Follow

### Lens Registry

The spec defines the v1 lens registry as:

```json
{
  "lens_registry": [
    {"id": "structure", "version": "v1.0", "enabled": true},
    {"id": "trend",     "version": "v1.0", "enabled": true},
    {"id": "momentum",  "version": "v1.0", "enabled": true}
  ]
}
```

### Evidence Snapshot shape

```json
{
  "context": {
    "instrument": "XAUUSD",
    "timeframe": "1H",
    "timestamp": "2026-03-18T10:30:00Z"
  },
  "lenses": {
    "structure": { "...full structure lens output..." },
    "trend": { "...full trend lens output..." },
    "momentum": { "...full momentum lens output..." }
  },
  "derived": {
    "alignment_score": 0.85,
    "conflict_score": 0.10,
    "signal_state": "SIGNAL",
    "coverage": 0.66,
    "persona_agreement_score": null
  },
  "note": "coverage and persona_agreement_score are populated in the run object after personas complete — not in the snapshot itself (snapshot is built before personas run)",
  "meta": {
    "active_lenses": ["structure", "trend", "momentum"],
    "inactive_lenses": [],
    "failed_lenses": [],
    "lens_errors": {},
    "evidence_version": "v1.0",
    "snapshot_id": "sha256-hash-of-content"
  }
}
```

Important:

* `coverage` and `persona_agreement_score` are present in the snapshot schema but are **not populated by the Snapshot Builder**. At snapshot-build time, both should be `null`. Do not invent a later-phase computation here.
* Snapshot is immutable once built.
* Downstream code reads this object only.
* Snapshot is a **plain dict**, not a Pydantic model. `SnapshotBuildResult` carries `snapshot: dict | None`.

### Derived signals

Use the spec's exact deterministic mapping:

```python
DIRECTION_MAP = {
    "bullish": +1, "positive": +1, "above": +1, "expanding": +1,
    "bearish": -1, "negative": -1, "below": -1, "reversing": -1,
    "neutral": 0, "flat": 0, "mixed": 0, "unknown": 0
}
```

Primary directional fields per lens:

* structure -> `lenses.structure.trend.local_direction`
* trend     -> `lenses.trend.direction.overall`
* momentum  -> `lenses.momentum.direction.state`

Formula:

```python
direction_values = [DIRECTION_MAP.get(lens_primary_direction, 0)
                    for lens in active_lenses]

if all(v == 0 for v in direction_values):
    alignment_score = 0.0
    conflict_score  = 0.0
    signal_state    = "NO_SIGNAL"
else:
    alignment_score = abs(mean(direction_values))  # mean = sum / len
    conflict_score  = 1.0 - alignment_score
    signal_state    = "SIGNAL"
```

Use plain arithmetic (`sum(values) / len(values)`) for the mean — no external mean function needed.

### Snapshot Builder responsibilities

Per spec, `ai_analyst/core/snapshot_builder.py` is responsible for:

1. Collect all `LensOutput` objects
2. Validate each against its contract
3. Populate `meta` (`active_lenses`, `inactive_lenses`, `failed_lenses`, `lens_errors`, version, snapshot_id)
4. Compute `derived.alignment_score` and `derived.conflict_score`
5. Assemble and return the immutable snapshot object

### run_status

Per spec, `run_status` is determined at the Snapshot Builder stage:

* `SUCCESS`: all lenses succeeded
* `DEGRADED`: at least one lens failed and at least one succeeded
* `FAILED`: all lenses failed

This PR should return or expose `run_status` from the builder layer rather than force downstream recomputation.

---

## Files to Create

| File | Purpose |
|---|---|
| `ai_analyst/lenses/registry.py` | Canonical v1 lens registry + simple helpers |
| `ai_analyst/core/snapshot_builder.py` | Evidence Snapshot Builder + run_status derivation |
| `ai_analyst/tests/core/__init__.py` | Test package init (if not already present) |
| `ai_analyst/tests/core/test_lens_registry.py` | Unit tests for registry behavior |
| `ai_analyst/tests/core/test_snapshot_builder.py` | Unit tests for snapshot assembly, failure meta, derived signals, snapshot_id |

**Registry location follows the spec:** Section 12.3 names `ai_analyst/lenses/registry.py`. Do not place it in `core/`.

## Existing Files Allowed to Modify

Keep this minimal and additive only.

| File | Change |
|---|---|
| `ai_analyst/lenses/__init__.py` | Add registry exports only if needed for clean imports |
| `ai_analyst/core/__init__.py` | Create or update only if required by repo package structure |

Do not touch graph, personas, governance, UI, or persistence.

---

## Implementation Targets

### 1. `ai_analyst/lenses/registry.py`

Implement a minimal, explicit registry for v1.

Recommended shape:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class LensRegistryEntry:
    id: str
    version: str
    enabled: bool = True
```

Provide:

* canonical `V1_LENS_REGISTRY` — list of 3 frozen entries
* helper to return registry snapshot as `list[dict]`
* helper to derive enabled lens IDs
* helper to derive inactive lens IDs

Keep it simple.
No plugin architecture.
No dynamic imports.
No user-authored lens loading.

### 2. `ai_analyst/core/snapshot_builder.py`

Implement the snapshot builder as a pure deterministic module.

Recommended public surface:

```python
from pydantic import BaseModel
from typing import Literal

class SnapshotBuildResult(BaseModel):
    snapshot: dict | None
    run_status: Literal["SUCCESS", "DEGRADED", "FAILED"]
    error: str | None = None
```

Recommended entry point:

```python
def build_evidence_snapshot(
    *,
    instrument: str,
    timeframe: str,
    timestamp: str,
    lens_outputs: list[LensOutput],
    lens_registry: list[dict] | None = None,
) -> SnapshotBuildResult:
    ...
```

Behavior:

* Accept `LensOutput` objects from the three v1 lenses
* Use registry to determine which lenses are enabled/inactive
* For each enabled lens:
  * if `status == "success"` and `data` is present → namespace under `snapshot["lenses"][lens_id]`
  * if `status == "failed"` → add to `meta.failed_lenses`, record `meta.lens_errors[lens_id]`, do NOT place under `lenses.*`
* For inactive lenses:
  * add to `meta.inactive_lenses`
  * omit from `lenses.*`
* Build `context`
* Build `derived` — `coverage` and `persona_agreement_score` always `null`
* Build `meta`
* Compute `snapshot_id`
* Derive `run_status`
* Return `SnapshotBuildResult`

### 3. Snapshot ID

`snapshot_id` must be deterministic and content-based.

Requirements:

* stable for identical input content
* different when content changes
* based on canonical JSON serialization of snapshot content

Recommended approach:

1. Build snapshot dict with `meta.snapshot_id = ""`
2. Canonicalize JSON (`sort_keys=True`, stable separators)
3. SHA-256 hash
4. Backfill `meta.snapshot_id` with the resulting hex digest
5. Return final snapshot

Be consistent across tests.
Do not include nondeterministic ordering.

### 4. Schema discipline

The snapshot must namespace only successful lens `data`, not full `LensOutput` wrappers.

Correct:

```json
"lenses": {
  "structure": { "...structure lens data dict..." }
}
```

NOT:

```json
"lenses": {
  "structure": {
    "status": "success",
    "data": { "..." }
  }
}
```

### 5. run_status behavior

* no successful lenses → `FAILED`, `snapshot` may be partial or absent depending on the cleanest implementation, but be consistent and test it
* some success + some failure → `DEGRADED`
* all active enabled lenses successful → `SUCCESS`

Important: if all enabled lenses fail, do not pretend there is a valid evidence surface.

---

## TDD Sequence

Follow red/green/refactor strictly.

### Lens Registry

```text
1. Write test_registry_contains_three_v1_lenses                      → RED
2. Implement minimal canonical registry                              → GREEN
3. Write test_registry_entries_have_id_version_enabled               → RED
4. Implement entry shape/export helper                               → GREEN
5. Write test_enabled_lens_ids_default_to_structure_trend_momentum   → RED
6. Implement enabled-id helper                                       → GREEN
7. Write test_inactive_lens_logic_when_one_disabled                  → RED
8. Implement inactive-id helper                                      → GREEN
9. Refactor                                                          → GREEN
```

### Snapshot Builder

```text
1. Write test_build_returns_result_object                            → RED
2. Create minimal SnapshotBuildResult + build_evidence_snapshot      → GREEN
3. Write test_snapshot_contains_context_lenses_derived_meta          → RED
4. Implement skeleton snapshot assembly                              → GREEN
5. Write test_successful_lenses_are_namespaced_under_lenses          → RED
6. Implement successful lens namespacing                             → GREEN
7. Write test_failed_lens_goes_to_meta_failed_lenses_not_lenses      → RED
8. Implement failed lens handling                                    → GREEN
9. Write test_inactive_lens_goes_to_meta_inactive_and_is_absent      → RED
10. Implement inactive lens handling                                 → GREEN
11. Write alignment/conflict score tests (7-scenario table below)    → RED
12. Implement exact deterministic formulas                           → GREEN
13. Write all_neutral_edge_case_sets_no_signal                       → RED
14. Implement NO_SIGNAL branch                                       → GREEN
15. Write run_status_tests_success_degraded_failed                   → RED
16. Implement run_status derivation                                  → GREEN
17. Write snapshot_id_stability_and_uniqueness_tests                 → RED
18. Implement canonical hash logic                                   → GREEN
19. Write regression/shape tests for AC-5..AC-9                      → RED
20. Refactor — no behavior change                                    → GREEN
21. Run full relevant suite                                          → GREEN
```

---

## Alignment Score Test Scenarios

These 7 scenarios prove the derived signal formula handles every combination. Test each explicitly using `pytest.approx` for float comparisons.

| # | Scenario | Structure direction | Trend overall | Momentum state | Direction values | Expected alignment | Expected conflict | Expected signal_state |
|---|---|---|---|---|---|---|---|---|
| 1 | All bullish | bullish (+1) | bullish (+1) | bullish (+1) | [+1, +1, +1] | 1.0 | 0.0 | SIGNAL |
| 2 | All bearish | bearish (-1) | bearish (-1) | bearish (-1) | [-1, -1, -1] | 1.0 | 0.0 | SIGNAL |
| 3 | Full conflict | bullish (+1) | bearish (-1) | neutral (0) | [+1, -1, 0] | 0.0 | 1.0 | SIGNAL |
| 4 | 2 bull + 1 bear | bullish (+1) | bullish (+1) | bearish (-1) | [+1, +1, -1] | 0.333... | 0.666... | SIGNAL |
| 5 | All neutral | ranging (0) | ranging (0) | neutral (0) | [0, 0, 0] | 0.0 | 0.0 | NO_SIGNAL |
| 6 | 2 bull + 1 neutral | bullish (+1) | bullish (+1) | neutral (0) | [+1, +1, 0] | 0.666... | 0.333... | SIGNAL |
| 7 | 1 lens only (DEGRADED) | bullish (+1) | — (failed) | — (failed) | [+1] | 1.0 | 0.0 | SIGNAL |

Scenario 7 is critical: when two lenses fail, derived signals are computed only from the surviving active lens. The builder must not include failed lens directions in the calculation.

---

## Test Fixtures

Do **not** use raw price data here.
This layer consumes `LensOutput` objects, not OHLCV.

Create frozen helper builders in the snapshot builder test file:

```python
from ai_analyst.lenses.base import LensOutput


def make_structure_success(direction="bullish", state="HH_HL") -> LensOutput:
    return LensOutput(
        lens_id="structure", version="v1.0", timeframe="1H", status="success", error=None,
        data={
            "timeframe": "1H",
            "levels": {"support": 2000.0, "resistance": 2100.0},
            "distance": {"to_support": 0.8, "to_resistance": 1.5},
            "swings": {"recent_high": 2095.0, "recent_low": 2010.0},
            "trend": {"local_direction": direction, "structure_state": state},
            "breakout": {"status": "holding", "level_broken": "resistance"},
            "rejection": {"at_support": False, "at_resistance": True},
        },
    )


def make_trend_success(overall="bullish") -> LensOutput:
    return LensOutput(
        lens_id="trend", version="v1.0", timeframe="1H", status="success", error=None,
        data={
            "timeframe": "1H",
            "direction": {"ema_alignment": "bullish", "price_vs_ema": "above", "overall": overall},
            "strength": {"slope": "positive", "trend_quality": "strong"},
            "state": {"phase": "continuation", "consistency": "aligned"},
        },
    )


def make_momentum_success(state="bullish") -> LensOutput:
    return LensOutput(
        lens_id="momentum", version="v1.0", timeframe="1H", status="success", error=None,
        data={
            "timeframe": "1H",
            "direction": {"state": state, "roc_sign": "positive"},
            "strength": {"impulse": "strong", "acceleration": "rising"},
            "state": {"phase": "expanding", "trend_alignment": "aligned"},
            "risk": {"exhaustion": False, "chop_warning": False},
        },
    )


def make_failed_output(lens_id="momentum", error="insufficient bars") -> LensOutput:
    return LensOutput(
        lens_id=lens_id, version="v1.0", timeframe="1H",
        status="failed", error=error, data=None,
    )
```

---

## Required Tests

### `ai_analyst/tests/core/test_lens_registry.py`

Minimum coverage:

* registry contains exactly structure/trend/momentum
* each entry has id/version/enabled
* default enabled set is all three
* disabling one lens marks it inactive without mutating canonical defaults

### `ai_analyst/tests/core/test_snapshot_builder.py`

Minimum coverage by class:

#### `TestSnapshotBuilderSchema`

* returns `SnapshotBuildResult`
* snapshot contains top-level `context`, `lenses`, `derived`, `meta`
* `context.instrument`, `context.timeframe`, `context.timestamp` preserved
* successful lens outputs namespaced under `lenses.<lens_id>`
* only lens `data` is stored, not wrapper metadata
* `coverage` is `null` at snapshot time
* `persona_agreement_score` is `null` at snapshot time

#### `TestSnapshotBuilderFailureMeta`

* failed lens appears in `meta.failed_lenses`
* failed lens error stored in `meta.lens_errors`
* failed lens absent from `lenses.*`
* inactive lens appears in `meta.inactive_lenses`
* inactive lens absent from `lenses.*`

#### `TestSnapshotBuilderDerivedSignals`

Test all 7 scenarios from the alignment score table above. Use `pytest.approx` for float comparisons.

#### `TestSnapshotBuilderRunStatus`

* all active enabled lenses success → `SUCCESS`
* one or more failures with at least one success → `DEGRADED`
* all enabled lenses failed → `FAILED`

#### `TestSnapshotId`

* identical snapshot inputs produce identical `snapshot_id`
* changing one field changes `snapshot_id`
* `snapshot_id` present in meta on every non-error snapshot
* hash generation is deterministic across repeated runs

---

## Acceptance Criteria Mapping

| AC | Criterion | What proves it |
|---|---|---|
| AC-5 | Snapshot Builder namespaces lens outputs under `lenses.*` | `test_successful_lenses_are_namespaced_under_lenses` |
| AC-6 | Failed lens in `meta.failed_lenses` + error in `meta.lens_errors` | `TestSnapshotBuilderFailureMeta` tests |
| AC-7 | Inactive lens in `meta.inactive_lenses` — absent from `lenses.*` | `TestSnapshotBuilderFailureMeta` tests |
| AC-8 | `alignment_score` and `conflict_score` computed, in 0.0–1.0 | 7-scenario test table in `TestSnapshotBuilderDerivedSignals` |
| AC-9 | `snapshot_id` unique per content | `TestSnapshotId` stability + uniqueness tests |
| AC-10 | All existing tests remain green | Full `pytest ai_analyst/ -q` regression check |

---

## Constraints

* All new code under `ai_analyst/`
* No live provider dependency
* No pipeline wiring in this PR
* No persona/governance/UI work
* No separate snapshot model file — snapshot is a plain dict
* No speculative multi-timeframe support implementation beyond preserving the schema shape
* No dynamic registry/plugin system
* No SQLite
* No LLM behavior changes

---

## Verification Checklist

```bash
# 1. New tests
python -m pytest ai_analyst/tests/core/test_lens_registry.py -v
python -m pytest ai_analyst/tests/core/test_snapshot_builder.py -v

# 2. Lens tests still green
python -m pytest ai_analyst/tests/lenses/ -v

# 3. Core + lens slice green
python -m pytest ai_analyst/tests/core ai_analyst/tests/lenses -v

# 4. Full regression — must be >= baseline (verify before starting)
python -m pytest ai_analyst/ --tb=short -q 2>&1 | tail -5

# 5. Inspect changed files
git diff --name-only main
# Expected: only files under ai_analyst/lenses/, ai_analyst/core/,
#           ai_analyst/tests/core/ plus minimal __init__.py if needed

# 6. Gate 1 checklist — all must be true after merge:
#    [x] AC-1:  Structure Lens valid schema (PR-AE-1)
#    [x] AC-2:  Trend Lens valid schema (PR-AE-2)
#    [x] AC-3:  Momentum Lens valid schema (PR-AE-2)
#    [x] AC-4:  Failed lens clean failure (PR-AE-1 + PR-AE-2)
#    [x] AC-5:  Snapshot namespaces under lenses.* (this PR)
#    [x] AC-6:  Failed lens in meta (this PR)
#    [x] AC-7:  Inactive lens in meta (this PR)
#    [x] AC-8:  Derived signals computed, in range (this PR)
#    [x] AC-9:  snapshot_id unique hash (this PR)
#    [x] AC-10: All existing tests green (this PR)
```

---

## PR Description

```
PR-AE-3: Lens Registry + Evidence Snapshot Builder — Gate 1 closer

Closes Gate 1 for P1 by adding the immutable shared evidence layer:
- ai_analyst/lenses/registry.py: canonical v1 lens registry
- ai_analyst/core/snapshot_builder.py: snapshot assembly, failure-aware meta,
  derived signals, snapshot_id, run_status
- ai_analyst/tests/core/test_lens_registry.py: registry tests
- ai_analyst/tests/core/test_snapshot_builder.py: snapshot builder tests

Acceptance criteria closed:
- AC-5  Snapshot Builder namespaces lens outputs under lenses.*
- AC-6  Failed lens recorded in meta.failed_lenses + meta.lens_errors
- AC-7  Inactive lens recorded in meta.inactive_lenses and absent from lenses.*
- AC-8  alignment_score/conflict_score computed deterministically in 0.0-1.0 range
- AC-9  snapshot_id generated from content hash
- AC-10 existing tests remain green

Gate 1 complete: all 10 P1 acceptance criteria pass.
No persona, governance, UI, or persistence changes.
Next: PR-AE-4 (PersonaContract schema + validator registry + AnalystOutput expansion).

Spec: docs/ANALYSIS_ENGINE_SPEC_v1.2.md, Sections 4.6, 5, 8.1, 12.3
```
