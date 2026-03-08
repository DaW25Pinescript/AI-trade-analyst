# Phase E+ Spec — Additional Instruments / Provider Abstraction

**Status:** Spec drafted — implementation pending  
**Date:** 8 March 2026  
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`

---

## 1. Purpose

Phase E+ is the next Market Data Officer evolution after the closed:

- **Phase 1A** — EURUSD baseline spine
- **Phase 1B** — XAUUSD baseline spine

Those phases proved the relay for two instruments:

```text
run_feed.py --fixture
        ↓
market_data/packages/latest/
        ↓
refresh_from_latest_exports("<instrument>")
        ↓
MarketPacketV2
        ↓
run_analyst() with packet
        ↓
AnalystOutput
        ↓
Arbiter / artifact write
```

Phase E+ is **not** another relay-proof phase for a single instrument.  
It is the **generalization phase**:

1. formalize instrument metadata into a reusable config layer
2. formalize provider/alias metadata without breaking the current Dukascopy-first spine
3. preserve the existing file-based artifact flow and `MarketPacketV2` contract
4. keep the relay deterministic and testable for EURUSD and XAUUSD while making extension to more instruments straightforward

---

## 2. Scope

### In scope

- extracting instrument-specific defaults from ad hoc code paths into a small, explicit config layer
- normalizing provider metadata / alias metadata per instrument
- preserving current active provider behavior (**Dukascopy remains primary** unless explicitly changed later)
- making fixture seeding instrument-aware via config rather than a hardcoded dict buried in one function
- ensuring `run_feed.py`, officer loaders, and tests read from the same instrument/provider metadata source
- preparing the repo for additional instruments without redesigning the analyst graph

### Target Instruments

| Instrument | Tier | Rationale |
|------------|------|-----------|
| GBPUSD | Tier 1 — FX major | Same family as EURUSD — easiest config extension, tests FX metadata generalisation |
| XAGUSD | Tier 2 — Metal | Same family as XAUUSD — proves metals pattern is not gold-only |
| XPTUSD | Tier 2 — Metal | Different price range and liquidity profile — stress-tests instrument-aware config |

**Deferred (not in this phase):**

| Instrument | Reason |
|------------|--------|
| DXY | Synthetic construction, may need alternate source logic — not a simple config extension |
| USDJPY, USDCAD, etc. | Defer until GBPUSD proves FX generalisation works cleanly |

### Out of scope

- no new top-level module
- no SQLite / database layer
- no scheduler / cron / APScheduler work
- no analyst graph redesign
- no UI redesign
- no MarketPacketV2 contract redesign unless a true spec mismatch is proven
- no mandatory live yFinance integration in this phase
- no broad multi-provider runtime switching unless the diagnostic proves a minimal version is already mostly present

---

## 3. Repo-Aligned Assumptions

These assumptions are based on the closed Phase 1A / 1B work and current repo direction.

| Area | Assumption |
|------|------------|
| Runtime artifacts | remain under `market_data/` |
| Storage model | file-based spine only |
| Feed output | canonical / derived / packages / reports |
| Officer contract | `build_market_packet()` / `refresh_from_latest_exports()` returning `MarketPacketV2` |
| Proven instruments | EURUSD, XAUUSD |
| Current active provider | Dukascopy |
| Future/optional alias concern | yFinance aliases should be represented in config, not assumed active |
| Relay proof status | EURUSD and XAUUSD already proven |
| Fixture strategy | remains valid and should become config-driven, not duplicated ad hoc |

### Instrument Metadata Reference

Approximate fixture parameters for each instrument — existing and new. Verify against `feed/config.py` before implementing; these are starting estimates, not hardcoded targets.

| Instrument | Price Scale | Plausible Range | Fixture Base Price | Fixture Volatility | Volume Range | yFinance Alias | Timeframes |
|------------|-------------|-----------------|-------------------|-------------------|--------------|----------------|-----------|
| EURUSD | 100,000 | 1.05 – 1.25 | 1.0850 | 0.0005 | 100 – 5,000 | `EURUSD=X` | 1m, 5m, 15m, 1h, 4h, 1d |
| XAUUSD | 1,000 | 1,500 – 3,500 | 2700.00 | 2.00 | 0.1 – 10.0 | `GC=F` | 15m, 1h, 4h, 1d |
| GBPUSD | 100,000 | 1.15 – 1.45 | 1.2700 | 0.0005 | 100 – 5,000 | `GBPUSD=X` | 1m, 5m, 15m, 1h, 4h, 1d |
| XAGUSD | 1,000 | 18.00 – 40.00 | 28.00 | 0.15 | 0.1 – 50.0 | `SI=F` | 15m, 1h, 4h, 1d |
| XPTUSD | 1,000 | 700.00 – 1,400.00 | 980.00 | 3.00 | 0.01 – 5.0 | `PL=F` | 15m, 1h, 4h, 1d |

> **Note:** `yFinance Alias` is metadata only — no live yFinance calls in Phase E+. Verify `PRICE_RANGES` in `feed/config.py` for XAGUSD/XPTUSD; if not yet defined, adding them is in scope.

### Current likely design smell

The most likely target in Phase E+ is that instrument/provider knowledge is still scattered, for example across:
- `_FIXTURE_PARAMS`
- feed config
- trusted instrument lists
- structure support
- optional alias assumptions in docs or future plans

Phase E+ should reduce this scatter without creating a new architecture.

---

## 4. Key Files Likely in Scope

The exact list must be confirmed by diagnostics, but Phase E+ is expected to stay near these files:

```text
market_data_officer/run_feed.py
market_data_officer/feed/config.py
market_data_officer/officer/service.py
market_data_officer/officer/loader.py
market_data_officer/tests/conftest.py
market_data_officer/tests/
docs/README_specs.md
docs/AI_TradeAnalyst_Progress.md
```

Potential additions are allowed **inside existing directories only** if diagnostics justify them, for example:
- a small config module under `market_data_officer/`
- a new test file under `market_data_officer/tests/`

No new top-level directory is allowed.

---

## 5. Current State Audit Hypothesis

This section is a starting hypothesis only. Diagnostics must confirm or reject it.

### What is already proven
- EURUSD relay proof
- XAUUSD relay proof
- deterministic fixture seeding exists
- officer packet assembly exists
- analyst packet consumption exists
- Dukascopy-first file spine works
- `MarketPacketV2` contract is stable enough to reuse

### What likely remains messy
- instrument-specific defaults may still be hardcoded in runtime code paths
- provider aliasing may exist only informally in docs, not in one config source
- future instruments may require touching multiple files to add basic support
- fixture parameters may not be normalized with feed/provider metadata

### Core Phase E+ question
Can the repo be changed so that adding a new instrument or representing an alternate provider alias becomes a **config update + targeted test**, rather than a scavenger hunt across multiple modules?

---

## 6. Acceptance Criteria

Before writing any code, diagnostics must report which of these are already true and which are not.

| Gate / Check | Acceptance Condition | Status |
|-------------|----------------------|--------|
| AC-1: centralized instrument metadata | Instrument-specific defaults (fixture pricing / volatility / volume / timeframe expectations / aliases where relevant) come from one repo-aligned config source rather than scattered literals | ⏳ Next |
| AC-2: provider metadata model | Provider identity and optional alias metadata are represented explicitly per instrument without changing current Dukascopy-first runtime semantics | ⏳ Next |
| AC-3: feed path compatibility | `run_feed.py` still works for existing proven instruments after the refactor | ⏳ Next |
| AC-4: officer contract preserved | `refresh_from_latest_exports()` / `build_market_packet()` still return valid `MarketPacketV2` without contract breakage | ⏳ Next |
| AC-5: fixture generalization | Fixture seeding for EURUSD and XAUUSD reads from the same config source and remains deterministic | ⏳ Next |
| AC-6: extension ergonomics | Adding a future instrument requires minimal config-first changes, not scattered code edits; this is demonstrated by at least one config-level extension test or documented dry-run path | ⏳ Next |
| AC-7: regression safety | Existing EURUSD and XAUUSD relay tests still pass | ⏳ Next |
| AC-8: no SQLite | No SQLite or DB layer introduced | ⏳ Next |
| AC-9: no new top-level module | Work stays inside existing repo/module boundaries | ⏳ Next |
| AC-10: no scheduler | No scheduling/orchestration automation introduced | ⏳ Next |

---

## 7. Pre-Code Diagnostic Protocol

Before changing code, the implementer must run these checks and report findings.

### Step 1 — Find instrument/provider scatter
Search for:
- instrument names (`EURUSD`, `XAUUSD`)
- fixture param dicts / base prices / volatility
- provider names / aliases (`Dukascopy`, `yfinance`, `EURUSD=X`, etc.)
- trusted instrument lists
- timeframe expectations

Expected result:
a concrete map of where instrument/provider knowledge currently lives.

### Step 2 — Identify current source(s) of truth
Determine:
- where active feed/provider behavior is actually decided
- where fixture seeding parameters are decided
- where officer trust / instrument handling is decided
- whether there is already a de facto config layer that should simply be normalized rather than replaced

### Step 3 — Verify relay baseline still holds
Run the existing MDO tests and confirm the current baseline remains green before any changes.

Expected baseline:
- current relay tests for EURUSD and XAUUSD pass
- no regressions before touching code

### Step 4 — Propose the smallest config-layer patch
Based on Steps 1–3, report:
- the minimum files to change
- whether a new small config file inside `market_data_officer/` is warranted
- whether existing config modules can absorb the change cleanly
- whether alias metadata should be data-only in this phase rather than behavior-switching

### Step 5 — Do not implement until reviewed
No code changes until the smallest patch set is approved.

---

## 8. Implementation Constraints

### 8.1 General rule
This is a **normalization phase**, not a redesign phase.

The implementer should prefer:
- extracting existing truth into one small config layer
- deleting duplicate literals
- preserving current behavior
- adding tests that lock the new shape

The implementer should avoid:
- inventing a new abstraction hierarchy unless diagnostics prove it is necessary
- live-provider complexity expansion
- touching analyst internals unless a true packet-contract issue is discovered

### 8.1b Implementation Sequence

For a refactor touching multiple consumers, order matters. Recommended sequence:

1. Define `INSTRUMENT_REGISTRY` (or `InstrumentConfig` dataclass + dict) with **existing instruments only** (EURUSD, XAUUSD)
2. Verify **364/364 tests still pass** — no behavior change yet
3. Add GBPUSD, XAGUSD, XPTUSD to registry
4. Update `run_feed.py`, `feed/config.py`, `officer/service.py` to read from registry
5. Verify **364/364 still pass** — prove refactor is non-breaking
6. Add new fixture + relay tests for the 3 new instruments

Do not skip Step 2 or Step 5. These are the regression checkpoints that prove the refactor is safe.

### 8.2 Allowed change surface
Expected allowed areas:

```text
market_data_officer/run_feed.py
market_data_officer/feed/config.py
market_data_officer/officer/service.py
market_data_officer/officer/loader.py
market_data_officer/tests/conftest.py
market_data_officer/tests/
```

Possible addition:
- one small config-focused file **inside `market_data_officer/`** if diagnostics show there is no clean existing home

### 8.3 Out of scope
- `ai_analyst/` graph redesign
- new database layer
- scheduler / cron
- UI or frontend work
- full provider failover system
- broad live yFinance ingestion migration

---

## 9. Success Definition

> **Phase E+ is done when:**
> the repo has one clear config-driven source of truth for instrument/provider metadata used by fixture seeding and related MDO paths → EURUSD and XAUUSD relay proofs still pass → provider alias metadata exists in a repo-aligned form without breaking current Dukascopy-first behavior → extending to an additional instrument is demonstrably more config-first and less scatter-prone → targeted tests pass → no SQLite introduced → no new top-level module created.

This is the same relay discipline as earlier phases, but now applied to **maintainability and extension ergonomics**, not just one-instrument proof.

---

## 10. Why Phase E+ Matters

Without Phase E+, every new instrument risks:
- repeated hardcoded fixture params
- repeated provider assumptions
- repeated alias handling discussions
- repeated manual sync across feed/officer/test paths

Phase E+ should convert that into:
- one explicit metadata layer
- one repeatable extension pattern
- less drift between docs and code
- faster future spec/diagnostic cycles

---

## 11. Diagnostic Findings

*To be populated after running the pre-code diagnostic protocol (Section 7).*

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1A | EURUSD baseline spine | ✅ Done |
| Phase 1B | XAUUSD baseline spine | ✅ Done |
| Phase E+ | Additional instruments, provider abstraction | ⏳ Next |
| Operationalise | Scheduler / APScheduler integration | Out of scope for E+ |

---

## 13. Recommended Agent Prompt

Read `docs/PhaseE_Spec.md` (or this draft) and treat it as the controlling spec for this pass.

First task only:
run the diagnostic protocol in Section 7 and report gaps before changing any code.

I want:
- a map of where instrument/provider knowledge currently lives
- a repo-vs-spec comparison
- a gap list against AC-1 through AC-10
- the smallest patch plan to normalize instrument/provider metadata without breaking current relay behavior

Hard constraints:
- no SQLite
- no new top-level module
- no scheduler
- preserve current Dukascopy-first runtime semantics unless diagnostics prove a minimal exception
- preserve `MarketPacketV2` contract path
- keep changes as small and local as possible

Do not code until the diagnostic report is complete and reviewed.

---

*Drafted from the closed Phase 1A / 1B specs, specs index, and current progress baseline on 8 March 2026.*
