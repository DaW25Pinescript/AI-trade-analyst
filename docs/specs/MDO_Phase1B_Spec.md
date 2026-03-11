# Market Data Officer — Phase 1B Spec

## Repo-Aligned Implementation Target

**Project:** AI Trade Analyst
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Date:** 8 March 2026
**Status:** ✅ Complete — implemented and verified 8 March 2026 (364/364 tests, zero regressions)

**Context:** Phase 1A proved the deterministic relay from feed artifacts into analyst consumption for EURUSD (359/359 tests). Phase 1B extends the same proven spine to **XAUUSD**. The decode layer, price-scale verification, instrument config, and structure engine already support XAUUSD — the remaining gap is the hot-package fixture → officer → analyst relay proof.

---

## 1. Scope & Constraints

### 1.1 What Phase 1B Is

- Prove `run_feed.py --fixture --instrument XAUUSD` writes valid XAUUSD hot-package artifacts
- Prove `refresh_from_latest_exports("XAUUSD")` returns a valid `MarketPacketV2`
- Prove `run_analyst()` consumes a XAUUSD packet without crashing
- Fix the fixture seeder to use instrument-appropriate base prices and volatility
- Add targeted relay tests mirroring Phase 1A's pattern for XAUUSD
- Lock the contract with tests

### 1.2 What Phase 1B Is NOT

Hard constraints — do not violate:

- ❌ Do not create a new top-level module — work inside `market_data_officer/` only
- ❌ Do not introduce SQLite — file-based spine (Parquet/CSV) is canonical
- ❌ Do not build a scheduler — CLI/manual trigger only in this phase
- ❌ Do not change the analyst graph architecture — packet injection path already exists
- ❌ Do not change the officer contract — `MarketPacketV2` schema is locked
- ❌ Do not change the decode layer — XAUUSD decode is already verified (Phase 1B pre-work, 2026-03-06)

---

## 2. Repo-Aligned Assumptions

Derived from actual codebase state — cross-referenced against Phase 1A baseline.

| Key | Value |
|-----|-------|
| Runtime artifacts root | `market_data/` (created at runtime) |
| Canonical / derived storage | Parquet/CSV via pipeline — no SQLite |
| Hot package location | `market_data/packages/latest/` |
| Instrument | `XAUUSD` |
| Price scale | 1,000 (raw ticks ÷ 1000 = USD price) |
| Plausible price range | $1,500–$3,500 (enforced in `feed/config.py`) |
| Target timeframe set | `15m`, `1h`, `4h`, `1d` |
| Ingestion trigger | CLI / manual — `run_feed.py` |
| Contract path | `build_market_packet()` / `refresh_from_latest_exports()` |
| Packet schema | `MarketPacketV2` in `officer/contracts.py` |
| Analyst consumption path | `run_analyst()` → `build_market_packet()` if no packet injected |
| Provider (primary) | Dukascopy (bi5 format) — same as EURUSD |
| Trust level | TRUSTED (already in `TRUSTED_INSTRUMENTS` set) |
| EQH/EQL tolerance | 0.50 USD (vs EURUSD 0.00010) |
| FVG min size | 0.30 USD (vs EURUSD 0.0003) |
| Decode verification | ✅ Verified 2026-03-06 against pricegold.net and bullion-rates.com |

---

## 3. Key File Paths

| Role | Path |
|------|------|
| CLI entrypoint | `market_data_officer/run_feed.py` |
| Feed pipeline | `market_data_officer/feed/pipeline.py` |
| Feed config (instruments) | `market_data_officer/feed/config.py` |
| Decode layer | `market_data_officer/feed/decode.py` |
| Officer service | `market_data_officer/officer/service.py` |
| Officer loader | `market_data_officer/officer/loader.py` |
| Packet schema | `market_data_officer/officer/contracts.py` |
| Structure config | `market_data_officer/structure/config.py` |
| Tests | `market_data_officer/tests/` |
| Phase 1A relay tests (reference) | `market_data_officer/tests/test_phase1a_relay.py` |
| Existing XAUUSD decode tests | `market_data_officer/tests/test_xauusd.py` |
| Existing XAUUSD structure tests | `market_data_officer/tests/test_structure_xauusd.py` |

---

## 4. Current State Audit

### 4.1 What Already Works for XAUUSD

