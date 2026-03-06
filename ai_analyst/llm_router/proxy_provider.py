"""Proxy-specific connection configuration.

Encapsulates the local CLIProxyAPI connection details so they are
not scattered across the codebase.
"""
from typing import Any

from .config_loader import load_config


def get_proxy_config() -> dict[str, Any]:
    """Return the proxy connection dict from the loaded config."""
    config = load_config()
    backend = config["llm_backend"]
    return {
        "mode": backend["mode"],
        "base_url": backend["base_url"],
        "api_key": backend["api_key"],
    }


def is_local_proxy_mode() -> bool:
    """Return True if the current config uses local_claude_proxy mode."""
    config = load_config()
    return config["llm_backend"].get("mode") == "local_claude_proxy"
