"""LLM Router — primary interface.

Single-source-of-truth for LLM routing decisions.  Call sites ask for a
resolved route and receive a complete contract — they never assemble
provider/model/transport parameters themselves.

Usage:
    from ai_analyst.llm_router import router
    from ai_analyst.llm_router.router import ResolvedRoute

    # Task-based resolution (e.g. arbiter_decision):
    route = router.resolve_task_route("arbiter_decision")

    # Profile-based resolution (e.g. from analyst roster):
    route = router.resolve_profile_route("claude_sonnet")

    # Legacy dict-based resolution (backward-compatible):
    route_dict = router.resolve("chart_extract")

    # Or load the analyst roster:
    roster = router.get_analyst_roster()
"""
import logging
from dataclasses import dataclass
from typing import Any

from .config_loader import load_config
from .model_profiles import resolve_profile
from .task_types import ALL_TASK_TYPES

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedRoute:
    """Complete call contract returned by route resolution helpers.

    All fields needed for an LLM call are present — call sites never need
    to resolve provider, model, or transport config themselves.
    """
    provider: str
    model: str
    api_base: str | None
    api_key: str | None
    retries: int
    fallback_provider: str | None = None
    fallback_model: str | None = None

    def to_call_kwargs(self) -> dict[str, Any]:
        """Return kwargs suitable for passing to acompletion_metered().

        Maps ResolvedRoute fields to the keyword arguments expected by
        LiteLLM / acompletion_metered: custom_llm_provider, api_base, api_key.
        """
        return {
            "custom_llm_provider": self.provider,
            "api_base": self.api_base,
            "api_key": self.api_key,
        }


_TASK_MODEL_PROFILES: dict[str, str] = {
    "analyst_reasoning": "claude_sonnet",
    "arbiter_decision": "claude_opus",
}

# Hardcoded default roster — used when analyst_roster is absent from YAML.
_DEFAULT_ANALYST_ROSTER: list[dict[str, str]] = [
    {"profile": "claude_sonnet", "persona": "default_analyst"},
    {"profile": "claude_sonnet", "persona": "risk_officer"},
    {"profile": "claude_sonnet", "persona": "prosecutor"},
    {"profile": "claude_sonnet", "persona": "ict_purist"},
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

    profile_name = _TASK_MODEL_PROFILES.get(task_type)
    if profile_name:
        profile = resolve_profile(profile_name)
        model = profile.model
        fallback_model = profile.model
    else:
        model = task_cfg["primary_model"]
        fallback_model = task_cfg["fallback_model"]

    route = {
        "model": model,
        "fallback_model": fallback_model,
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


def _build_resolved_route(profile_name: str, retries: int) -> ResolvedRoute:
    """Internal helper — build a ResolvedRoute from a profile name and config."""
    config = load_config()
    backend = config["llm_backend"]
    profile = resolve_profile(profile_name)
    return ResolvedRoute(
        provider=profile.provider,
        model=profile.model,
        api_base=backend["base_url"],
        api_key=backend["api_key"],
        retries=retries,
        fallback_provider=None,
        fallback_model=None,
    )


def resolve_task_route(task_type: str) -> ResolvedRoute:
    """Resolve a complete call contract by task type.

    Looks up task→profile in _TASK_MODEL_PROFILES, resolves profile
    (including provider), and assembles the full transport contract.

    For tasks without a profile mapping (chart_extract, etc.), falls back
    to the YAML primary_model and infers provider from the model string
    prefix (e.g. "openai/claude-sonnet-4-6" → provider="openai").
    """
    if task_type not in ALL_TASK_TYPES:
        raise ValueError(
            f"Unknown task type: '{task_type}'. "
            f"Valid types: {sorted(ALL_TASK_TYPES)}"
        )

    config = load_config()
    task_cfg = config["task_routing"][task_type]

    profile_name = _TASK_MODEL_PROFILES.get(task_type)
    if profile_name:
        route = _build_resolved_route(profile_name, task_cfg["retries"])
    else:
        # Non-profile tasks — extract provider from model string if prefixed
        backend = config["llm_backend"]
        raw_model = task_cfg["primary_model"]
        if "/" in raw_model:
            provider, model = raw_model.split("/", 1)
        else:
            provider = "openai"
            model = raw_model
        route = ResolvedRoute(
            provider=provider,
            model=model,
            api_base=backend["base_url"],
            api_key=backend["api_key"],
            retries=task_cfg["retries"],
            fallback_provider=None,
            fallback_model=task_cfg.get("fallback_model"),
        )

    logger.info(
        "[router] resolve_task_route task=%s provider=%s model=%s",
        task_type, route.provider, route.model,
    )
    return route


def resolve_profile_route(profile_name: str) -> ResolvedRoute:
    """Resolve a complete call contract by profile name.

    Used by analyst roster call sites where the profile name is already
    known from the persona→profile mapping.
    """
    config = load_config()
    task_cfg = config["task_routing"].get("analyst_reasoning", {})
    retries = task_cfg.get("retries", 1)
    route = _build_resolved_route(profile_name, retries)

    logger.info(
        "[router] resolve_profile_route profile=%s provider=%s model=%s",
        profile_name, route.provider, route.model,
    )
    return route


def get_analyst_roster() -> list[dict]:
    """Load the analyst roster from llm_routing.yaml.

    Returns a list of dicts with 'profile' (str) and 'persona' (PersonaType).
    Falls back to _DEFAULT_ANALYST_ROSTER if the YAML has no analyst_roster key.
    """
    from ..models.persona import PersonaType

    config = load_config()
    raw_roster = config.get("analyst_roster", _DEFAULT_ANALYST_ROSTER)

    roster: list[dict] = []
    for entry in raw_roster:
        roster.append({
            "profile": entry["profile"],
            "persona": PersonaType(entry["persona"]),
        })

    logger.info(
        "[router] analyst_roster loaded: %d analysts — %s",
        len(roster),
        [f"{r['persona'].value}={r['profile']}" for r in roster],
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

    resolved = resolve_task_route(task_type)
    route = resolve(task_type)

    # Try primary model with configured retries
    last_error: Exception | None = None
    for attempt in range(route["retries"] + 1):
        try:
            response = await acompletion(
                model=resolved.model,
                messages=messages,
                api_base=resolved.api_base,
                api_key=resolved.api_key,
                custom_llm_provider=resolved.provider,
                **kwargs,
            )
            return response
        except Exception as e:
            last_error = e
            logger.warning(
                "[router] %s primary model %s failed (attempt %d/%d): %s",
                task_type,
                resolved.model,
                attempt + 1,
                route["retries"] + 1,
                e,
            )

    # Fallback to secondary model
    logger.warning(
        "[router] %s falling back from %s to %s after %d failed attempt(s)",
        task_type,
        resolved.model,
        route["fallback_model"],
        route["retries"] + 1,
    )
    try:
        response = await acompletion(
            model=route["fallback_model"],
            messages=messages,
            api_base=resolved.api_base,
            api_key=resolved.api_key,
            custom_llm_provider=resolved.provider,
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
            f"[router] {task_type}: both primary ({resolved.model}) and "
            f"fallback ({route['fallback_model']}) failed. "
            f"Primary error: {last_error}. Fallback error: {fallback_error}"
        ) from fallback_error
