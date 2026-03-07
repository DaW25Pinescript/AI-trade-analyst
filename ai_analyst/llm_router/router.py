"""LLM Router — primary interface.

Integration boundary decision (Phase 0 audit):
  Model names in this repo are scattered string literals (ANALYST_CONFIGS in
  analyst_nodes.py, ARBITER_MODEL in arbiter_node.py). The router is introduced
  as a clean new layer. Existing call sites are wired incrementally — not all
  at once — to avoid broad refactors.

Usage:
    from ai_analyst.llm_router import router
    route = router.resolve("chart_extract")
    # route = {"model": "...", "fallback_model": "...", "retries": 1,
    #          "base_url": "...", "api_key": "..."}

    # Or use the fallback-aware helper:
    response = await router.call_with_fallback("chart_extract", messages=[...])

    # Or load the analyst roster:
    roster = router.get_analyst_roster()
    # roster = [{"model": "gpt-4o", "persona": PersonaType.DEFAULT_ANALYST}, ...]
"""
import logging
from typing import Any

from .config_loader import load_config
from .task_types import ALL_TASK_TYPES

logger = logging.getLogger(__name__)

# Hardcoded default roster — used when analyst_roster is absent from YAML.
# Keeps backwards compatibility with configs that predate Phase 9.
_DEFAULT_ANALYST_ROSTER: list[dict[str, str]] = [
    {"model": "gpt-4o", "persona": "default_analyst"},
    {"model": "claude-sonnet-4-6", "persona": "risk_officer"},
    {"model": "gemini/gemini-1.5-pro", "persona": "prosecutor"},
    {"model": "xai/grok-vision-beta", "persona": "ict_purist"},
]


def resolve(task_type: str) -> dict[str, Any]:
    """Resolve routing configuration for a given task type.

    Returns a dict ready to be passed to a LiteLLM call site:
        model, fallback_model, retries, base_url, api_key
    """
    if task_type not in ALL_TASK_TYPES:
        raise ValueError(
            f"Unknown task type: '{task_type}'. "
            f"Valid types: {sorted(ALL_TASK_TYPES)}"
        )

    config = load_config()
    backend = config["llm_backend"]
    task_cfg = config["task_routing"][task_type]

    route = {
        "model": task_cfg["primary_model"],
        "fallback_model": task_cfg["fallback_model"],
        "retries": task_cfg["retries"],
        "base_url": backend["base_url"],
        "api_key": backend["api_key"],
    }

    logger.info(
        "[router] task=%s model=%s proxy_mode=%s",
        task_type,
        route["model"],
        backend.get("mode", "unknown"),
    )

    return route


def get_analyst_roster() -> list[dict]:
    """Load the analyst roster from llm_routing.yaml.

    Returns a list of dicts with 'model' (str) and 'persona' (PersonaType).
    Falls back to _DEFAULT_ANALYST_ROSTER if the YAML has no analyst_roster key.
    """
    from ..models.persona import PersonaType

    config = load_config()
    raw_roster = config.get("analyst_roster", _DEFAULT_ANALYST_ROSTER)

    roster: list[dict] = []
    for entry in raw_roster:
        roster.append({
            "model": entry["model"],
            "persona": PersonaType(entry["persona"]),
        })

    logger.info(
        "[router] analyst_roster loaded: %d analysts — %s",
        len(roster),
        [f"{r['persona'].value}={r['model']}" for r in roster],
    )
    return roster


async def call_with_fallback(task_type: str, messages: list, **kwargs) -> Any:
    """Execute an LLM call with router-resolved model and automatic fallback.

    Retries the primary model N times (as configured in llm_routing.yaml),
    then falls back to the secondary Claude model. Fallbacks are NEVER silent —
    every fallback produces a WARNING log entry.

    Args:
        task_type: One of the task type constants from task_types.py.
        messages: The messages list to send to the LLM.
        **kwargs: Additional keyword arguments passed to litellm.completion.

    Returns:
        The LLM completion response.
    """
    from litellm import acompletion

    route = resolve(task_type)

    # Try primary model with configured retries
    last_error: Exception | None = None
    for attempt in range(route["retries"] + 1):
        try:
            response = await acompletion(
                model=route["model"],
                messages=messages,
                api_base=route["base_url"],
                api_key=route["api_key"],
                custom_llm_provider="openai",
                **kwargs,
            )
            return response
        except Exception as e:
            last_error = e
            logger.warning(
                "[router] %s primary model %s failed (attempt %d/%d): %s",
                task_type,
                route["model"],
                attempt + 1,
                route["retries"] + 1,
                e,
            )

    # Fallback to secondary model
    logger.warning(
        "[router] %s falling back from %s to %s after %d failed attempt(s)",
        task_type,
        route["model"],
        route["fallback_model"],
        route["retries"] + 1,
    )
    try:
        response = await acompletion(
            model=route["fallback_model"],
            messages=messages,
            api_base=route["base_url"],
            api_key=route["api_key"],
            custom_llm_provider="openai",
            **kwargs,
        )
        return response
    except Exception as fallback_error:
        logger.warning(
            "[router] %s fallback model %s also failed: %s",
            task_type,
            route["fallback_model"],
            fallback_error,
        )
        raise RuntimeError(
            f"[router] {task_type}: both primary ({route['model']}) and "
            f"fallback ({route['fallback_model']}) failed. "
            f"Primary error: {last_error}. Fallback error: {fallback_error}"
        ) from fallback_error
