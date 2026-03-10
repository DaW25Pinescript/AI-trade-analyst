# Per-Instrument Provider Routing Spec

**Status:** ✅ Complete
**Date:** 8 March 2026 (implemented 9 March 2026)
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`

---

## 1. Purpose

Per-Instrument Provider Routing is the next phase after the closed:

- **Phase 1A** — EURUSD baseline spine
- **Phase 1B** — XAUUSD baseline spine
- **Phase E+** — instrument/provider metadata normalization
- **Provider Switchover** — controlled yFinance fallback for trusted instruments
- **Phase F** — Instrument Promotion

Those phases proved:

1. the deterministic file-based relay from feed artifacts → officer → `MarketPacketV2` → analyst consumption
2. five trusted instruments: `EURUSD`, `GBPUSD`, `XAUUSD`, `XAGUSD`, `XPTUSD`
3. provider fallback exists
4. provider provenance is preserved
5. registry metadata is now the source of truth

This phase is not about proving whether the instruments work. That is already done.

This phase is about making **provider choice explicit per instrument**.

The goal is to move from:

- "Dukascopy-first with fallback available"

to:

- "each trusted instrument has an explicit provider policy"

---

## 2. Scope

### In scope

- define explicit provider policy for each trusted instrument
- allow per-instrument default provider configuration
- allow per-instrument fallback policy
- preserve the existing file-based artifact spine
- preserve `MarketPacketV2`
- preserve provider provenance through pipeline → manifest → officer packet
- keep tests deterministic and mock-driven

### Target instruments

| Instrument | Family | Current Provider Behavior |
|------------|--------|--------------------------|
| EURUSD | FX | Dukascopy default, yFinance fallback available (implicit) |
| GBPUSD | FX | Dukascopy default, yFinance fallback available (implicit) |
| XAUUSD | Metals | Dukascopy default, yFinance fallback available (implicit) |
| XAGUSD | Metals | Dukascopy default, yFinance fallback available (implicit) |
| XPTUSD | Metals | Dukascopy default, yFinance fallback available (implicit) |

> Current behavior is implicit and global. This phase makes it explicit and per-instrument.

### Out of scope

- no new top-level module
- no SQLite / database layer
- no scheduler / cron / APScheduler work
- no analyst graph redesign
- no `MarketPacketV2` contract redesign unless diagnostics prove a true incompatibility
- no "any asset" universal provider framework
- no live provider dependency as a required test gate

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|------------|
| Runtime artifacts | remain under `market_data/` |
| Storage model | file-based spine only |
| Officer contract | `build_market_packet()` / `refresh_from_latest_exports()` returning `MarketPacketV2` |
| Trusted instruments | EURUSD, GBPUSD, XAUUSD, XAGUSD, XPTUSD |
| Registry status | centralized instrument metadata already exists |
| Fallback status | controlled yFinance fallback already exists |
| Provenance status | vendor/source flows through pipeline → manifest → officer packet |
| Test philosophy | deterministic fixture/mock tests remain the required acceptance backbone |
| Live-provider checks | optional manual smoke only, not required CI/phase gate |

### Current likely state

The system likely has:

- one global fallback policy
- implicit default-provider behavior
- no explicit per-instrument provider policy field yet

This phase should close that gap.

### Default policy hypothesis (starting point for diagnostic)

| Family | Primary | Fallback | Fallback Allowed | Direction |
|--------|---------|---------|-----------------|-----------|
| FX (EURUSD, GBPUSD) | `dukascopy` | `yfinance` | `True` | `one_way` |
| Metals (XAUUSD, XAGUSD, XPTUSD) | `dukascopy` | `yfinance` | `True` | `one_way` |

> One-way means primary → fallback only. The `fallback_direction` field should be representable even if `"symmetric"` is not used in this phase — avoids a schema change if a future instrument needs it.

---

## 4. Key Files Likely in Scope

```text
market_data_officer/instrument_registry.py
market_data_officer/feed/pipeline.py
market_data_officer/feed/yfinance_fallback.py
market_data_officer/tests/conftest.py
market_data_officer/tests/
docs/specs/README.md
docs/AI_TradeAnalyst_Progress.md
```

Possible additions allowed **inside existing directories only**:
- one small provider-policy helper inside `market_data_officer/` if diagnostics show it is cleaner than overloading existing files
- one routing-focused test file under `market_data_officer/tests/`

No new top-level directory is allowed.

---

## 5. Current State Audit Hypothesis

This section is a starting hypothesis only. Diagnostics must confirm or reject it.

### What is already true

- all five target instruments are trusted
- yFinance fallback exists
- `yfinance_alias` exists in the registry
- provider provenance is already preserved
- deterministic tests exist for relay / registry / fallback behavior

### What likely remains incomplete

- no explicit provider policy field per instrument
- no explicit representation of: primary provider, fallback allowed/not allowed, fallback target, fallback direction
- runtime selection may still be driven by generic fallback logic rather than instrument policy

### Core Per-Instrument Routing question

Can the repo be changed so that each trusted instrument has an explicit provider policy, while preserving current artifact shape, packet contract, and deterministic testing?

---

## 6. Provider Policy Model

This phase should decide how provider policy is represented.

Minimum policy questions per instrument:

- What is the default provider?
- Is fallback allowed?
- If fallback is allowed, what is the fallback provider?
- What is the fallback direction — one-way (primary → fallback only) or symmetric?
- Should fallback trigger on empty/no-data, provider transport failure, or both?

### Example target shape (illustrative only)

```
EURUSD:
  primary_provider   = "dukascopy"
  fallback_provider  = "yfinance"
  fallback_enabled   = True
  fallback_direction = "one_way"

