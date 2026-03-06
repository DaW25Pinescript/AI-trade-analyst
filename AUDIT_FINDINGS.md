# Audit Findings — 2026-03-06

## Critical (blocks testing)

- **CRIT-1: CLI replay command bypasses router and has no proxy support**
  `ai_analyst/cli.py:567-590` — The `replay` command imports `litellm.acompletion` directly,
  uses a hardcoded `ARBITER_MODEL = "claude-haiku-4-5-20251001"`, and passes **no `api_base`
  or `api_key`**. When the local Claude proxy is the only available backend, this call will
  fail because LiteLLM defaults to the Anthropic API (which requires a real API key).
  **Fix:** Use `router.resolve(ARBITER_DECISION)` and pass `api_base`/`api_key`.

- **CRIT-2: ExecutionRouter arbiter call uses hardcoded model, no proxy routing**
  `ai_analyst/core/execution_router.py:78,343-353` — `ARBITER_MODEL` is hardcoded to
  `"claude-haiku-4-5-20251001"` and `acompletion_metered()` is called without `api_base`
  or `api_key`. This means the ExecutionRouter path (used in hybrid/manual modes) cannot
  route through the local proxy.
  **Fix:** Use `router.resolve(ARBITER_DECISION)` and pass route params.

- **CRIT-3: Stale placeholder `main.py` at repo root**
  `main.py` — 8-line FastAPI "Hello World" stub. The real entry point is
  `ai_analyst/api/main.py`. A developer running `uvicorn main:app` from the repo root will
  get a dummy server instead of the actual application. This will cause confusion during
  first-time setup and live testing.
  **Fix:** Delete the file.

## Moderate (degrades reliability)

- **MOD-1: ARBITER_MODEL constant duplicated in 3 files**
  The same `"claude-haiku-4-5-20251001"` string is defined in:
  - `ai_analyst/graph/arbiter_node.py:26` (legacy, commented as kept for reference)
  - `ai_analyst/core/execution_router.py:78` (active, used in runtime)
  - `ai_analyst/cli.py:569` (active, used in replay)
  Changing the arbiter model requires editing multiple files. Single source of truth violated.
  **Fix:** Remove inline constants; use `router.resolve()` in all locations.

- **MOD-2: `.vscode/launch.json` contains hardcoded Windows path**
  `.vscode/launch.json:11` — Absolute path `c:\Users\david\OneDrive\...\index.html`.
  This breaks for any other developer and leaks the repo owner's local filesystem layout.
  **Fix:** Use `${workspaceFolder}/app/index.html` instead.

- **MOD-3: Analyst model names hardcoded in `ANALYST_CONFIGS`**
  `ai_analyst/graph/analyst_nodes.py:45-50` — Four analyst models are inline string literals.
  While these are routed through `acompletion_metered()` at runtime, changing the model roster
  requires a code change rather than a config change.
  **Deferred:** This is a design decision that belongs in the full router integration pass
  (out of scope for this stabilisation audit). Documented here for v2 planning.

- **MOD-4: `pytest-asyncio` version pinned to 1.3.0 (very old)**
  `ai_analyst/requirements.txt:28` — Current stable is 0.23+. Version 1.3.0 appears to be a
  non-standard version. The auto-mode annotation is working but generates 5 warnings about
  non-async functions marked with `@pytest.mark.asyncio`.
  **Deferred:** Tests pass; no runtime impact. Revisit during dependency update pass.

- **MOD-5: README status section outdated**
  `README.md` describes G11 as in-progress, but `tooling/release_checklist.md` shows G12
  complete. Creates ambiguity about current project phase.
  **Deferred:** Documentation-only; no runtime impact.

## Minor (cosmetic or low risk)

- **MIN-1: No `.dockerignore` file**
  `COPY . .` in Dockerfile copies `.git/`, `tests/`, `docs/`, `*.bat` files into the image.
  Wastes ~10-20% container storage. No functional impact.

- **MIN-2: Stale audit snapshot files in `docs/`**
  8 audit files dated Feb 24 – Mar 5 exist in `docs/`. No clear versioning or archival
  strategy.

- **MIN-3: `services/claude_code_api/` status unclear**
  Marked as "experimental" in comments but actively imported in production code
  (`claude_code_api_client.py`). Role vs. the main API path is undocumented.

- **MIN-4: Bridge retry constants hardcoded in JS**
  `app/scripts/api_bridge.js` — Timeout (180s), retry count (1), retry delay (400ms) are
  code constants, not user-configurable. Acceptable for current use but worth noting.

- **MIN-5: Overlay indicator keys hardcoded in JS**
  `app/scripts/ui/form_bindings.js:64` — `['m15overlay', 'm15structure', 'm15trendline',
  'customoverlay']` — Would require code change to add new overlay types.

## LiteLLM call map

