# Notes for V2

## Architecture observations

- The router module (`llm_router/`) is clean and well-isolated. It was easy to wire the two remaining call sites (CLI replay, ExecutionRouter) through it. The pattern of `router.resolve(task_type)` returning a dict with model/base_url/api_key is simple and effective.
- The `acompletion_metered()` wrapper in `usage_meter.py` is the natural chokepoint for all LLM calls. It handles both litellm and claude_code_api backends transparently. This is a strong seam for adding observability, cost controls, or circuit breakers.
- The dual-backend pattern (`AI_ANALYST_LLM_BACKEND=litellm|claude_code_api`) in usage_meter.py is clever but adds a dimension of complexity. In v2, consider whether the router should own this decision rather than usage_meter.
- The `ANALYST_CONFIGS` list in `analyst_nodes.py` defines models in code while the router defines them in YAML. These are two separate model registries that could drift. Unifying them is the obvious next step.
- Pydantic models are well-structured and the schema round-trip tests between Python and JS are a significant quality gate. Keep this pattern.
- The fallback chain in `llm_client.py` (`acompletion_with_retry` → `acompletion_with_fallback`) is solid but operates at a different layer than the router's own fallback mechanism in `router.call_with_fallback()`. These are two independent fallback systems that could interact unpredictably.

## Seams that caused friction

- **ARBITER_MODEL in 3 places**: The same constant was defined in `cli.py`, `execution_router.py`, and `arbiter_node.py`. Only the arbiter_node version was unused at runtime (router had taken over), but the other two were live and bypassing the router. Easy to miss during incremental migration.
- **CLI replay as a separate code path**: The `replay` command in `cli.py` reimplements a mini-arbiter pipeline outside the main graph. It uses direct `litellm.acompletion` instead of `acompletion_metered`, so replay runs don't appear in usage.jsonl. This parallel path is a maintenance liability.
- **No single "where do LLM calls happen" index**: Finding all LLM call sites required grepping for multiple patterns (`litellm`, `acompletion`, `api_base`, model name strings). A v2 architecture doc or `# LLM_CALL_SITE` marker convention would help.
- **Test dependency installation**: Running Python tests requires installing all of `requirements.txt` (pydantic, litellm, langgraph, fastapi, etc). There's no `pip install -e .` or `pyproject.toml` — just a raw requirements file. First-time setup is manual.
- **Two test suites, two runners**: JS tests run with `node --test`, Python tests with `pytest`. No unified command. The Makefile helps but could be more discoverable.

## Things that worked well (keep in v2)

- **Schema governance**: `enums.json` as single source of truth with drift-detection tests in both JS and Python is excellent. Zero schema drift found during audit.
- **Config-driven routing via YAML**: The `llm_routing.yaml` pattern with env var override (`CLAUDE_PROXY_BASE_URL`) is simple and effective. The fallback to `.example.yaml` when no local config exists is a nice touch.
- **Fail-safe arbiter**: The `_fallback_verdict()` pattern that returns NO_TRADE on any error is exactly the right default for a trading system. Never let a parsing error become a trade signal.
- **Usage metering**: Every LLM call (via the metered wrapper) gets logged to `usage.jsonl` with model, latency, tokens, cost. This is invaluable for cost management.
- **Progress events**: The `progress_store.push_event()` calls in analyst nodes enable real-time UI updates. Good design for async fan-out.
- **Test coverage depth**: 469 Python tests + 234 JS tests with zero failures. The overlay delta config alignment tests are particularly thorough.

## Open questions for v2 design

- Should `ANALYST_CONFIGS` (the model roster for the analyst fan-out) move into `llm_routing.yaml`? This would unify all model assignments in one config file, but it mixes "which models to fan out to" (an application concern) with "how to route to a proxy" (an infrastructure concern).
- The `claude_code_api` backend path and the `litellm` path are two parallel ways to reach an LLM. Should v2 collapse these into a single path, or is the dual-backend pattern worth keeping for flexibility?
- The CLI `replay` command bypasses `acompletion_metered()`, so replay runs aren't tracked in usage.jsonl. Should replay calls be metered? If not, should there be an explicit opt-out rather than a silent omission?
- Should the router's `call_with_fallback()` and `llm_client.py`'s `acompletion_with_fallback()` be consolidated into a single fallback mechanism? Currently there are two layers of retry/fallback logic that could compound.
- The `macro_risk_officer/` package is a soft dependency (try/except ImportError). Is this the right pattern long-term, or should it become a proper optional dependency with a feature flag?