XAUUSD:
  primary_provider   = "dukascopy"
  fallback_provider  = "yfinance"
  fallback_enabled   = True
  fallback_direction = "one_way"
```

The diagnostic should determine whether this belongs directly in `instrument_registry.py` on `InstrumentMeta`, or in a small adjacent policy structure inside `market_data_officer/`.

> **Note on `fallback_direction`:** This field is schema-only in this phase — `"one_way"` is the only value used. Do not implement symmetric fallback behavior unless diagnostics prove it is already nearly free. The field exists to avoid a breaking schema change if a future instrument needs it.

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|----------------------|--------|
| AC-1 | Explicit provider policy exists | Each trusted instrument has an explicit provider policy in config/registry | ✅ Done |
| AC-2 | Default provider is deterministic | Runtime chooses the configured default provider per instrument rather than implicit global behavior | ✅ Done |
| AC-3 | Fallback policy is explicit | Fallback enabled/disabled, fallback target, and fallback direction are represented explicitly per instrument | ✅ Done |
| AC-4 | Existing fallback semantics preserved | Fallback still triggers only on approved provider failure conditions (empty/no-data or transport exception) — not on arbitrary downstream exceptions | ✅ Done |
| AC-5 | `fallback_enabled=False` testable | An instrument with `fallback_enabled=False` does not fall back — negative case proven by test | ✅ Done |
| AC-6 | Artifact compatibility preserved | Canonical / derived / package export shape remains compatible with current officer loaders | ✅ Done |
| AC-7 | Officer contract preserved | `refresh_from_latest_exports()` / `build_market_packet()` still return valid `MarketPacketV2` | ✅ Done |
| AC-8 | Provenance correct | `source.vendor` reflects actual provider used, not configured primary | ✅ Done |
| AC-9 | Deterministic tests | Acceptance remains fixture/mock driven; no live provider dependency in CI | ✅ Done |
| AC-10 | Live smoke optional only | At most one optional manual live-ingestion smoke; diagnostic only, not a required gate | ✅ Done |
| AC-11 | Regression safety | Existing trusted-instrument relay tests still pass | ✅ Done |
| AC-12 | No SQLite | No SQLite or DB layer introduced | ✅ Done |
| AC-13 | No new top-level module | Work stays inside existing repo/module boundaries | ✅ Done |
| AC-14 | No scheduler | No scheduling/orchestration automation introduced | ✅ Done |

---

## 8. Pre-Code Diagnostic Protocol

Before changing code, the implementer must run these checks and report findings.

### Step 1 — Map current provider-routing behavior

Search for Dukascopy references, yFinance references, fallback trigger logic, provider literals, provenance/vendor assignment, and any instrument-specific provider branching.

```bash
grep -n "provider\|dukascopy\|yfinance\|fallback\|vendor\|primary" market_data_officer/feed/pipeline.py market_data_officer/feed/yfinance_fallback.py market_data_officer/instrument_registry.py
```

Expected result: a concrete map of where provider choice is currently decided.

### Step 2 — Audit current `InstrumentMeta` fields

```python
from market_data_officer.instrument_registry import InstrumentMeta, INSTRUMENT_REGISTRY
import dataclasses
print(dataclasses.fields(InstrumentMeta))
for sym, meta in INSTRUMENT_REGISTRY.items():
    print(sym, meta)
