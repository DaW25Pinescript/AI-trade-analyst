# Market Data Officer — Phase 1A Spec
## Repo-Aligned Implementation Target

**Project:** AI Trade Analyst  
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Date:** 8 March 2026  
**Status:** ✅ Approved — active controlling spec for Phase 1A

> **Context:** Smoke path proven end-to-end (Run 7 ✅). Analysts currently receive no real market data — they reason from prompt context only. Phase 1A closes this gap by feeding a real `MarketPacketV2` into the analyst graph.

---

## 1. Scope & Constraints

### 1.1 What Phase 1A Is

- Integrate the existing `market_data_officer/` module into the proven analyst pipeline
- Produce real hot-package artifacts for EURUSD via the file-based spine
- Prove that `refresh_from_latest_exports()` returns a valid `MarketPacketV2`
- Prove that `run_analyst()` consumes a real packet without crashing
- Add targeted tests to lock the contract

### 1.2 What Phase 1A Is NOT

> **Hard constraints — do not violate:**

- ❌ Do not create a new top-level module — work inside `market_data_officer/` only
- ❌ Do not introduce SQLite — file-based spine (Parquet/CSV) is canonical
- ❌ Do not build a scheduler — CLI/manual trigger only in this phase
- ❌ Do not change the analyst graph architecture — packet injection path already exists

---

## 2. Repo-Aligned Assumptions

Derived from actual codebase state, not the abstract spec in section 8 of the session handoff doc.

| Key | Value |
|-----|-------|
| Runtime artifacts root | `market_data/` (created at runtime) |
| Canonical / derived storage | Parquet/CSV via pipeline — no SQLite |
| Hot package location | `market_data/packages/latest/` |
| EURUSD yFinance alias (future/optional) | `EURUSD=X` — not active in current MDO implementation |
| Target timeframe set | `1m`, `5m`, `15m`, `1h`, `4h`, `1d` |
| Ingestion trigger | CLI / manual — `run_feed.py` |
| Contract path | `build_market_packet()` / `refresh_from_latest_exports()` |
| Packet schema | `MarketPacketV2` in `officer/contracts.py` |
| Analyst consumption path | `run_analyst()` → `build_market_packet()` if no packet injected |
| Provider (primary) | Dukascopy (bi5 format) |
| Provider (yFinance) | Optional dep (`mro` group in `pyproject.toml`) — not imported by `market_data_officer/` |
| Provider (stub) | Finnhub — not present in current codebase |

---

## 3. Key File Paths

| Role | Path |
|------|------|
| CLI entrypoint | `market_data_officer/run_feed.py` |
| Feed pipeline | `market_data_officer/feed/pipeline.py` |
| Officer service | `market_data_officer/officer/service.py` |
| Officer loader | `market_data_officer/officer/loader.py` |
| Packet schema | `market_data_officer/officer/contracts.py` |
| Tests | `market_data_officer/tests/` |

---

## 4. Current State Audit

### 4.1 What Already Works

- `run_feed.py` — real CLI with `--hot-only`, `--gap-report`, `--diagnostics` modes
- `build_market_packet()` / `refresh_from_latest_exports()` — real implementations, return `MarketPacketV2`
- `MarketPacketV2` — assembles source, timeframes, features, summary, quality, structure
- `run_analyst()` — already calls `build_market_packet()` if no packet injected
- 354 tests passing green in `market_data_officer/` test suite

### 4.2 Known Failure Mode

> ⚠️ **Hard-fail path:** For trusted instruments (including EURUSD), a missing hot-package manifest propagates `FileNotFoundError` via quality checks. This is intentional behaviour — but it means analysts hard-fail in dev when feed artifacts have not been written.

Analogy: the officer (vending machine) works correctly — it refuses to dispense when the restocking truck (feed) hasn't arrived. The machine is not broken; the truck just hasn't run.

### 4.3 Gap Summary

- No in-repo Phase 1A acceptance criteria doc ← **this document is that doc**
- EURUSD hot-package artifacts may not exist in the dev environment
- No fixture/seed path for dev when yFinance/Dukascopy is unreachable
- Whether `run_feed.py` completes successfully for EURUSD has not been verified in CI

---

## 5. Phase 1A Acceptance Criteria

> Before writing any code, run diagnostics against each gate. Report which are currently failing and why.

