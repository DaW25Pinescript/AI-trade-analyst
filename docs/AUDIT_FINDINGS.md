# Audit Findings — 2026-03-06

> **Last updated:** 2026-03-06 — Phase 9-13 consolidation pass complete.

## Critical (blocks testing)

- **CRIT-1: CLI replay command bypasses router and has no proxy support** — **RESOLVED** ✅
  `ai_analyst/cli.py` — Was using hardcoded `ARBITER_MODEL` and direct `litellm.acompletion`
  with no `api_base` or `api_key`.
  **Resolution:** Now uses `router.resolve(ARBITER_DECISION)` and passes `api_base`/`api_key`.
  Fixed in `a5dabac`, `8d519a3`.

- **CRIT-2: ExecutionRouter arbiter call uses hardcoded model, no proxy routing** — **RESOLVED** ✅
  `ai_analyst/core/execution_router.py` — Was hardcoded to `"claude-haiku-4-5-20251001"` with
  no proxy support.
  **Resolution:** Now uses `router.resolve(ARBITER_DECISION)` and passes route params.
  Fixed in `a5dabac`, `8d519a3`.

- **CRIT-3: Stale placeholder `main.py` at repo root** — **RESOLVED** ✅
  8-line FastAPI stub that shadowed the real entry point.
  **Resolution:** File deleted. Fixed in `cc72c1c`.

## Moderate (degrades reliability)

- **MOD-1: ARBITER_MODEL constant duplicated in 3 files** — **RESOLVED** ✅
  Was defined in `arbiter_node.py`, `execution_router.py`, and `cli.py`.
  **Resolution:** Legacy constant removed from `arbiter_node.py` (`c1b3a61`). Both
  `execution_router.py` and `cli.py` now use `router.resolve()` instead of inline constants.

- **MOD-2: `.vscode/launch.json` contains hardcoded Windows path** — **RESOLVED** ✅
  Was an absolute `c:\Users\...` path.
  **Resolution:** Replaced with `${workspaceFolder}/app/index.html`. Fixed in `59e002b`.

- **MOD-3: Analyst model names hardcoded in `ANALYST_CONFIGS`** — **RESOLVED** ✅
  `ai_analyst/graph/analyst_nodes.py:45-50` — Four analyst models were inline string literals.
  **Resolution:** Phase 9 — Models moved to `config/llm_routing.yaml` (`analyst_roster` section).
  `analyst_nodes.py` now loads via `router.get_analyst_roster()` with hardcoded defaults as fallback.

- **MOD-4: `pytest-asyncio` version pinned to 1.3.0 (very old)** — **DEFERRED**
  Generates 5 cosmetic warnings but all tests pass. No runtime impact.
  **Rationale:** Revisit during dependency update pass.

- **MOD-5: README status section outdated** — **RESOLVED** ✅
  `README.md` described G11 as in-progress and showed stale test counts.
  **Resolution:** Updated to reflect G12 complete and current test counts (703+).

## Minor (cosmetic or low risk)

- **MIN-1: No `.dockerignore` file** — **RESOLVED** ✅
  `COPY . .` in Dockerfile was copying `.git/`, `tests/`, `docs/` into the image.
  **Resolution:** `.dockerignore` added. Fixed in `69172ff`.

- **MIN-2: Stale audit snapshot files in `docs/`** — **ACCEPTED**
  8 audit files from Feb 24–Mar 5 exist in `docs/`. No runtime impact. Retained as
  historical audit trail.

- **MIN-3: `services/claude_code_api/` status unclear** — **RESOLVED** ✅
  **Status:** Experimental backend. Shells out to `claude -p` for text-only messages.
  Does not support images and provides no token usage data.
  **Resolution:** Phase 13 — Documented as experimental in `usage_meter.py` with a WARNING
  log when activated. Production use should prefer litellm + local Claude proxy.

- **MIN-4: Bridge retry constants hardcoded in JS** — **ACCEPTED**
  Timeout (180s), retry count (1), retry delay (400ms) are reasonable defaults.
  Acceptable for current use.

