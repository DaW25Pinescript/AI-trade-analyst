"""Load and validate llm_routing.yaml configuration.

Lazy-loads on first call; caches the result for the process lifetime.
Supports env var overrides for the proxy connection:
  - CLAUDE_PROXY_BASE_URL  → overrides llm_backend.base_url
  - LOCAL_LLM_PROXY_API_KEY → overrides llm_backend.api_key
"""
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .task_types import ALL_TASK_TYPES

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "llm_routing.yaml"
_EXAMPLE_PATH = _CONFIG_PATH.with_name("llm_routing.example.yaml")

_cached_config: dict[str, Any] | None = None

# Tokens treated as non-functional placeholders (case-insensitive).
_PLACEHOLDER_TOKENS = frozenset({
    "not-needed",
    "your_proxy_key_here",
    "changeme",
    "placeholder",
    "xxx",
    "REPLACE_ME",
})


def _classify_api_key(value: str) -> str:
    """Return a safe classification of an API key value (never the key itself)."""
    if not value:
        return "empty"
    if value.lower() in {t.lower() for t in _PLACEHOLDER_TOKENS}:
        return "placeholder-like"
    return "non-empty secret"


class ConfigurationError(Exception):
    """Raised when llm_routing.yaml is missing or malformed."""


def _validate(config: dict[str, Any]) -> None:
    """Validate required keys in the loaded config."""
    if "llm_backend" not in config:
        raise ConfigurationError("llm_routing.yaml missing required key: 'llm_backend'")
    backend = config["llm_backend"]
    for key in ("mode", "base_url", "api_key"):
        if key not in backend:
            raise ConfigurationError(f"llm_backend missing required key: '{key}'")

    if "task_routing" not in config:
        raise ConfigurationError("llm_routing.yaml missing required key: 'task_routing'")
    routing = config["task_routing"]
    for task_type in ALL_TASK_TYPES:
        if task_type not in routing:
            raise ConfigurationError(f"task_routing missing entry for task type: '{task_type}'")
        entry = routing[task_type]
        for key in ("primary_model", "fallback_model", "retries"):
            if key not in entry:
                raise ConfigurationError(
                    f"task_routing.{task_type} missing required key: '{key}'"
                )

    # Validate analyst_roster if present
    if "analyst_roster" in config:
        _validate_analyst_roster(config["analyst_roster"])


def _validate_analyst_roster(roster: Any) -> None:
    """Validate analyst_roster entries have required keys and valid persona values."""
    if not isinstance(roster, list):
        raise ConfigurationError("analyst_roster must be a list")

    # Import here to avoid circular imports at module level
    from ..models.persona import PersonaType

    valid_personas = {p.value for p in PersonaType}

    for i, entry in enumerate(roster):
        if not isinstance(entry, dict):
            raise ConfigurationError(f"analyst_roster[{i}] must be a mapping")
        if "model" not in entry:
            raise ConfigurationError(f"analyst_roster[{i}] missing required key: 'model'")
        if "persona" not in entry:
            raise ConfigurationError(f"analyst_roster[{i}] missing required key: 'persona'")
        if entry["persona"] not in valid_personas:
            raise ConfigurationError(
                f"analyst_roster[{i}] has invalid persona '{entry['persona']}'. "
                f"Valid: {sorted(valid_personas)}"
            )


def load_config(*, force_reload: bool = False) -> dict[str, Any]:
    """Load and cache the LLM routing configuration.

    Tries config/llm_routing.yaml first, falls back to
    config/llm_routing.example.yaml if the primary file does not exist.
    """
    global _cached_config
    if _cached_config is not None and not force_reload:
        return _cached_config

    path = _CONFIG_PATH if _CONFIG_PATH.exists() else _EXAMPLE_PATH
    if not path.exists():
        raise ConfigurationError(
            f"Neither {_CONFIG_PATH} nor {_EXAMPLE_PATH} found. "
            "Copy config/llm_routing.example.yaml to config/llm_routing.yaml and customise."
        )

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ConfigurationError(f"llm_routing config at {path} is not a valid YAML mapping.")

    _validate(config)

    backend = config["llm_backend"]

    # Apply env var override for base URL
    env_base_url = os.getenv("CLAUDE_PROXY_BASE_URL")
    if env_base_url:
        backend["base_url"] = env_base_url

    # Apply env var override for API key
    env_api_key = os.getenv("LOCAL_LLM_PROXY_API_KEY", "")
    api_key_source: str
    if env_api_key:
        backend["api_key"] = env_api_key
        api_key_source = "env (LOCAL_LLM_PROXY_API_KEY)"
    else:
        api_key_source = f"config file ({path.name})"

    # Diagnostic log (never leaks the actual key)
    logger.info(
        "[config_loader] config_file=%s | api_key source=%s | api_key class=%s",
        path,
        api_key_source,
        _classify_api_key(backend["api_key"]),
    )

    _cached_config = config
    return _cached_config
