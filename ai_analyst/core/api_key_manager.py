"""
API key availability checker and execution mode suggester.

API keys are managed via environment variables only.
Keys are never stored in the database, logs, or source code.
Design principle: adding a key upgrades that analyst from manual to
automated — nothing else changes.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelAvailability:
    model_id: str
    available: bool
    env_var: str
    reason: Optional[str] = None


# Maps model identifiers (as used by LiteLLM) to their required env var
SUPPORTED_MODELS: dict[str, str] = {
    "claude-sonnet-4-6":          "ANTHROPIC_API_KEY",
    "claude-haiku-4-5-20251001":  "ANTHROPIC_API_KEY",
    "gpt-4o":                     "OPENAI_API_KEY",
    "gpt-4o-mini":                "OPENAI_API_KEY",
    "gemini/gemini-1.5-pro":      "GOOGLE_API_KEY",
    "grok/grok-4-vision":         "XAI_API_KEY",
    "grok/grok-3":                "XAI_API_KEY",
}

# Human-readable provider labels used in CLI output
PROVIDER_LABELS: dict[str, str] = {
    "ANTHROPIC_API_KEY": "Claude Sonnet / Haiku",
    "OPENAI_API_KEY":    "GPT-4o / GPT-4o-mini",
    "GOOGLE_API_KEY":    "Gemini 1.5 Pro",
    "XAI_API_KEY":       "Grok Vision / Grok-3",
}


def check_model_availability(model_id: str) -> ModelAvailability:
    env_var = SUPPORTED_MODELS.get(model_id)
    if not env_var:
        return ModelAvailability(model_id, False, "", reason="Model not in supported list")

    key = os.getenv(env_var, "").strip()
    if not key:
        return ModelAvailability(
            model_id, False, env_var, reason=f"Missing env var: {env_var}"
        )

    return ModelAvailability(model_id, True, env_var)


def get_available_models() -> list[ModelAvailability]:
    return [check_model_availability(m) for m in SUPPORTED_MODELS]


def is_key_set(env_var: str) -> bool:
    return bool(os.getenv(env_var, "").strip())


def get_key_status() -> dict[str, bool]:
    """Return a dict of env_var → bool for all tracked API key env vars."""
    seen: dict[str, bool] = {}
    for env_var in SUPPORTED_MODELS.values():
        if env_var not in seen:
            seen[env_var] = is_key_set(env_var)
    return seen


def suggest_execution_mode() -> str:
    """
    Inspect available API keys and suggest the best execution mode.
    Returns: "manual" | "hybrid" | "automated"
    Design principle: never block on missing keys. If absent, route to manual.
    """
    available_count = sum(1 for avail in get_available_models() if avail.available)

    # Count unique providers actually available
    available_keys = sum(1 for v in get_key_status().values() if v)

    if available_keys == 0:
        return "manual"
    # If we have at least one key but not all four analyst providers
    elif available_keys < len(get_key_status()):
        return "hybrid"
    else:
        return "automated"


def get_model_for_analyst_index(analyst_index: int) -> tuple[Optional[str], Optional[str]]:
    """
    Returns (model_id, env_var) for an analyst slot (0-based index) if the key
    is available, or (None, None) if not — caller routes to manual in that case.
    Slot assignment follows the spec's recommended model order.
    """
    slot_models = [
        "claude-sonnet-4-6",
        "gpt-4o",
        "gemini/gemini-1.5-pro",
        "grok/grok-4-vision",
    ]
    if analyst_index >= len(slot_models):
        return None, None

    model_id = slot_models[analyst_index]
    avail = check_model_availability(model_id)
    if avail.available:
        return model_id, avail.env_var
    return None, None