- **MIN-5: Overlay indicator keys hardcoded in JS** — **ACCEPTED**
  Would require code change to add new overlay types. Acceptable for current scope.

## Resolution summary

| Severity | Total | Resolved | Deferred | Accepted |
|----------|-------|----------|----------|----------|
| Critical | 3 | 3 | 0 | 0 |
| Moderate | 5 | 4 | 1 | 0 |
| Minor | 5 | 2 | 0 | 3 |
| **Total** | **13** | **9** | **1** | **3** |

## LiteLLM call map (current state)

| File | Model resolution | Status |
|------|-----------------|--------|
| `ai_analyst/llm_router/router.py` | `litellm.acompletion` via `router.call_with_fallback()` | Centralised |
| `ai_analyst/core/usage_meter.py` | `litellm.acompletion` in `acompletion_metered()` | Centralised (metering) |
| `ai_analyst/core/usage_meter.py` | `litellm.completion_cost` for cost extraction | Centralised (metering) |
| `ai_analyst/cli.py` (replay) | Via `acompletion_metered()` + `router.resolve(ARBITER_DECISION)` | **Centralised** (Phase 12) |
| `ai_analyst/graph/analyst_nodes.py` | Via `acompletion_metered()` + `router.resolve(ANALYST_REASONING)` | Centralised |
| `ai_analyst/graph/arbiter_node.py` | Via `acompletion_metered()` + `router.resolve(ARBITER_DECISION)` | Centralised |
| `ai_analyst/core/chart_two_step.py` | Via `acompletion_metered()` + `router.resolve(CHART_EXTRACT/CHART_INTERPRET)` | Centralised |
| `ai_analyst/core/execution_router.py` | Via `acompletion_metered()` + `router.resolve(ARBITER_DECISION)` | **Centralised** |

All LLM calls now route through `llm_router/router.py`. No inline model bypasses remain.

### Model name string literals in Python code

| File | String | Context | Status |
|------|--------|---------|--------|
| `ai_analyst/graph/analyst_nodes.py` | None — loaded from YAML | ANALYST_CONFIGS via `router.get_analyst_roster()` | Resolved (Phase 9) |
| `ai_analyst/core/api_key_manager.py` | 7 model IDs | SUPPORTED_MODELS lookup | Appropriate |
| `ai_analyst/core/llm_client.py` | 5 model IDs | Fallback chain defaults | Appropriate |
| `config/llm_routing.example.yaml` | claude-sonnet, claude-opus | YAML config | Correct location |

## Questions / ambiguities

- **Q1:** ~~`ANALYST_CONFIGS` unified?~~ — **RESOLVED** (Phase 9). Models now in `llm_routing.yaml`.

- **Q2:** ~~`services/claude_code_api/` status?~~ — **RESOLVED** (Phase 13). Documented as
  experimental. Emits WARNING log when activated. Production should use litellm + proxy.

- **Q3:** The `macro_risk_officer/config/weights.yaml` and `thresholds.yaml` files have no
  `.example` variants. Are these stable defaults that ship as-is, or should they be
  gitignored with examples?

## Dead code / orphaned files

- **`main.py` (repo root):** Deleted. ✅
- **`ARBITER_MODEL` in `graph/arbiter_node.py`:** Removed. ✅
- **Stale audit snapshots in `docs/`:** Retained as historical audit trail (no runtime impact).

## TODOs found in codebase

No `TODO`, `FIXME`, or `HACK` comments found in any Python file. Clean.

## Test suite status

### JavaScript tests (tests/*.js)
- **234 tests, 0 failures, 0 skipped** — `node --test tests/*.js`

### Python tests (ai_analyst/tests/)
- **469 tests, 0 failures, 5 warnings** — `python -m pytest ai_analyst/tests/`
- Warnings: 5 tests in `test_audit3_execution_correctness.py` are marked with
  `@pytest.mark.asyncio` but are not async functions (cosmetic, no impact).