```

Report: which policy fields are missing. Confirm whether registry already contains enough metadata to represent per-instrument policy or whether new fields are needed.

### Step 3 — Verify baseline remains green

```bash
python -m pytest market_data_officer/tests/ -q --tb=short
```

Expected: 419/419 green.

### Step 4 — Recommend smallest provider-policy design

Report the smallest safe design:
- direct policy fields on `InstrumentMeta` in `instrument_registry.py`
- or a small adjacent policy structure/helper inside `market_data_officer/`

Preferred answer: the smallest design that keeps provider policy explicit and testable.

### Step 5 — Define test strategy before code

Report how acceptance will be proven, including:
- correct provider selected on happy path (all five instruments)
- fallback activates when `fallback_enabled=True` and trigger condition met
- fallback does **not** activate when `fallback_enabled=False` (AC-5 negative case)
- provenance correct in both primary and fallback paths

No code until the smallest patch set is approved.

---

## 9. Implementation Constraints

### 9.1 General rule

This is a **provider policy phase**, not a provider framework phase.

The implementer should prefer:
- using the existing registry
- keeping one small provider-policy layer
- preserving current artifact shape and packet contract
- mocking provider selection/failure in tests
- keeping tests deterministic

The implementer should avoid:
- a broad plugin/provider framework
- cross-package sprawl
- rewriting feed/export/officer contracts
- introducing live-network dependencies into the core test suite

### 9.1b Implementation Sequence

1. Add policy fields to `InstrumentMeta` with defaults that reproduce current behavior
2. Verify **419/419** still pass — fields exist, nothing reads them yet
3. Update `feed/pipeline.py` to read provider policy from registry
4. Verify **419/419** still pass — policy read but behavior unchanged on happy path
5. Add tests: correct provider selected, fallback obeys policy, `fallback_enabled=False` proven, provenance correct
6. Verify **419+** pass — final gate

Do not skip Step 2 or Step 4. A behavior change on Step 3 that breaks existing tests must be caught before new tests are written.

### 9.2 Allowed change surface

```text
market_data_officer/instrument_registry.py     # add policy fields to InstrumentMeta
market_data_officer/feed/pipeline.py           # read policy from registry
market_data_officer/feed/yfinance_fallback.py  # if policy needs to be passed through
market_data_officer/tests/conftest.py          # policy fixture helpers if needed
market_data_officer/tests/test_provider_routing.py  # new — per-instrument policy tests
```

No changes expected to: `feed/export.py`, `officer/service.py`, `officer/contracts.py`.

### 9.3 Out of scope

- analyst graph redesign
- new DB layer
- scheduler / cron
- UI/frontend work
- broad "all providers for all assets" framework
- changing `MarketPacketV2`

---

## 10. Success Definition

> **Per-Instrument Provider Routing is done when:**  
> Each trusted instrument has an explicit provider policy in the registry → runtime reads policy, no hardcoded provider strings → correct provider selected on happy path → `fallback_enabled=False` proven by test → fallback obeys trigger conditions (empty/no-data or transport exception only) → `source.vendor` reflects actual provider used → existing relay tests pass unchanged → 419+ tests green → no SQLite → no new top-level module.

Provider choice is no longer a global implicit default. It is a per-instrument declaration, proven by tests.

---

## 11. Why This Phase Matters

Without Per-Instrument Provider Routing:
- provider choice remains partly implicit — a future instrument could be added without anyone deciding what its provider should be
- fallback cannot be disabled per instrument — no way to say "XPTUSD: Dukascopy only, no fallback"
- the registry carries `yfinance_alias` metadata with no runtime policy governing when it is used

With Per-Instrument Provider Routing:
- adding a new instrument requires an explicit provider decision — the registry enforces it
- instruments with thin liquidity or unreliable yFinance coverage can have fallback disabled
- `yfinance_alias` becomes a runtime-consumed field under a governing policy, not passive metadata

---

## 12. Diagnostic Findings

### InstrumentMeta fields added

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `primary_provider` | `str` | `"dukascopy"` | Default data provider for this instrument |
| `fallback_provider` | `str` | `"yfinance"` | Fallback provider when primary fails |
| `fallback_enabled` | `bool` | `True` | Whether fallback is allowed |
| `fallback_direction` | `str` | `"one_way"` | Schema-only — `"one_way"` or `"symmetric"` |

### Policy decisions per instrument

| Instrument | Primary | Fallback | Enabled | Direction | Justification |
|-----------|---------|----------|---------|-----------|---------------|
| EURUSD | dukascopy | yfinance | True | one_way | Reproduces current behavior. Reliable yFinance coverage via `EURUSD=X`. |
| GBPUSD | dukascopy | yfinance | True | one_way | Same FX family. Reliable yFinance coverage via `GBPUSD=X`. |
| XAUUSD | dukascopy | yfinance | True | one_way | Reproduces current behavior. Gold futures `GC=F` reliable on yFinance. |
| XAGUSD | dukascopy | yfinance | True | one_way | Same metals family. Silver futures `SI=F` reliable on yFinance. |
| XPTUSD | dukascopy | yfinance | True | one_way | Same metals family. Platinum `PL=F` has yFinance coverage. No deviation from family default. |

### AC gap table (pre-implementation)

| # | Gate | Pre-impl State | Gap? |
|---|------|---------------|------|
| AC-1 | Explicit provider policy | No policy fields on InstrumentMeta | **GAP** |
| AC-2 | Default provider deterministic | Implicit — Dukascopy hardcoded | **GAP** |
| AC-3 | Fallback policy explicit | Unconditional global fallback | **GAP** |
| AC-4 | Fallback semantics preserved | Triggers on empty/no-data or RequestException only | MET |
| AC-5 | `fallback_enabled=False` testable | No mechanism to disable fallback | **GAP** |
| AC-6 | Artifact compatibility | Baseline intact | MET |
| AC-7 | Officer contract preserved | Baseline intact | MET |
| AC-8 | Provenance correct | Vendor chain works end-to-end | MET |
| AC-9 | Deterministic tests | 419/419 fixture/mock | MET |
| AC-10 | Live smoke optional | No live tests | MET |
| AC-11 | Regression safety | 419/419 green | MET |
| AC-12 | No SQLite | None present | MET |
| AC-13 | No new top-level module | All in market_data_officer/ | MET |
| AC-14 | No scheduler | None present | MET |

### Patch set (files + line delta)

| File | Description | Delta |
|------|-------------|-------|
| `market_data_officer/instrument_registry.py` | +4 policy fields on InstrumentMeta with defaults + docstring | +8 lines |
| `market_data_officer/feed/pipeline.py` | Vendor stamps read from meta; fallback gated on meta.fallback_enabled | +4 lines, ~10 lines modified |
| `market_data_officer/tests/test_provider_routing.py` | **New** — 49 tests: policy fields, defaults, AC-4 trigger conditions, AC-5 negative case, provenance, immutability, guard rails | +262 lines |

### Regression gate results

| Gate | Result |
|------|--------|
| Step 2 (fields added, not wired) | 419/419 green |
| Step 4 (wired, before new tests) | 419/419 green |
| Step 6 (final, with new tests) | 468/468 green |

---

## 13. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1A | EURUSD baseline spine | ✅ Done — 359/359 |
| Phase 1B | XAUUSD spine | ✅ Done — 364/364 |
| Phase E+ | Instrument registry + GBPUSD/XAGUSD/XPTUSD | ✅ Done — 404/404 |
| Provider Switchover | yFinance fallback + vendor provenance | ✅ Done — 404/404 |
| Phase F | Instrument Promotion — all 5 trusted | ✅ Done — 419/419 |
| Per-Instrument Provider Routing | Explicit policy per instrument (this spec) | ✅ Done — 468/468 |
| Operationalise | Scheduler / APScheduler integration | ⏳ Pending |

---

## 14. Recommended Agent Prompt

```
Read `docs/specs/MDO_ProviderRouting_Spec.md` in full before starting. Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 8 and report findings before changing any code:

1. Map current provider-routing behavior — Dukascopy call sites, fallback trigger logic, vendor provenance chain
2. Audit InstrumentMeta fields — confirm which policy fields are missing
3. Run 419/419 baseline
4. Recommend smallest policy design: fields directly on InstrumentMeta vs adjacent structure
5. Report AC gap table (AC-1 through AC-14)
6. Propose smallest patch set: files, one-line description, estimated line delta
7. Propose default provider policy for all five trusted instruments — justify any deviation from family default

Hard constraints:
- No hardcoded provider strings in runtime code — registry is source of truth
- Default policy for EURUSD and XAUUSD must reproduce current behavior exactly — existing tests pass without modification
- fallback_enabled=False must be testable — prove fallback does not activate (AC-5)
- Fallback triggers only on empty/no-data or transport exception — not arbitrary downstream exceptions (AC-4)
- No SQLite, no new top-level module, no scheduler
- MarketPacketV2 contract locked
- Deterministic tests only

Do not change any code until the diagnostic report is reviewed and the patch set is approved.

On completion, close the spec and update docs:
1. `docs/specs/MDO_ProviderRouting_Spec.md` — mark ✅ Complete, flip all AC cells, populate §12 Diagnostic Findings with: InstrumentMeta fields added, policy decisions per instrument with justification, AC gap table (pre-impl), patch set (files + line delta), regression gate results
2. `docs/specs/README.md` — move to Completed, update Current Phase to Operationalise
3. `docs/AI_TradeAnalyst_Progress.md` — update current phase, add completed row with test count

Commit all doc changes on the same branch as the implementation.
```

---

*Drafted from closed Phase F spec, README_specs, and progress plan baseline on 8 March 2026.*