- `XAUUSD` is registered in `INSTRUMENTS` with `price_scale=1_000` (`feed/config.py`)
- `XAUUSD` is in `TRUSTED_INSTRUMENTS` (`officer/service.py`)
- `PRICE_RANGES["XAUUSD"]` is set to `(1_500.0, 3_500.0)` (`feed/config.py`)
- Decode layer verified for XAUUSD bi5 format (`feed/decode.py`)
- Structure engine supports XAUUSD with instrument-specific tolerances (`structure/config.py`)
- `run_feed.py` accepts `--instrument XAUUSD` for both `--fixture` and live feed modes
- `refresh_from_latest_exports()` accepts any instrument string — not EURUSD-specific
- 51+ XAUUSD-specific tests exist across decode and structure suites
- AI analyst fixture exists (`ai_analyst/tests/fixtures/xauusd_sample_run.json`)

### 4.2 Known Gap — Fixture Seeder Uses EURUSD-Specific Prices

⚠️ `_seed_fixture()` in `run_feed.py` uses hardcoded `base_price = 1.0850` and `volatility = 0.0005`. These are EURUSD values. When seeding XAUUSD:

- Generated prices will be ~$1.08 instead of ~$2,700
- This will likely fail `PRICE_RANGES["XAUUSD"]` validation ($1,500–$3,500) during quality checks
- Volume characteristics may also be unrealistic (XAUUSD volumes are naturally smaller)

This is the **primary code gap** for Phase 1B.

### 4.3 Known Gap — conftest.py Fixtures Are EURUSD-Only

The `hot_packages_dir` fixture in `conftest.py` hardcodes EURUSD base prices. If Phase 1B relay tests need a conftest-level XAUUSD fixture, this must be extended.

### 4.4 Gap Summary

| Gap | Type | Impact |
|-----|------|--------|
| Fixture seeder uses EURUSD base price/volatility | Code defect | XAUUSD fixture artifacts will have wrong prices |
| conftest.py lacks XAUUSD hot-package fixture | Test gap | No conftest-level XAUUSD fixture for relay tests |
| No XAUUSD relay integration test | Test gap | Officer → analyst relay unproven for XAUUSD |
| No XAUUSD fixture CLI verification | Verification gap | `--fixture --instrument XAUUSD` unverified end-to-end |

---

## 5. Phase 1B Acceptance Criteria

Before writing any code, run diagnostics against each gate. Report which are currently failing and why.

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | `run_feed.py --fixture` | Completes successfully for XAUUSD with no unhandled exceptions | ✅ Done |
| AC-2 | Artifact writes | Expected hot-package artifacts written under `market_data/packages/latest/` with XAUUSD prefix | ✅ Done |
| AC-3 | MarketPacketV2 | `refresh_from_latest_exports("XAUUSD")` returns valid MarketPacketV2 (no FileNotFoundError, no price-range violation) | ✅ Done |
| AC-4 | Timeframe coverage | MarketPacketV2 includes all 4 expected timeframes: `15m`, `1h`, `4h`, `1d` | ✅ Done |
| AC-5 | Price plausibility | All OHLC values in fixture data fall within `PRICE_RANGES["XAUUSD"]` ($1,500–$3,500) | ✅ Done |
| AC-6 | Analyst consumption | `run_analyst()` completes and returns a structured result without FileNotFoundError or packet-schema exception — packet schema is validated, not just non-null | ✅ Done |
| AC-7 | Contract tests | Two targeted tests pass: **Test A** (officer relay) — seed XAUUSD fixture → `refresh_from_latest_exports("XAUUSD")` → assert valid MarketPacketV2 → assert 4 timeframes (15m, 1h, 4h, 1d) → assert prices in range. **Test B** (analyst consumption) — call `run_analyst()` with injected XAUUSD packet + mocked LLM → assert no crash / structured result returned. Deterministic with no live LLM or provider dependency. | ✅ Done |
| AC-8 | No SQLite | No SQLite introduced — confirmed by `grep -r sqlite market_data_officer/` | ✅ Done |
| AC-9 | No new module | No new top-level module — work confined to `market_data_officer/` | ✅ Done |
| AC-10 | No regressions | All pre-existing tests (359+) remain green | ✅ Done |

---

## 6. Pre-Code Diagnostic Protocol

Run these steps before changing any code. Report findings against AC-1 through AC-10 first.

### Step 1 — Verify XAUUSD hot-package artifacts

```bash
ls market_data/packages/latest/XAUUSD*
```

Expected: `XAUUSD_hot.json` manifest + 4 CSV files (`XAUUSD_15m_latest.csv`, etc.). If missing: fixture has not been seeded — proceed to Step 2.

### Step 2 — Run the fixture seeder for XAUUSD