| File | Line | Model string or call | Centralised or inline? |
|------|------|----------------------|------------------------|
| `ai_analyst/llm_router/router.py` | 76,84,112 | `litellm.acompletion` via `router.call_with_fallback()` | Centralised (router) |
| `ai_analyst/core/usage_meter.py` | 86 | `litellm.acompletion` lazy import in `acompletion_metered()` | Centralised (metering wrapper) |
| `ai_analyst/core/usage_meter.py` | 55 | `litellm.completion_cost` for cost extraction | Centralised (metering) |
| `ai_analyst/cli.py` | 567,584 | `litellm.acompletion` direct import, `ARBITER_MODEL` hardcoded | **Inline — bypasses router** |
| `ai_analyst/graph/analyst_nodes.py` | 63-74 | Via `acompletion_metered()` + `router.resolve(ANALYST_REASONING)` | Centralised |
| `ai_analyst/graph/arbiter_node.py` | 88-99 | Via `acompletion_metered()` + `router.resolve(ARBITER_DECISION)` | Centralised |
| `ai_analyst/core/chart_two_step.py` | 125-136 | Via `acompletion_metered()` + `router.resolve(CHART_EXTRACT)` | Centralised |
| `ai_analyst/core/chart_two_step.py` | 183-194 | Via `acompletion_metered()` + `router.resolve(CHART_INTERPRET)` | Centralised |
| `ai_analyst/core/execution_router.py` | 343-353 | Via `acompletion_metered()`, `ARBITER_MODEL` hardcoded, **no `api_base`/`api_key`** | **Inline — bypasses router** |

### Model name string literals in Python code

| File | Line | String | Context |
|------|------|--------|---------|
| `ai_analyst/cli.py` | 569 | `"claude-haiku-4-5-20251001"` | ARBITER_MODEL constant |
| `ai_analyst/core/execution_router.py` | 78 | `"claude-haiku-4-5-20251001"` | ARBITER_MODEL constant |
| `ai_analyst/graph/arbiter_node.py` | 26 | `"claude-haiku-4-5-20251001"` | Legacy constant (comment says kept for reference) |
| `ai_analyst/graph/analyst_nodes.py` | 46 | `"gpt-4o"` | ANALYST_CONFIGS |
| `ai_analyst/graph/analyst_nodes.py` | 47 | `"claude-sonnet-4-6"` | ANALYST_CONFIGS |
| `ai_analyst/graph/analyst_nodes.py` | 48 | `"gemini/gemini-1.5-pro"` | ANALYST_CONFIGS |
| `ai_analyst/graph/analyst_nodes.py` | 49 | `"xai/grok-vision-beta"` | ANALYST_CONFIGS |
| `ai_analyst/core/api_key_manager.py` | 24-30 | 7 model IDs | SUPPORTED_MODELS lookup (appropriate) |
| `ai_analyst/core/llm_client.py` | 18-22 | 5 model IDs | Fallback chain defaults (appropriate) |
| `config/llm_routing.example.yaml` | 8-30 | claude-sonnet, claude-opus | YAML config (correct location) |

## Questions / ambiguities (do not fix without clarification)

- **Q1:** `ANALYST_CONFIGS` in `analyst_nodes.py` defines models separately from
  `llm_routing.yaml`. Should these be unified in the router pass, or is the intent that
  the analyst roster is code-defined while the proxy/base_url comes from config?

- **Q2:** `services/claude_code_api/` is imported by `claude_code_api_client.py` and gated
  behind `AI_ANALYST_LLM_BACKEND=claude_code_api`. Is this an active integration path or
  experimental? Should it be wired through the router?

- **Q3:** The `macro_risk_officer/config/weights.yaml` and `thresholds.yaml` files have no
  `.example` variants. Are these stable defaults that ship as-is, or should they be
  gitignored with examples?

## Dead code / orphaned files

- **`main.py` (repo root):** 8-line FastAPI stub. Not imported anywhere. The real entry
  point is `ai_analyst/api/main.py`. → **Delete.**

- **`ARBITER_MODEL` in `graph/arbiter_node.py:26`:** Constant kept "for reference" per
  comment, but runtime now uses `router.resolve()`. → **Remove constant.**

- **Stale audit snapshots in `docs/`:** 8 files from previous audits (Feb 24–Mar 5). Not
  actively referenced. → **Archive or leave (no runtime impact).**

## TODOs found in codebase

No `TODO`, `FIXME`, or `HACK` comments found in any Python file. Clean.

## Test suite status

### JavaScript tests (tests/*.js)
- **234 tests, 0 failures, 0 skipped** — `node --test tests/*.js`

### Python tests (ai_analyst/tests/)
- **469 tests, 0 failures, 5 warnings** — `python -m pytest ai_analyst/tests/`
- Warnings: 5 tests in `test_audit3_execution_correctness.py` are marked with
  `@pytest.mark.asyncio` but are not async functions (cosmetic, no impact).
