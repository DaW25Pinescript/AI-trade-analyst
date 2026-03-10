Market Data Officer — Phase 1A Spec
Repo-Aligned Implementation Target
Project: AI Trade Analyst
Repo: github.com/DaW25Pinescript/AI-trade-analyst
Date: 8 March 2026
Status: ✅ Complete — implemented and verified 8 March 2026 (359/359 tests, zero regressions)

Context: Smoke path proven end-to-end (Run 7 ✅). Analysts currently receive no real market data — they reason from prompt context only. Phase 1A closes this gap by feeding a real MarketPacketV2 into the analyst graph.


1. Scope & Constraints
1.1 What Phase 1A Is

Integrate the existing market_data_officer/ module into the proven analyst pipeline
Produce real hot-package artifacts for EURUSD via the file-based spine
Prove that refresh_from_latest_exports() returns a valid MarketPacketV2
Prove that run_analyst() consumes a real packet without crashing
Add targeted tests to lock the contract

1.2 What Phase 1A Is NOT

Hard constraints — do not violate:


❌ Do not create a new top-level module — work inside market_data_officer/ only
❌ Do not introduce SQLite — file-based spine (Parquet/CSV) is canonical
❌ Do not build a scheduler — CLI/manual trigger only in this phase
❌ Do not change the analyst graph architecture — packet injection path already exists


2. Repo-Aligned Assumptions
Derived from actual codebase state, not the abstract spec in section 8 of the session handoff doc.
KeyValueRuntime artifacts rootmarket_data/ (created at runtime)Canonical / derived storageParquet/CSV via pipeline — no SQLiteHot package locationmarket_data/packages/latest/EURUSD yFinance alias (future/optional)EURUSD=X — not active in current MDO implementationTarget timeframe set1m, 5m, 15m, 1h, 4h, 1dIngestion triggerCLI / manual — run_feed.pyContract pathbuild_market_packet() / refresh_from_latest_exports()Packet schemaMarketPacketV2 in officer/contracts.pyAnalyst consumption pathrun_analyst() → build_market_packet() if no packet injectedProvider (primary)Dukascopy (bi5 format)Provider (yFinance)Optional dep (mro group in pyproject.toml) — not imported by market_data_officer/Provider (stub)Finnhub — not present in current codebase

3. Key File Paths
RolePathCLI entrypointmarket_data_officer/run_feed.pyFeed pipelinemarket_data_officer/feed/pipeline.pyOfficer servicemarket_data_officer/officer/service.pyOfficer loadermarket_data_officer/officer/loader.pyPacket schemamarket_data_officer/officer/contracts.pyTestsmarket_data_officer/tests/

4. Current State Audit
4.1 What Already Works

run_feed.py — real CLI with --hot-only, --gap-report, --diagnostics modes
build_market_packet() / refresh_from_latest_exports() — real implementations, return MarketPacketV2
MarketPacketV2 — assembles source, timeframes, features, summary, quality, structure
run_analyst() — already calls build_market_packet() if no packet injected
354 tests passing green in market_data_officer/ test suite

4.2 Known Failure Mode

⚠️ Hard-fail path: For trusted instruments (including EURUSD), a missing hot-package manifest propagates FileNotFoundError via quality checks. This is intentional behaviour — but it means analysts hard-fail in dev when feed artifacts have not been written.

Analogy: the officer (vending machine) works correctly — it refuses to dispense when the restocking truck (feed) hasn't arrived. The machine is not broken; the truck just hasn't run.
4.3 Gap Summary

No in-repo Phase 1A acceptance criteria doc ← this document is that doc
EURUSD hot-package artifacts may not exist in the dev environment
No fixture/seed path for dev when yFinance/Dukascopy is unreachable
Whether run_feed.py completes successfully for EURUSD has not been verified in CI


5. Phase 1A Acceptance Criteria

Before writing any code, run diagnostics against each gate. Report which are currently failing and why.

#GateAcceptance ConditionStatusAC-1run_feed.pyCompletes successfully for EURUSD baseline flow with no unhandled exceptions✅ DoneAC-2Artifact writesExpected hot-package artifacts written under market_data/packages/latest/✅ DoneAC-3MarketPacketV2refresh_from_latest_exports("EURUSD") returns valid MarketPacketV2 (no FileNotFoundError)✅ DoneAC-4Timeframe coverageMarketPacketV2 includes all 6 expected timeframes: 1m, 5m, 15m, 1h, 4h, 1d✅ DoneAC-5Analyst consumptionrun_analyst() completes and returns a structured result without FileNotFoundError or packet-schema exception — packet schema is validated, not just non-null✅ DoneAC-6Contract testsTwo targeted tests pass: Test A (officer relay) — seed fixture → refresh_from_latest_exports("EURUSD") → assert valid MarketPacketV2 → assert 6 timeframes. Test B (analyst consumption) — call run_analyst() with injected packet + mocked LLM → assert no crash / structured result returned. Keeps AC-6 deterministic with no live LLM or provider dependency.✅ DoneAC-7No SQLiteNo SQLite introduced — confirmed by grep -r sqlite market_data_officer/✅ DoneAC-8No new moduleNo new top-level module — work confined to market_data_officer/✅ Done

6. Pre-Code Diagnostic Protocol

Run these steps before changing any code. Report findings against AC-1 through AC-8 first.

Step 1 — Verify hot-package artifacts
POSIX:
bashls market_data/packages/latest/
Windows (CMD):
cmddir market_data\packages\latest\
Windows (PowerShell):
powershellGet-ChildItem market_data\packages\latest\
Expected: manifest JSON + CSV files for EURUSD across all 6 timeframes. If missing: feed has not run — proceed to Step 2.

