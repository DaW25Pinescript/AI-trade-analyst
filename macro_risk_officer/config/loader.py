"""
Config loader for macro_risk_officer.

Loads thresholds.yaml and weights.yaml once per process (module-level cache)
and exposes typed accessor functions. All components (ReasoningEngine,
DecayManager, MacroScheduler) call these instead of hardcoding constants.

This makes every tunable parameter configurable via YAML without code
changes — eliminating the config-drift gap from MRO-P1/P2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

_CONFIG_DIR = Path(__file__).parent
_cache: Dict[str, Any] = {}


def _load(filename: str) -> dict:
    """Load and cache a YAML config file from the config directory."""
    if filename not in _cache:
        path = _CONFIG_DIR / filename
        with open(path, "r") as fh:
            _cache[filename] = yaml.safe_load(fh)
    return _cache[filename]


def load_thresholds() -> dict:
    """Return the parsed contents of thresholds.yaml."""
    return _load("thresholds.yaml")


def load_weights() -> dict:
    """Return the parsed contents of weights.yaml."""
    return _load("weights.yaml")


def _clear_cache() -> None:
    """Clear the module-level cache. Used in tests only."""
    _cache.clear()
