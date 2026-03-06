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
"""
import logging
from typing import Any

from .config_loader import load_config
from .task_types import ALL_TASK_TYPES

logger = logging.getLogger(__name__)


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