Step 2 — Run the feed CLI
POSIX:
bashpython market_data_officer/run_feed.py --instrument EURUSD --start-date 2026-03-03 --end-date 2026-03-07
Windows:
cmdpython market_data_officer\run_feed.py --instrument EURUSD --start-date 2026-03-03 --end-date 2026-03-07

Windows note: if running inside a venv, activate first: .venv\Scripts\activate
Date note: --start-date and --end-date are required. Use a recent weekday range — Dukascopy returns empty payloads for weekend hours, which will produce "no data fetched" without error.


Step 3 — Test packet assembly directly
POSIX / Windows (both work from repo root with venv active):
bashpython -c "from market_data_officer.officer.service import refresh_from_latest_exports; print(refresh_from_latest_exports('EURUSD'))"
Expected: MarketPacketV2 printed without exception. If FileNotFoundError: artifacts from Step 2 not written.

Windows note: if import fails with ModuleNotFoundError, confirm PYTHONPATH includes repo root:
cmdset PYTHONPATH=.


Step 4 — Run the MDO test suite
POSIX / Windows:
bashpytest market_data_officer/tests/ -v
Windows alternative if pytest not on PATH:
cmdpython -m pytest market_data_officer\tests\ -v
Baseline: 354 passing. If regressions: note which tests fail and why before touching code.

Step 5 — Report smallest patch set
Based on Steps 1–4, list the minimum file changes needed to make AC-1 through AC-6 pass. Do not implement until this list is reviewed.

7. Implementation Constraints
7.1 Dev Environment Gap — Fixture Strategy
If yFinance/Dukascopy is unreachable during development, choose one of:
Option A (preferred): Pre-bake a minimal valid EURUSD hot-package fixture (small real or synthetic candle CSV + manifest JSON). Wire a --fixture flag on run_feed.py or a standalone seed_fixture.py script inside market_data_officer/ that writes to market_data/packages/latest/. Feed code untouched; officer gets real-shaped artifacts. The fixture must preserve the exact manifest/CSV shape expected by refresh_from_latest_exports() — no fake side-channel loader or alternate read path should be introduced. The same fixture logic powers both Test A (officer relay) and Test B (analyst consumption) in AC-6.
Option B: Confirm yFinance is wired as default dev provider and switch EURUSD to it if Dukascopy is current primary.
Option C (avoid): Treat EURUSD as unverified/unknown to dodge FileNotFoundError. This papers over the gap rather than closing it.
7.2 Code Change Surface
Restrict changes to:
market_data_officer/run_feed.py          # CLI args, pipeline handoff only
market_data_officer/feed/                # feed pipeline internals if defects found
market_data_officer/officer/service.py   # packet assembly if gaps found
market_data_officer/officer/loader.py    # hot-package reader if gaps found
market_data_officer/officer/contracts.py # schema only if spec mismatch
market_data_officer/tests/               # new targeted tests for AC-6
7.3 Out of Scope

ai_analyst/ — analyst graph internals (packet injection path already exists)
Any new top-level directory
Any database layer
Any scheduler or cron


8. Success Definition

Phase 1A is done when:
run_feed.py writes EURUSD artifacts → refresh_from_latest_exports("EURUSD") returns valid MarketPacketV2 → run_analyst() consumes it without crashing → all 6 timeframes present → targeted tests pass → 354+ tests green → no SQLite introduced → no new module created.

This is the relay race: feed → hot-package → officer → analyst. Phase 1A is proven when each handoff is confirmed by a test, not just by running the smoke path manually.

9. Phase Roadmap
PhaseScopeStatusPhase 1AEURUSD baseline spine (this spec)✅ Done — 359/359 testsPhase 1B+XAUUSD (15m, 1h, 4h, 1d)⏳ NextPhase E+Additional instruments, provider abstraction, alias config⏳ PendingOperationaliseScheduler / APScheduler integrationOut of scope for 1A

10. Diagnostic Findings (8 March 2026)

Historical record — pre-implementation diagnostics only. These were the gaps at the start of the implementation session. All ACs are now ✅ Done (see Section 5). This section is preserved so future readers can see what the actual blockers were and how they were resolved.

Root cause: no hot-package artifacts existed in dev — Dukascopy returns empty payloads on weekends. Code was not broken.
ACStatusGap TypeRoot CauseAC-1FAILRuntime/providerDukascopy weekend + spec omitted --start-date/--end-dateAC-2FAILMissing artifactBlocked by AC-1 — no feed run has produced artifactsAC-3FAILMissing artifactBlocked by AC-2 — FileNotFoundError on missing manifestAC-4FAILMissing artifactBlocked by AC-2/AC-3AC-5FAILMissing artifactBlocked by AC-3 + potential LLM provider dependencyAC-6PARTIALTest/fixture gap354 unit tests pass; integration relay test missingAC-7PASSNoneCleanAC-8PASSNoneClean
Approved patch set:
PatchFilesEst. LinesResolvesFixture seedingrun_feed.py (~20–30 lines)~20–30AC-1 through AC-5Relay + consumption teststests/test_phase1a_relay.py (new)~80–100AC-6 (both Test A + Test B)Spec doc accuracydocs/specs/MDO_Phase1A_Spec.md~5Doc accuracy (provider, CLI args)

Appendix — Historical Implementation Prompt

Archived. This was the prompt used to drive the implementation session. Phase 1A is complete. Preserved for reference.

Read `docs/specs/MDO_Phase1A_Spec.md` and treat it as the controlling spec for this pass.

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