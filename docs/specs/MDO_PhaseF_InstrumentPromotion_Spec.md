# Instrument Promotion Spec — GBPUSD / XAGUSD / XPTUSD Relay Proof & Trust-Level Promotion

**Status:** ✅ Complete
**Date:** 8 March 2026 (drafted) · 9 March 2026 (closed)
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`

---

## 1. Purpose

Instrument Promotion is the next phase after the closed:

- **Phase 1A** — EURUSD baseline spine
- **Phase 1B** — XAUUSD baseline spine
- **Phase E+** — instrument/provider metadata normalization
- **Provider Switchover** — controlled yFinance fallback for trusted instruments

Those phases proved:

1. the deterministic file-based relay from feed artifacts → officer → `MarketPacketV2` → analyst consumption
2. the relay for two trusted instruments (**EURUSD**, **XAUUSD**)
3. a shared `instrument_registry` / metadata layer
4. controlled provider fallback and provenance handling

This phase is not about adding a new routing layer. Its purpose is to **close the unverified-instrument gap** by proving which additional instruments are ready to be promoted from `unverified` to `provisional` or `trusted`.

Target instruments for this phase:

- **GBPUSD**
- **XAGUSD**
- **XPTUSD**

---

## 2. Scope

### In scope

- proving the deterministic relay for the currently unverified instruments:
  - `GBPUSD`
  - `XAGUSD`
  - `XPTUSD`
- validating fixture realism and packet plausibility per instrument
- validating officer packet assembly for each candidate instrument
- validating analyst consumption using injected packets and mocked LLM calls
- defining promotion rules for moving an instrument from:
  - `unverified` → `provisional`
  - or `unverified` → `trusted`
- updating trust levels only if acceptance gates are satisfied

### Out of scope

- no new top-level module
- no SQLite / database layer
- no scheduler / cron / APScheduler work
- no analyst graph redesign
- no UI redesign
- no `MarketPacketV2` contract redesign unless diagnostics prove a real incompatibility
- no broad provider-routing redesign
- no “any asset” universalization in this phase
- no live provider dependency as a required test gate

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|------------|
| Runtime artifacts | remain under `market_data/` |
| Storage model | file-based spine only |
| Officer contract | `build_market_packet()` / `refresh_from_latest_exports()` returning `MarketPacketV2` |
| Proven trusted instruments | EURUSD, XAUUSD |
| Current unverified instruments | GBPUSD, XAGUSD, XPTUSD |
| Registry status | centralized instrument metadata already exists |
| Fallback status | provider switchover/fallback exists where already approved |
| Test philosophy | deterministic fixture/mock tests remain the required acceptance backbone |
| Live-provider checks | optional manual smoke only, not required CI/phase gate |

### Candidate Instrument Reference

| Instrument | Family | Current Trust Level | Dukascopy Ticker | yFinance Alias | Timeframes | Promotion Hypothesis |
|------------|--------|--------------------|-----------------:|----------------|------------|---------------------|
| GBPUSD | FX | `"unverified"` | `GBPUSD` | `GBPUSD=X` | 15m, 1h, 4h, 1d | `"provisional"` or `"trusted"` |
| XAGUSD | Metals | `"unverified"` | `XAGUSD` | `SI=F` | 15m, 1h, 4h, 1d | `"provisional"` or `"trusted"` |
| XPTUSD | Metals | `"unverified"` | `XPTUSD` | `PL=F` | 15m, 1h, 4h, 1d | `"provisional"` or `"trusted"` |

> Promotion hypotheses are starting estimates only — diagnostic findings determine the actual outcome. All Phase E+ registry values (`base_price`, `volatility`, `volume_range`, `price_range`) were set as starting estimates and must be validated in Step 1 of the diagnostic before fixture tests are run.

### Strategic outcome

After this phase, the repo should know which of the currently unverified instruments are:

- still `unverified`
- safe to mark `provisional`
- or safe to mark `trusted`

based on evidence from the same relay discipline used in earlier phases.

---

## 4. Key Files Likely in Scope

The exact list must be confirmed by diagnostics, but likely in-scope files include:

```text
market_data_officer/instrument_registry.py
market_data_officer/run_feed.py
market_data_officer/tests/conftest.py
market_data_officer/tests/
docs/specs/README.md
docs/AI_TradeAnalyst_Progress.md
```

Possible additions allowed **inside existing directories only**:
- one new promotion-focused test file under `market_data_officer/tests/`
- small fixture/helper changes if diagnostics show they are needed

No new top-level directory is allowed.

---

## 5. Current State Audit Hypothesis

This section is a starting hypothesis only. Diagnostics must confirm or reject it.

### What is already true
- EURUSD relay proof exists
- XAUUSD relay proof exists
- registry metadata exists for GBPUSD, XAGUSD, XPTUSD
- deterministic fixture seeding already exists
- provider fallback and provenance handling already exist
- the packet/analyst relay is stable enough to test new instruments

### Note on registry values
Phase E+ set `base_price`, `volatility`, `volume_range`, and `price_range` for these instruments as **starting estimates**, not validated values. The diagnostic Step 1 must confirm or correct them before any fixture tests are run as acceptance gates. Treating unvalidated estimates as authoritative risks passing tests against implausible synthetic data.

### What likely remains unknown
- whether fixture defaults for GBPUSD, XAGUSD, XPTUSD are realistic enough
- whether price plausibility ranges are sufficient for promotion
- whether structure tolerances / imbalance thresholds behave sensibly for those instruments
- whether each candidate instrument should become `provisional` or `trusted`
- whether all three should be promoted in the same phase

### Core Instrument Promotion question

Which of the currently unverified instruments can be promoted based on deterministic relay proof and plausibility checks, without introducing speculative trust?

---

## 6. Promotion Rules

Promotion should be evidence-based.

### Promotion to `provisional`
An instrument may be promoted to `provisional` if:
- fixture/artifact/packet/analyst relay is proven deterministically
- metadata and plausibility checks pass
- but live-provider confidence or structure-level confidence is still limited

### Promotion to `trusted`
An instrument may be promoted to `trusted` only if:
- deterministic relay is proven
- plausibility checks are strong
- no known material ambiguity remains in metadata or packet behavior
- diagnostics indicate parity with the already trusted instrument pattern for its family

### Keep `unverified`
If an instrument fails relay proof, plausibility checks, or reveals unresolved ambiguity, it remains `unverified`.

---

## 7. Acceptance Criteria

Before writing any code, diagnostics must report which of these are already true and which are not.

| Gate / Check | Acceptance Condition | Status |
|-------------|----------------------|--------|
| AC-1: fixture seeding works | `run_feed.py --fixture --instrument <instrument>` completes cleanly for each candidate instrument | ✅ Done |
| AC-2: artifact shape correct | latest package artifacts are written in the expected canonical shape for each candidate instrument | ✅ Done |
| AC-3: packet assembly works | `refresh_from_latest_exports("<instrument>")` returns valid `MarketPacketV2` for each candidate instrument | ✅ Done |
| AC-4: timeframe coverage correct | packet includes the expected timeframe set for each instrument family | ✅ Done |
| AC-5: price plausibility holds | OHLC ranges are plausible for each candidate instrument according to registry/config rules | ✅ Done |
| AC-6: analyst consumption works | `run_analyst()` can consume injected packets for each candidate instrument without crash (LLM mocked) | ✅ Done |
| AC-7: promotion decision justified | each candidate instrument ends the phase with an explicit result: remain unverified / promote provisional / promote trusted | ✅ Done |
| AC-8: deterministic tests | acceptance is proven by deterministic fixture/mock tests, not live provider dependency | ✅ Done |
| AC-9: regression safety | existing EURUSD/XAUUSD relay tests still pass | ✅ Done |
| AC-10: no SQLite | no SQLite or DB layer introduced | ✅ Done |
| AC-11: no new top-level module | work stays inside existing repo/module boundaries | ✅ Done |
| AC-12: no scheduler | no scheduling/orchestration automation introduced | ✅ Done |

---

## 8. Pre-Code Diagnostic Protocol

Before changing code, the implementer must run these checks and report findings.

### Step 1 — Check registry coverage for target instruments
Inspect `instrument_registry` and report for each candidate instrument:
- trust level
- timeframes
- price range / scale
- fixture defaults
- alias/provider metadata
- structure tolerances

Expected result:
a side-by-side table for GBPUSD, XAGUSD, XPTUSD.

### Step 2 — Verify current fixture path
Run fixture seeding and report:
- whether artifacts are written
- whether generated prices/volumes look plausible
- whether timeframe sets are correct

### Step 3 — Verify packet path
For each candidate instrument:
- call `refresh_from_latest_exports("<instrument>")`
- report whether `MarketPacketV2` is returned
- report timeframe presence and basic packet plausibility

### Step 4 — Verify analyst consumption
For each candidate instrument:
- inject the packet into the analyst path with mocked LLM
- confirm no crash
- confirm structured result path still works

### Step 5 — Recommend promotion outcome
For each instrument, report one of:
- remain `unverified`
- promote to `provisional`
- promote to `trusted`

No code until the smallest patch set is approved.

---

## 9. Implementation Constraints

### 9.1 General rule
This is an **evidence-and-promotion phase**, not a redesign phase.

The implementer should prefer:
- using the existing registry and relay
- proving behavior instrument by instrument
- making only the smallest metadata/test changes needed
- promoting trust levels only where justified

The implementer should avoid:
- blanket promotion of all unverified instruments
- speculative trust-level changes
- adding new routing abstractions
- broad contract changes

### 9.1b Implementation Sequence

Process instruments sequentially — a failure on one should not block promotion of another.

1. Validate and correct registry values if needed (Step 1) — do not run fixture tests until base_price/volatility/price_range are plausible
2. Verify **404/404 baseline** green
3. Prove GBPUSD: fixture → artifact → packet → analyst consumption
4. Verify **404+** pass
5. Prove XAGUSD: fixture → artifact → packet → analyst consumption
6. Verify **404+** pass
7. Prove XPTUSD: fixture → artifact → packet → analyst consumption
8. Verify **404+** pass
9. Update `trust_level` in registry for each instrument based on findings
10. Verify **404+** final gate

Each instrument should have isolated promotion coverage, preferably in its own test file unless diagnostics show a single well-structured promotion test module is cleaner. A regression gate after each instrument confirms the relay contract is not being broken incrementally.

### 9.2 Allowed change surface
Expected allowed areas:

```text
market_data_officer/instrument_registry.py
market_data_officer/run_feed.py
market_data_officer/tests/conftest.py
market_data_officer/tests/
```

Possible additions:
- one promotion-focused test file inside `market_data_officer/tests/`
- small metadata adjustments if diagnostics prove they are needed

### 9.3 Out of scope
- analyst graph redesign
- new DB layer
- scheduler / cron
- UI/frontend work
- broad provider-routing redesign
- changing `MarketPacketV2`

---

## 10. Success Definition

> **Instrument Promotion is done when:**
> GBPUSD, XAGUSD, and XPTUSD have each been evaluated through the deterministic relay → fixture/artifact/packet/analyst-consumption behavior is proven or rejected explicitly → each instrument receives an evidence-based trust decision (`unverified`, `provisional`, or `trusted`) → existing trusted-instrument tests still pass → no SQLite introduced → no new top-level module created.

This phase is successful if it reduces ambiguity, even if not all three instruments are promoted.

---

## 11. Why This Phase Matters

Without Instrument Promotion:
- the registry contains instruments whose status is still speculative
- provider routing decisions for those instruments remain premature
- future operational choices stay theoretical

With Instrument Promotion:
- trust levels become evidence-based
- future per-instrument provider routing becomes meaningful
- future asset expansion follows a repeatable standard

---

## 12. Diagnostic Findings

### Registry values — confirmed correct, no corrections needed

| Field | GBPUSD | XAGUSD | XPTUSD |
|-------|--------|--------|--------|
| price_scale | 100,000 | 1,000 | 1,000 |
| price_range | (1.15, 1.45) | (18.00, 40.00) | (700.00, 1,400.00) |
| base_price | 1.2700 | 28.00 | 980.00 |
| fixture_volatility | 0.0005 | 0.15 | 3.00 |
| fixture_volume_range | (100, 5000) | (0.1, 50.0) | (0.01, 5.0) |
| timeframes | 6 (FX set) | 4 (metals set) | 4 (metals set) |
| yfinance_alias | GBPUSD=X | SI=F | PL=F |
| eqh_eql_tolerance | 0.00010 | 0.10 | 0.50 |
| fvg_min_size | 0.0003 | 0.05 | 0.30 |

All values are plausible and internally consistent with family baselines (GBPUSD ↔ EURUSD, XAGUSD/XPTUSD ↔ XAUUSD).

### Spec discrepancy — GBPUSD timeframes

The §3 candidate table listed GBPUSD with 4 timeframes (15m, 1h, 4h, 1d). The registry assigns `_FX_TIMEFRAMES` = 6 TFs (1m, 5m, 15m, 1h, 4h, 1d), which is structurally correct — GBPUSD is FX, not metals. The registry is treated as source of truth; the spec table was a drafting error.

### Plausibility assessment

All 3 instruments passed deterministic price-range plausibility tests using registry `price_range` bounds. Every generated OHLC value falls within the declared range. Fixture volatility and volume ranges are internally consistent with their family baselines.

### AC gap table (pre-implementation)

| AC | Pre-impl status | Gap |
|----|----------------|-----|
| AC-1 through AC-6 | Infrastructure existed but no tests | No conftest fixtures; no relay tests for GBPUSD/XAGUSD/XPTUSD |
| AC-7 | No promotion decision recorded | trust_level still "unverified" |
| AC-8 | Infra deterministic | Gap: no test file |
| AC-9 | 404/404 green | No gap |
| AC-10–12 | Constraints held | No gap |

### Final patch set

| File | Change | Delta |
|------|--------|-------|
| `market_data_officer/instrument_registry.py` | trust_level: "unverified" → "trusted" for GBPUSD, XAGUSD, XPTUSD | 3 lines changed |
| `market_data_officer/tests/conftest.py` | Generic `_instrument_hot_packages()` helper + 3 new fixtures | +42 lines |
| `market_data_officer/tests/test_promotion_relay.py` | **New file** — 15 tests across 6 classes | +213 lines |
| `market_data_officer/tests/test_phase_e_registry.py` | Updated trust-level assertions for promoted instruments | 4 lines changed |
| `market_data_officer/tests/test_contracts.py` | Changed unverified-instrument test to use NZDUSD (GBPUSD now trusted) | 1 line changed |
| `docs/specs/MDO_PhaseF_InstrumentPromotion_Spec.md` | Closed spec | doc only |
| `docs/specs/README.md` | Updated completed/current phase | doc only |
| `docs/AI_TradeAnalyst_Progress.md` | Updated progress table | doc only |

### Regression gate results

| Gate | Test count | Result |
|------|-----------|--------|
| Baseline (pre-work) | 404/404 | ✅ Green |
| After relay tests added | 419/419 | ✅ Green |
| After all 3 promotions | 419/419 | ✅ Green |

### Trust-level decisions

| Instrument | Decision | Justification |
|------------|----------|---------------|
| **GBPUSD** | `unverified` → `trusted` | Structurally identical to trusted EURUSD: same price_scale (100k), same 6 TFs, same tolerance/FVG values. Full relay proven: fixture → artifact → packet → analyst. All prices within declared range. No material ambiguity. |
| **XAGUSD** | `unverified` → `trusted` | Structurally parallel to trusted XAUUSD: same price_scale (1k), same 4 TFs. Appropriately scaled tolerances for silver price level. Full relay proven. No material ambiguity. |
| **XPTUSD** | `unverified` → `trusted` | Structurally parallel to trusted XAUUSD: same price_scale (1k), same 4 TFs, same tolerance values. Full relay proven. No material ambiguity. |

---

## 13. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1A | EURUSD baseline spine | ✅ Done |
| Phase 1B | XAUUSD baseline spine | ✅ Done |
| Phase E+ | Additional instruments / provider abstraction | ✅ Done |
| Provider Switchover | yFinance fallback / per-instrument switching | ✅ Done |
| Instrument Promotion | GBPUSD / XAGUSD / XPTUSD trust-level promotion | ✅ Done |
| Operationalise | Scheduler / APScheduler integration | Out of scope for this phase |

---

## 14. Recommended Agent Prompt

Read `docs/Instrument_Promotion_Spec.md` (or this draft) and treat it as the controlling spec for this pass.

First task only:
run the diagnostic protocol in Section 8 and report gaps before changing any code.

I want:
- a side-by-side audit of GBPUSD / XAGUSD / XPTUSD
- a repo-vs-spec comparison
- a gap list against AC-1 through AC-12
- the smallest patch plan needed
- a proposed promotion outcome for each instrument

Hard constraints:
- no SQLite
- no new top-level module
- no scheduler
- preserve current artifact and `MarketPacketV2` contracts
- deterministic tests remain the required acceptance backbone
- no speculative promotion without evidence

Do not code until the diagnostic report is complete and reviewed.

On completion, close the spec and update docs:
1. `docs/Instrument_Promotion_Spec.md` — mark status ✅ Complete, flip all AC cells to ✅ Done, populate §12 Diagnostic Findings with: registry values found and any corrections made, plausibility assessment per instrument, AC gap table (pre-impl), final patch set (files + line delta), per-instrument regression gate results, trust_level decision with justification per instrument
2. `docs/specs/README.md` — move Instrument Promotion to Completed table, update Current Phase block to Per-Instrument Provider Routing
3. `docs/AI_TradeAnalyst_Progress.md` — update current phase, add Instrument Promotion completed row with final test count

Commit all doc changes on the same branch as the implementation.

---

*Drafted from the closed Phase 1A / 1B / E+ / Provider Switchover specs and current project baseline on 8 March 2026.*