```bash
python market_data_officer/run_feed.py --instrument XAUUSD --fixture
```

Expected: completes without error. Check: do the generated CSV files contain prices in the $1,500–$3,500 range? If prices are ~$1.08: the fixture seeder is using EURUSD defaults.

### Step 3 — Test packet assembly directly

```bash
python -c "from market_data_officer.officer.service import refresh_from_latest_exports; pkt = refresh_from_latest_exports('XAUUSD'); print(pkt)"
```

Expected: `MarketPacketV2` printed without exception. If price-range validation fails: fixture prices are wrong (see Step 2).

### Step 4 — Run the full test suite

```bash
pytest market_data_officer/tests/ -v
```

Baseline: 359+ passing. If regressions: note which tests fail and why before touching code.

### Step 5 — Report smallest patch set

Based on Steps 1–4, list the minimum file changes needed to make AC-1 through AC-10 pass. Do not implement until this list is reviewed.

---

## 7. Implementation Constraints

### 7.1 Fixture Seeder — Instrument-Aware Pricing

The `_seed_fixture()` function in `run_feed.py` must be updated to use instrument-appropriate base prices and volatility:

| Parameter | EURUSD | XAUUSD |
|-----------|--------|--------|
| `base_price` | 1.0850 | 2700.00 |
| `volatility` | 0.0005 | 2.00 |
| `volume range` | 100–5000 | 0.1–10.0 |

Implementation approach: add a simple lookup dict keyed by instrument inside `_seed_fixture()`. No new module, no new config file.

**Strict fixture scope for XAUUSD:** the fixture seeder must write **only the 4 target timeframes** (`15m`, `1h`, `4h`, `1d`) when `--instrument XAUUSD`. Writing 6 TFs and asserting on 4 is not acceptable — it weakens the phase boundary and makes AC-2, AC-4, and AC-7 harder to reason about. The diagnostic confirmed a "superficial pass" risk once already; keep the patch surgical.

### 7.2 Test Fixture — conftest.py Extension

Add an `xauusd_hot_packages_dir` fixture (or parametrize the existing `hot_packages_dir`) using XAUUSD-appropriate price/volume values. Must use the same manifest/CSV shape as the existing EURUSD fixture.

### 7.3 Code Change Surface

Restrict changes to:

```
market_data_officer/run_feed.py               # instrument-aware pricing in _seed_fixture()
market_data_officer/tests/conftest.py          # XAUUSD hot-package fixture
market_data_officer/tests/test_phase1b_relay.py  # new — XAUUSD relay + consumption tests
```

### 7.4 Out of Scope

- `ai_analyst/` — analyst graph internals (packet injection path already exists)
- `market_data_officer/feed/decode.py` — XAUUSD decode already verified
- `market_data_officer/feed/config.py` — XAUUSD instrument config already present
- `market_data_officer/officer/service.py` — XAUUSD already in TRUSTED_INSTRUMENTS
- `market_data_officer/structure/` — XAUUSD structure config already present
- Any new top-level directory
- Any database layer
- Any scheduler or cron

---

## 8. Success Definition

Phase 1B is done when:

`run_feed.py --fixture --instrument XAUUSD` writes XAUUSD artifacts with plausible prices → `refresh_from_latest_exports("XAUUSD")` returns valid `MarketPacketV2` → `run_analyst()` consumes it without crashing → all 4 timeframes present (15m, 1h, 4h, 1d) → prices within $1,500–$3,500 → targeted tests pass → 359+ tests green → no SQLite introduced → no new module created.

This is the same relay race as Phase 1A: feed → hot-package → officer → analyst. Phase 1B is proven when each handoff is confirmed by a test for XAUUSD specifically.

---

## 9. Why Phase 1B Should Be Faster Than Phase 1A

- The spine is already proven end-to-end for EURUSD
- The officer contract (`MarketPacketV2`) is locked
- The fixture pattern (`--fixture`) already exists
- The analyst packet-consumption path is already proven
- XAUUSD decode, config, and structure support are already implemented and verified
- XAUUSD is already in `TRUSTED_INSTRUMENTS`
- The only code gaps are: fixture pricing defaults and test coverage

Expected patch size: ~30–50 lines across 3 files (vs ~100–130 lines for Phase 1A).

---

## 10. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1A | EURUSD baseline spine | ✅ Done — 359/359 tests |
| Phase 1B | XAUUSD spine (this spec) | ✅ Done — 364/364 tests |
| Phase E+ | Additional instruments, provider abstraction, alias config | ⏳ Next |
| Operationalise | Scheduler / APScheduler integration | Out of scope for 1B |

