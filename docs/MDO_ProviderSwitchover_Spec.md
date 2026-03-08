# Provider Switchover Spec — yFinance Fallback / Per-Instrument Switching

**Status:** Spec drafted — implementation pending  
**Date:** 8 March 2026  
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`

---

## 1. Purpose

Provider Switchover is the next phase after the closed:

- **Phase 1A** — EURUSD baseline spine
- **Phase 1B** — XAUUSD baseline spine
- **Phase E+** — instrument/provider metadata normalization

Those phases proved:

1. the deterministic file-based relay from feed artifacts → officer → `MarketPacketV2` → analyst consumption
2. the relay for at least two trusted instruments (**EURUSD**, **XAUUSD**)
3. a shared `instrument_registry` / metadata layer that now carries provider-adjacent metadata such as `yfinance_alias`

This phase is the first runtime provider phase.

Its purpose is to activate **controlled provider switchover behavior** using the now-complete registry and alias metadata, without destabilizing the existing **Dukascopy-first** working baseline.

---

## 2. Scope

### In scope

- define the runtime policy for provider selection
- add **yFinance fallback** behavior when Dukascopy is unavailable or unsuitable
- optionally support **per-instrument provider selection** if diagnostics show the code path is already close to that shape
- keep the file-based artifact spine intact
- preserve `MarketPacketV2`
- ensure fallback/switchover behavior is testable without live provider dependency in CI
- keep current proven instruments working:
  - EURUSD
  - XAUUSD
- use the completed registry / alias metadata as the source of provider-routing context

### Out of scope

- no new top-level module
- no SQLite / database layer
- no scheduler / cron / APScheduler work
- no analyst graph redesign
- no UI redesign
- no `MarketPacketV2` contract redesign unless a true incompatibility is proven
- no broad “any asset” universalization in this phase
- no live provider dependency as a required test gate

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|------------|
| Runtime artifacts | remain under `market_data/` |
| Storage model | file-based spine only |
| Officer contract | `build_market_packet()` / `refresh_from_latest_exports()` returning `MarketPacketV2` |
| Proven instruments | EURUSD, XAUUSD |
| Registry status | centralized instrument metadata already exists |
| Alias status | `yfinance_alias` metadata already exists per instrument |
| Current active runtime behavior | Dukascopy-first |
| Test philosophy | deterministic fixture tests remain the required acceptance backbone |
| Live-provider checks | optional manual smoke only, not required CI/phase gate |

### Instrument / Provider Reference

| Instrument | Trust Level | Dukascopy Ticker | yFinance Alias | Fallback in Scope |
|------------|-------------|-----------------|----------------|-------------------|
| EURUSD | trusted | `EURUSD` | `EURUSD=X` | ✅ Yes |
| XAUUSD | trusted | `XAUUSD` | `GC=F` | ✅ Yes |
| GBPUSD | unverified | `GBPUSD` | `GBPUSD=X` | ⏳ Later |
| XAGUSD | unverified | `XAGUSD` | `SI=F` | ⏳ Later |
| XPTUSD | unverified | `XPTUSD` | `PL=F` | ⏳ Later |

> Prove the fallback pattern on trusted instruments first. Unverified instruments deferred to a later phase.

### Expected strategic outcome

After this phase, provider behavior should become:

- explicit
- minimally configurable
- deterministic in tests
- backwards-compatible for current Dukascopy-first paths

without turning the MDO into a complex provider framework.

---

## 4. Key Files Likely in Scope

The exact list must be confirmed by diagnostics, but likely in-scope files include:

```text
market_data_officer/instrument_registry.py
market_data_officer/run_feed.py
market_data_officer/feed/config.py
market_data_officer/feed/pipeline.py
market_data_officer/feed/export.py
market_data_officer/tests/conftest.py
market_data_officer/tests/
macro_risk_officer/ingestion/clients/price_client.py   (read-only reference unless diagnostics justify reuse)
docs/README_specs.md
docs/AI_TradeAnalyst_Progress.md
```

Possible addition allowed **inside existing directories only**:
- one small provider-routing helper inside `market_data_officer/` if diagnostics show it is cleaner than overloading existing files

No new top-level directory is allowed.

---

## 5. Current State Audit Hypothesis

This section is a starting hypothesis only. Diagnostics must confirm or reject it.

### What is already true
- Dukascopy-first runtime behavior exists
- registry metadata exists
- `yfinance_alias` metadata already exists in the registry
- deterministic fixture tests exist and are the right acceptance backbone
- proven relay exists for EURUSD and XAUUSD
- alias normalization is complete enough that runtime switchover is now a narrower problem

### What likely remains incomplete
- provider selection may still be implicit/hardcoded
- fallback behavior may not exist at all in the MDO path
- yFinance alias metadata may exist but not be consumed by runtime feed logic
- provider failure semantics may not yet be explicit
- there may be no one place defining:
  - provider priority
  - fallback policy
  - per-instrument override behavior

### Core Provider Switchover question

Can the repo be changed so that provider choice becomes a small, explicit runtime policy — defaulting to Dukascopy but able to fall back to yFinance safely — without breaking current artifact generation and packet assembly?

---

## 6. Acceptance Criteria

Before writing any code, diagnostics must report which of these are already true and which are not.

| Gate / Check | Acceptance Condition | Status |
|-------------|----------------------|--------|
| AC-1: explicit provider policy | Current provider-selection logic is centralized and no longer buried in scattered conditionals / literals | ⏳ Next |
| AC-2: Dukascopy-first preserved | Existing Dukascopy-first semantics remain the default behavior | ⏳ Next |
| AC-3: yFinance fallback available | A controlled yFinance fallback path exists for supported instruments using `yfinance_alias`, without changing the default happy path. Fallback triggers on **both**: (1) empty/no-data response from Dukascopy, and (2) provider transport exception — not on any unhandled exception, and not preemptively | ⏳ Next |
| AC-4: per-instrument override representable | The config/registry can represent provider preference per instrument even if the default remains global | ⏳ Next |
| AC-5: artifact compatibility preserved | Canonical / derived / package export shape remains compatible with current officer loaders | ⏳ Next |
| AC-6: officer contract preserved | `refresh_from_latest_exports()` / `build_market_packet()` still return valid `MarketPacketV2` without contract breakage | ⏳ Next |
| AC-7: deterministic tests | Required acceptance remains fixture/mock driven; no live provider dependency is introduced into CI | ⏳ Next |
| AC-8: live smoke optional only | At most one optional manual live-ingestion smoke is added; it must be diagnostic only, not a required gate | ⏳ Next |
| AC-9: regression safety | Existing EURUSD/XAUUSD relay tests still pass | ⏳ Next |
| AC-10: no SQLite | No SQLite or DB layer introduced | ⏳ Next |
| AC-11: no new top-level module | Work stays inside existing repo/module boundaries | ⏳ Next |
| AC-12: no scheduler | No scheduling/orchestration automation introduced | ⏳ Next |

---

## 7. Pre-Code Diagnostic Protocol

Before changing code, the implementer must run these checks and report findings.

### Step 1 — Locate provider-selection logic
Search for:
- Dukascopy references
- yFinance references
- provider literals
- alias usage (`yfinance_alias`, `EURUSD=X`, etc.)
- any existing fallback logic
- any per-instrument branching on provider

Expected result:
a concrete map of where runtime provider behavior is currently decided.

### Step 2 — Compare metadata vs runtime usage
Determine:
- where `yfinance_alias` currently exists
- whether it is already consumed anywhere by MDO runtime code
- whether provider info is already present in registry/config in enough shape to support runtime switchover
- whether any current macro-risk code should remain a reference only or can be safely reused

### Step 2b — Verify artifact shape (critical for AC-5)

Before writing any fallback code, document the exact artifact shape the yFinance path must produce:

```bash
ls market_data/packages/latest/
head -5 market_data/packages/latest/EURUSD_1h_latest.csv
cat market_data/packages/latest/EURUSD_hot.json
```

**Windows:**
```cmd
dir market_data\packages\latest\
```

Report: exact CSV column order and manifest JSON schema. The yFinance fallback must produce identical shape — the officer loader reads without modification. A shape mismatch here breaks AC-5 and AC-6 silently.

### Step 3 — Verify baseline relay still holds
Run the existing test suite and confirm the current baseline remains green before any changes.

Expected baseline:
- current relay and registry tests pass
- no regressions before patching

### Step 4 — Decide switchover shape
Report which of these is the smallest viable runtime design:

1. **fallback only**
   - Dukascopy default, yFinance only on failure
2. **global provider mode + fallback**
   - one runtime setting, with fallback policy
3. **per-instrument provider preference**
   - only if diagnostics show it is already nearly free

The preferred answer should be the **smallest safe option**.

### Step 4b — yFinance client strategy

After deciding switchover shape, report which implementation path is cleaner:

**Option A (preferred if clean):** Write a minimal `_fetch_yfinance(instrument, start, end)` function directly inside `market_data_officer/feed/` — self-contained, no cross-module dependency.

**Option B:** Import and reuse the existing `macro_risk_officer/ingestion/clients/price_client.py` yFinance client — only if the interface is stable and the import does not create an unclean cross-package dependency.

The diagnostic should recommend one option before any code is written.

### Step 5 — Define test strategy before code
Report how acceptance will be proven with:
- fixture/mocked tests as the backbone
- optional manual live smoke only if helpful

No code until the smallest patch set is approved.

---

## 8. Implementation Constraints

### 8.1 General rule
This is a **runtime provider policy phase**, not a broad ingestion redesign.

The implementer should prefer:
- using the existing registry
- keeping one small provider-routing policy layer
- preserving existing artifact shape
- mocking provider failure/success in tests
- keeping Dukascopy-first behavior as the default

The implementer should avoid:
- a full plugin/provider framework
- broad cross-package coupling
- rewriting feed/export/officer contracts
- introducing live-network dependencies into the core test suite

### 8.1b Implementation Sequence

For a runtime behavior change, regression gates matter more than for a config refactor.

1. Confirm yFinance importable and artifact shape documented (Steps 1–2b)
2. Write yFinance fetch function (Option A or B) — **do not wire fallback yet**
3. Verify **404/404 still pass** — fetch function exists but is not called
4. Insert fallback trigger at the single identified insertion point in `feed/pipeline.py`
5. Verify **404/404 still pass** with fallback path inactive (Dukascopy primary unchanged)
6. Add deterministic fallback tests: mock Dukascopy empty → yFinance called → artifacts written → packet assembled (EURUSD + XAUUSD)
7. Verify **404+ pass**

Do not skip Step 3 or Step 5. These confirm the refactor is non-breaking before and after wiring.

### 8.2 Allowed change surface
Expected allowed areas:

```text
market_data_officer/instrument_registry.py     # alias lookup — read only
market_data_officer/run_feed.py
market_data_officer/feed/config.py
market_data_officer/feed/pipeline.py           # fallback insertion point
market_data_officer/feed/yfinance_client.py    # new minimal fetch (Option A) — preferred unless diagnostics prove macro_risk_officer reuse is cleaner and dependency-safe
market_data_officer/tests/conftest.py
market_data_officer/tests/test_provider_switchover.py  # new — fallback tests
```

Possible addition:
- one small provider policy/helper file inside `market_data_officer/` if diagnostics justify it

### 8.3 Out of scope
- analyst graph redesign
- new DB layer
- scheduler / cron
- UI/frontend work
- broad “all providers for all assets” framework
- changing `MarketPacketV2`

---

## 9. Success Definition

> **Provider Switchover is done when:**
> the repo has one explicit provider-selection policy → Dukascopy remains the default behavior → yFinance fallback is available in a controlled way using existing alias metadata → existing artifact and packet contracts remain unchanged → deterministic tests prove the behavior without live dependency → optional live smoke remains non-blocking → no SQLite introduced → no new top-level module created.

This is the same relay discipline as earlier phases, but now applied to **runtime provider behavior** rather than just metadata normalization.

---

## 10. Why This Phase Matters

Without Provider Switchover:
- alias metadata remains passive
- provider failure handling remains implicit or absent
- extending the system to more instruments still risks operational fragility
- the repo remains Dukascopy-dependent in runtime terms even though the metadata layer is ready for more

With Provider Switchover:
- the registry becomes operational, not just structural
- provider behavior becomes explicit
- fallback policy becomes auditable
- future instrument expansion becomes less brittle

---

## 11. Diagnostic Findings

*To be populated after running the pre-code diagnostic protocol (Section 7).*

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1A | EURUSD baseline spine | ✅ Done |
| Phase 1B | XAUUSD baseline spine | ✅ Done |
| Phase E+ | Additional instruments / provider abstraction | ✅ Done |
| Provider Switchover | yFinance fallback / per-instrument switching | ⏳ Next |
| Operationalise | Scheduler / APScheduler integration | Out of scope for this phase |

---

## 13. Recommended Agent Prompt

Read `docs/Provider_Switchover_Spec.md` (or this draft) and treat it as the controlling spec for this pass.

First task only:
run the diagnostic protocol in Section 7 and report gaps before changing any code.

I want:
- a map of where provider-selection logic currently lives
- a repo-vs-spec comparison
- a gap list against AC-1 through AC-12
- the smallest patch plan to activate yFinance fallback / provider switchover without breaking current Dukascopy-first relay behavior

Hard constraints:
- no SQLite
- no new top-level module
- no scheduler
- preserve current artifact and `MarketPacketV2` contracts
- deterministic tests remain the required acceptance backbone
- live provider checks are optional diagnostics only

Do not code until the diagnostic report is complete and reviewed.

---

*Drafted from the closed Phase 1A / 1B / E+ specs and current project baseline on 8 March 2026.*
