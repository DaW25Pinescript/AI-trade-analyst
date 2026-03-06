# Notes for V2

> **Last updated:** 2026-03-06 — Phase 9-13 consolidation pass.

## Architecture observations

- The router module (`llm_router/`) is clean and well-isolated. It was easy to wire the two remaining call sites (CLI replay, ExecutionRouter) through it. The pattern of `router.resolve(task_type)` returning a dict with model/base_url/api_key is simple and effective.
- The `acompletion_metered()` wrapper in `usage_meter.py` is the natural chokepoint for all LLM calls. It handles both litellm and claude_code_api backends transparently. This is a strong seam for adding observability, cost controls, or circuit breakers.
- Pydantic models are well-structured and the schema round-trip tests between Python and JS are a significant quality gate. Keep this pattern.

## Resolved in Phase 9-13

- **ANALYST_CONFIGS unified** (Phase 9): Models moved from hardcoded `analyst_nodes.py` list to `llm_routing.yaml` (`analyst_roster` section). `router.get_analyst_roster()` provides the interface with hardcoded defaults as fallback. Single config file for all model assignments.
- **Fallback mechanisms consolidated** (Phase 10): Removed `ENABLE_FALLBACK_ROUTING` env var and `acompletion_with_fallback` from the metered call path. `acompletion_with_retry` handles retries at the call level; `router.call_with_fallback()` handles task-level primary→fallback routing. Single fallback authority. `llm_client.py` functions retained as lower-level primitives.
- **pyproject.toml added** (Phase 11): Supports `pip install -e ".[dev]"` and `pip install -e ".[mro]"`. Includes pytest config and coverage settings.
- **Replay metering** (Phase 12): CLI `replay` command now routes through `acompletion_metered()` instead of raw `litellm.acompletion`. Replay runs appear in `usage.jsonl` with stage `replay_arbiter`.
- **Dual-backend clarified** (Phase 13): `claude_code_api` backend documented as experimental. Emits WARNING log when activated. Does not support images, provides no token usage. Production should use litellm + local Claude proxy.

## Seams that caused friction

- **ARBITER_MODEL in 3 places**: The same constant was defined in `cli.py`, `execution_router.py`, and `arbiter_node.py`. Only the arbiter_node version was unused at runtime (router had taken over), but the other two were live and bypassing the router. Easy to miss during incremental migration.
- **CLI replay as a separate code path**: The `replay` command in `cli.py` reimplements a mini-arbiter pipeline outside the main graph. ~~It uses direct `litellm.acompletion` instead of `acompletion_metered`, so replay runs don't appear in usage.jsonl.~~ **Fixed in Phase 12** — now routes through `acompletion_metered()`.
- **No single "where do LLM calls happen" index**: Finding all LLM call sites required grepping for multiple patterns (`litellm`, `acompletion`, `api_base`, model name strings). A v2 architecture doc or `# LLM_CALL_SITE` marker convention would help.
- **Test dependency installation**: ~~Running Python tests requires installing all of `requirements.txt`. There's no `pip install -e .` or `pyproject.toml`.~~ **Fixed in Phase 11** — `pyproject.toml` added.
- **Two test suites, two runners**: JS tests run with `node --test`, Python tests with `pytest`. No unified command. The Makefile helps but could be more discoverable.

## Things that worked well (keep)

- **Schema governance**: `enums.json` as single source of truth with drift-detection tests in both JS and Python is excellent. Zero schema drift found during audit.
- **Config-driven routing via YAML**: The `llm_routing.yaml` pattern with env var override (`CLAUDE_PROXY_BASE_URL`) is simple and effective. The fallback to `.example.yaml` when no local config exists is a nice touch. Now also includes the analyst roster.
- **Fail-safe arbiter**: The `_fallback_verdict()` pattern that returns NO_TRADE on any error is exactly the right default for a trading system. Never let a parsing error become a trade signal.
- **Usage metering**: Every LLM call (via the metered wrapper) gets logged to `usage.jsonl` with model, latency, tokens, cost. Now includes replay calls too.
- **Progress events**: The `progress_store.push_event()` calls in analyst nodes enable real-time UI updates. Good design for async fan-out.
- **Test coverage depth**: 469 Python tests + 234 JS tests with zero failures. The overlay delta config alignment tests are particularly thorough.

## Remaining open questions

- The `macro_risk_officer/` package is a soft dependency (try/except ImportError). Is this the right pattern long-term, or should it become a proper optional dependency with a feature flag?
- The `macro_risk_officer/config/weights.yaml` and `thresholds.yaml` files have no `.example` variants. Are these stable defaults that ship as-is, or should they be gitignored with examples?