---

## 11. Diagnostic Findings (8 March 2026)

> **Historical record — pre-implementation diagnostics only.** These were the gaps found before any code was changed. All ACs are now ✅ Done (see Section 5).

**Root cause:** `_seed_fixture()` hardcodes `base_price = 1.0850` and `volatility = 0.0005` (EURUSD values) regardless of instrument. No price-range validation fires at packet-build time — wrong prices produce a plausible-looking but incorrect packet.

**Additional finding:** The officer service does not gate on `PRICE_RANGES` at packet-build time. AC-5 (price plausibility) is therefore the only gate catching this — making it a critical test, not a sanity check.

| AC | Status | Finding |
|----|--------|---------|
| AC-1 | PASS (superficial) | No crash, but prices are EURUSD-scale (~$1.08) |
| AC-2 | PASS (superficial) | 6 CSV files written — wrong TF count + wrong prices |
| AC-3 | PASS (superficial) | No exception, but prices ~$1.08 not ~$2,700 |
| AC-4 | PASS | All 4 target TFs present (plus extra 1m, 5m outside scope) |
| AC-5 | **FAIL** | All OHLC values ~$1.08 — outside $1,500–$3,500 range |
| AC-6 | UNTESTED | No XAUUSD analyst consumption test exists |
| AC-7 | **FAIL** | `test_phase1b_relay.py` does not exist |
| AC-8 | PASS | `grep -r sqlite market_data_officer/` returns nothing |
| AC-9 | PASS | All work inside `market_data_officer/` |
| AC-10 | PASS | 359/359 green baseline confirmed |

**Approved patch set:**

| File | Change | Resolves |
|------|--------|---------|
| `market_data_officer/run_feed.py` | Instrument-keyed lookup for `base_price`, `volatility`, `volume_range`. XAUUSD: `base_price=2700.0`, `volatility=2.0`, `volume_range=(0.1, 10.0)`. Write **only 4 TFs** (`15m`, `1h`, `4h`, `1d`) for XAUUSD. | AC-1, AC-2, AC-3, AC-5 |
| `market_data_officer/tests/conftest.py` | Add `xauusd_hot_packages_dir` fixture with XAUUSD prices (~$2,700), volumes, and 4 TFs only | AC-7 prerequisite |
| `market_data_officer/tests/test_phase1b_relay.py` | New: Test A (officer relay, assert 4 TFs + prices in range) + Test B (analyst consumption, injected packet + mocked LLM) | AC-6, AC-7 |

---

*Drafted from repo state, closed Phase 1A spec, and progress plan baseline on 8 March 2026.*

---

## Appendix — Implementation Prompt

```
Read `docs/specs/MDO_Phase1B_Spec.md` and treat it as the controlling spec for this pass.

Diagnostic report is complete (see Section 11). Approved patch set:

Patch 1 — market_data_officer/run_feed.py:
- Add instrument-keyed lookup dict in _seed_fixture() for base_price, volatility, volume_range
- XAUUSD: base_price=2700.0, volatility=2.0, volume_range=(0.1, 10.0)
- Write ONLY 4 TFs (15m, 1h, 4h, 1d) for XAUUSD — not 6

Patch 2 — market_data_officer/tests/conftest.py:
- Add xauusd_hot_packages_dir fixture with XAUUSD-appropriate prices (~$2,700),
  volumes, and 4 TFs only. Same manifest/CSV shape as existing hot_packages_dir.

Patch 3 — market_data_officer/tests/test_phase1b_relay.py (new file):
- Test A (officer relay): seed XAUUSD fixture → refresh_from_latest_exports("XAUUSD")
  → assert valid MarketPacketV2 → assert exactly 4 TFs (15m, 1h, 4h, 1d)
  → assert all OHLC prices within $1,500–$3,500
- Test B (analyst consumption): run_analyst() with injected XAUUSD packet
  + mocked LLM → assert structured AnalystOutput returned without exception

Hard constraints:
- no SQLite, no new top-level module, no scheduler
- changes inside market_data_officer/ only
- do not touch decode.py, config.py, service.py, structure/ — all verified correct
- MarketPacketV2 contract locked — no schema changes
- fixture must write exactly 4 TFs for XAUUSD — asserting on 4 while writing 6 is not acceptable

After implementing, run: pytest market_data_officer/tests/ -v
Target: 359+ tests green, both new relay tests pass, AC-5 price plausibility confirmed.
```