| # | Gate | Acceptance Condition | Status |
|---|------|----------------------|--------|
| AC-1 | `run_feed.py` | Completes successfully for EURUSD baseline flow with no unhandled exceptions | ⏳ Next |
| AC-2 | Artifact writes | Expected hot-package artifacts written under `market_data/packages/latest/` | ⏳ Next |
| AC-3 | `MarketPacketV2` | `refresh_from_latest_exports("EURUSD")` returns valid `MarketPacketV2` (no `FileNotFoundError`) | ⏳ Next |
| AC-4 | Timeframe coverage | `MarketPacketV2` includes all 6 expected timeframes: `1m`, `5m`, `15m`, `1h`, `4h`, `1d` | ⏳ Next |
| AC-5 | Analyst consumption | `run_analyst()` completes and returns a structured result without `FileNotFoundError` or packet-schema exception — packet schema is validated, not just non-null | ⏳ Next |
| AC-6 | Contract tests | Two targeted tests pass: **Test A (officer relay)** — seed fixture → `refresh_from_latest_exports("EURUSD")` → assert valid `MarketPacketV2` → assert 6 timeframes. **Test B (analyst consumption)** — call `run_analyst()` with injected packet + mocked LLM → assert no crash / structured result returned. Keeps AC-6 deterministic with no live LLM or provider dependency. | ⏳ Next |
| AC-7 | No SQLite | No SQLite introduced — confirmed by `grep -r sqlite market_data_officer/` | ⏳ Next |
| AC-8 | No new module | No new top-level module — work confined to `market_data_officer/` | ⏳ Next |

---

## 6. Pre-Code Diagnostic Protocol

> **Run these steps before changing any code. Report findings against AC-1 through AC-8 first.**

### Step 1 — Verify hot-package artifacts

**POSIX:**
```bash
ls market_data/packages/latest/
```

**Windows (CMD):**
```cmd
dir market_data\packages\latest\
```

**Windows (PowerShell):**
```powershell
Get-ChildItem market_data\packages\latest\
```

Expected: manifest JSON + CSV files for EURUSD across all 6 timeframes. If missing: feed has not run — proceed to Step 2.

---

### Step 2 — Run the feed CLI

**POSIX:**
```bash
python market_data_officer/run_feed.py --instrument EURUSD --start-date 2026-03-03 --end-date 2026-03-07
```

**Windows:**
```cmd
python market_data_officer\run_feed.py --instrument EURUSD --start-date 2026-03-03 --end-date 2026-03-07
```

> **Windows note:** if running inside a venv, activate first: `.venv\Scripts\activate`
> **Date note:** `--start-date` and `--end-date` are required. Use a recent weekday range — Dukascopy returns empty payloads for weekend hours, which will produce "no data fetched" without error.

---

### Step 3 — Test packet assembly directly

**POSIX / Windows (both work from repo root with venv active):**
```bash
python -c "from market_data_officer.officer.service import refresh_from_latest_exports; print(refresh_from_latest_exports('EURUSD'))"
```

Expected: `MarketPacketV2` printed without exception. If `FileNotFoundError`: artifacts from Step 2 not written.

> **Windows note:** if import fails with `ModuleNotFoundError`, confirm `PYTHONPATH` includes repo root:
> ```cmd
> set PYTHONPATH=.
> ```

---

### Step 4 — Run the MDO test suite

**POSIX / Windows:**
```bash
pytest market_data_officer/tests/ -v
```

**Windows alternative if pytest not on PATH:**
```cmd
python -m pytest market_data_officer\tests\ -v
```

Baseline: 354 passing. If regressions: note which tests fail and why before touching code.

---

### Step 5 — Report smallest patch set

Based on Steps 1–4, list the minimum file changes needed to make AC-1 through AC-6 pass. **Do not implement until this list is reviewed.**

---

## 7. Implementation Constraints

### 7.1 Dev Environment Gap — Fixture Strategy

If yFinance/Dukascopy is unreachable during development, choose one of:

**Option A (preferred):** Pre-bake a minimal valid EURUSD hot-package fixture (small real or synthetic candle CSV + manifest JSON). Wire a `--fixture` flag on `run_feed.py` or a standalone `seed_fixture.py` script inside `market_data_officer/` that writes to `market_data/packages/latest/`. Feed code untouched; officer gets real-shaped artifacts. **The fixture must preserve the exact manifest/CSV shape expected by `refresh_from_latest_exports()` — no fake side-channel loader or alternate read path should be introduced.** The same fixture logic powers both Test A (officer relay) and Test B (analyst consumption) in AC-6.

**Option B:** Confirm yFinance is wired as default dev provider and switch EURUSD to it if Dukascopy is current primary.

**Option C (avoid):** Treat EURUSD as unverified/unknown to dodge `FileNotFoundError`. This papers over the gap rather than closing it.

### 7.2 Code Change Surface

Restrict changes to:

```
market_data_officer/run_feed.py          # CLI args, pipeline handoff only
market_data_officer/feed/                # feed pipeline internals if defects found
market_data_officer/officer/service.py   # packet assembly if gaps found
market_data_officer/officer/loader.py    # hot-package reader if gaps found
market_data_officer/officer/contracts.py # schema only if spec mismatch
market_data_officer/tests/               # new targeted tests for AC-6
```

### 7.3 Out of Scope

- `ai_analyst/` — analyst graph internals (packet injection path already exists)
- Any new top-level directory
- Any database layer
- Any scheduler or cron

---

## 8. Success Definition

> **Phase 1A is done when:**
> `run_feed.py` writes EURUSD artifacts → `refresh_from_latest_exports("EURUSD")` returns valid `MarketPacketV2` → `run_analyst()` consumes it without crashing → all 6 timeframes present → targeted tests pass → 354+ tests green → no SQLite introduced → no new module created.

This is the relay race: feed → hot-package → officer → analyst. Phase 1A is proven when each handoff is confirmed by a test, not just by running the smoke path manually.

---

## 9. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1A | EURUSD baseline spine (this spec) | ⏳ Next |
| Phase 1B+ | XAUUSD (`15m`, `1h`, `4h`, `1d`) | ⏳ Pending |
| Phase E+ | Additional instruments, provider abstraction, alias config | ⏳ Pending |
| Operationalise | Scheduler / APScheduler integration | Out of scope for 1A |

---

## 10. Diagnostic Findings (8 March 2026)

Diagnostic run completed before implementation. Root cause: no hot-package artifacts exist in dev — Dukascopy returns empty payloads on weekends. Code is not broken.

| AC | Status | Gap Type | Root Cause |
|----|--------|----------|------------|
| AC-1 | FAIL | Runtime/provider | Dukascopy weekend + spec omitted `--start-date`/`--end-date` |
| AC-2 | FAIL | Missing artifact | Blocked by AC-1 — no feed run has produced artifacts |
| AC-3 | FAIL | Missing artifact | Blocked by AC-2 — `FileNotFoundError` on missing manifest |
| AC-4 | FAIL | Missing artifact | Blocked by AC-2/AC-3 |
| AC-5 | FAIL | Missing artifact | Blocked by AC-3 + potential LLM provider dependency |
| AC-6 | PARTIAL | Test/fixture gap | 354 unit tests pass; integration relay test missing |
| AC-7 | PASS | None | Clean |
| AC-8 | PASS | None | Clean |

**Approved patch set:**

| Patch | Files | Est. Lines | Resolves |
|-------|-------|-----------|----------|
| Fixture seeding | `run_feed.py` (~20–30 lines) | ~20–30 | AC-1 through AC-5 |
| Relay + consumption tests | `tests/test_phase1a_relay.py` (new) | ~80–100 | AC-6 (both Test A + Test B) |
| Spec doc accuracy | `docs/MDO_Phase1A_Spec.md` | ~5 | Doc accuracy (provider, CLI args) |

---

## Recommended Agent Prompt

Paste this when starting the next session:

```
Read `docs/MDO_Phase1A_Spec.md` and treat it as the controlling spec for this pass.

Diagnostic report is complete (see Section 10). Approved patch set:

Patch 1 — Fixture seeding (~20–30 lines in run_feed.py):
- Add --fixture flag to run_feed.py that writes a minimal valid EURUSD hot package
  to market_data/packages/latest/ using the same shape as the existing
  conftest.py hot_packages_dir fixture. No new loader, no side-channel path.

Patch 2 — Integration tests (~80–100 lines, new file):
- Create market_data_officer/tests/test_phase1a_relay.py with two tests:
  Test A (officer relay): seed fixture → refresh_from_latest_exports("EURUSD")
    → assert valid MarketPacketV2 → assert all 6 timeframes present
  Test B (analyst consumption): call run_analyst() with injected packet
    + mocked LLM → assert no crash / structured result returned

Patch 3 — Spec doc (already applied, no code change needed):
- Provider corrected to Dukascopy, CLI args updated with --start-date/--end-date

Hard constraints:
- no SQLite
- no new top-level module
- no scheduler
- keep changes inside market_data_officer/ unless strictly required
- preserve the existing file-based spine and MarketPacketV2 contract path
- fixture must use the same manifest/CSV shape as existing conftest.py fixture
- do not introduce a side-channel loader or alternate read path

After implementing, run: pytest market_data_officer/tests/ -v
Target: 354+ tests green, both new relay tests pass.
```

---

*Derived from repo audit, session handoff doc, and status answers — 8 March 2026*  
*Source of truth: `docs/MDO_Phase1A_Spec.md` in repo*