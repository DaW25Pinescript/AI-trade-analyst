# Repository Audit Report — 2026-03-05

## Scope

Quick health audit focused on regression checks and plan/debt hygiene.

Checks run:

1. `node --test tests/*.js`
2. `pytest -q ai_analyst/tests macro_risk_officer/tests`

---

## Findings

### 1) Python async test compatibility gap (FIXED)

**Severity:** MEDIUM (test-suite failure on Python 3.10+ default event-loop behavior)

`test_macro_context_node_prefers_feeder` in `ai_analyst/tests/test_phase2a_feeder_bridge.py`
used:

```python
asyncio.get_event_loop().run_until_complete(...)
```

On this environment, that raised:

`RuntimeError: There is no current event loop in thread 'MainThread'.`

**Fix:** switched to:

```python
asyncio.run(...)
```

This aligns with modern asyncio entrypoint behavior and removes dependence on an
implicitly created loop.

---

### 2) MRO determinism test was too strict vs time-decay math (FIXED)

**Severity:** LOW/MEDIUM (intermittent test flake)

`test_ingest_produces_same_context_for_same_payload` in
`macro_risk_officer/tests/test_modal_worker.py` used full dict equality on
`MacroContext.model_dump()`. Because decay uses current wall-clock time,
back-to-back runs can differ by tiny floating-point deltas in `asset_pressure`.

**Fix:** replaced full-object strict equality with:

- exact checks for stable categorical/structural fields (`regime`, `vol_bias`,
  `conflict_score`, `confidence`, `time_horizon_days`, `active_event_ids`,
  `explanation`), and
- `pytest.approx(..., abs=1e-9)` for `asset_pressure` float values.

This preserves determinism intent while avoiding false negatives from
sub-millisecond timing drift.

---

## Planning / debt updates applied

- Updated `docs/V3_master_plan.md` to v2.14 (2026-03-05), refreshed verification
  snapshot counts, and recorded both stability fixes.
- Extended testing gap table to include **TEST-11** and marked it fixed.
- Updated release checklist test count in `tooling/release_checklist.md`.

---

## Verification after fixes

- Browser suite: **150/150 pass**
- Python suites: **550 pass, 13 skipped**
- Combined: **700 pass, 0 fail** (+13 intentional skips)
