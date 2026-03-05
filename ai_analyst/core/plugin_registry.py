"""
Phase 8d — Plugin/Extension Architecture.

Provides a registry for pluggable components:
  1. Analyst Personas — custom analyst personality configurations
  2. Data Sources — custom market data adapters (beyond Finnhub/FRED/GDELT)
  3. Hooks — webhook/callback integrations (post-verdict, post-AAR, etc.)

Plugins are discovered from:
  - Built-in defaults (always available)
  - `plugins/` directory in the project root (JSON/Python plugin manifests)
  - Environment variable `AI_ANALYST_PLUGINS_DIR` (custom plugin directory)

Plugin manifest format (JSON):
    {
        "name": "my_plugin",
        "version": "1.0.0",
        "type": "persona" | "data_source" | "hook",
        "description": "...",
        "config": { ... }
    }

Usage:
    from ai_analyst.core.plugin_registry import PluginRegistry, registry

    # Use the module-level singleton
    registry.discover_builtins()
    registry.discover_plugins()  # scans plugin directories

    # List registered plugins
    personas = registry.list_personas()
    sources = registry.list_data_sources()
    hooks = registry.list_hooks()

    # Register a new plugin programmatically
    registry.register_persona(PersonaPlugin(...))
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class PluginType(str, Enum):
    PERSONA = "persona"
    DATA_SOURCE = "data_source"
    HOOK = "hook"


class HookEvent(str, Enum):
    """Events that hooks can subscribe to."""
    POST_VERDICT = "post_verdict"
    POST_AAR = "post_aar"
    POST_BACKTEST = "post_backtest"
    PIPELINE_ERROR = "pipeline_error"


# ── Plugin data classes ──────────────────────────────────────────────────────


@dataclass
class PersonaPlugin:
    """A pluggable analyst persona configuration."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    system_prompt: str = ""
    model_preference: str = ""  # preferred LLM model
    temperature: float = 0.2
    risk_appetite: str = "moderate"  # conservative, moderate, aggressive
    specialization: str = ""  # e.g. "ICT", "orderflow", "macro"
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataSourcePlugin:
    """A pluggable data source adapter."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    source_type: str = ""  # "rest_api", "websocket", "file", "database"
    base_url: str = ""
    auth_env_var: str = ""  # env var name for API key
    refresh_interval_seconds: int = 300
    instruments: list[str] = field(default_factory=list)  # supported instruments
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookPlugin:
    """A pluggable webhook/callback integration."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    events: list[HookEvent] = field(default_factory=list)
    webhook_url: str = ""
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    # In-process callback (optional, for Python plugins)
    _callback: Optional[Callable] = field(default=None, repr=False)


# ── Registry ─────────────────────────────────────────────────────────────────


class PluginRegistry:
    """Central registry for all plugin types."""

    def __init__(self) -> None:
        self._personas: dict[str, PersonaPlugin] = {}
        self._data_sources: dict[str, DataSourcePlugin] = {}
        self._hooks: dict[str, HookPlugin] = {}

    # ── Registration ─────────────────────────────────────────────────────

    def register_persona(self, plugin: PersonaPlugin) -> None:
        self._personas[plugin.name] = plugin
        logger.info("Registered persona plugin: %s v%s", plugin.name, plugin.version)

    def register_data_source(self, plugin: DataSourcePlugin) -> None:
        self._data_sources[plugin.name] = plugin
        logger.info("Registered data source plugin: %s v%s", plugin.name, plugin.version)

    def register_hook(self, plugin: HookPlugin) -> None:
        self._hooks[plugin.name] = plugin
        logger.info("Registered hook plugin: %s v%s", plugin.name, plugin.version)

    # ── Queries ──────────────────────────────────────────────────────────

    def list_personas(self) -> list[PersonaPlugin]:
        return list(self._personas.values())

    def list_data_sources(self) -> list[DataSourcePlugin]:
        return list(self._data_sources.values())

    def list_hooks(self) -> list[HookPlugin]:
        return list(self._hooks.values())

    def get_persona(self, name: str) -> Optional[PersonaPlugin]:
        return self._personas.get(name)

    def get_data_source(self, name: str) -> Optional[DataSourcePlugin]:
        return self._data_sources.get(name)

    def get_hooks_for_event(self, event: HookEvent) -> list[HookPlugin]:
        return [h for h in self._hooks.values() if event in h.events and h.enabled]

    @property
    def total_plugins(self) -> int:
        return len(self._personas) + len(self._data_sources) + len(self._hooks)

    # ── Discovery ────────────────────────────────────────────────────────

    def discover_builtins(self) -> int:
        """Register built-in default plugins. Returns count registered."""
        count = 0

        # Built-in personas
        builtins = [
            PersonaPlugin(
                name="default_analyst",
                description="Standard multi-timeframe ICT/market-structure analyst",
                specialization="general",
                risk_appetite="moderate",
                temperature=0.2,
            ),
            PersonaPlugin(
                name="risk_officer",
                description="Conservative risk-focused analyst, emphasizes invalidation and disqualifiers",
                specialization="risk_management",
                risk_appetite="conservative",
                temperature=0.1,
            ),
            PersonaPlugin(
                name="prosecutor",
                description="Adversarial analyst, actively seeks reasons to reject the trade",
                specialization="adversarial",
                risk_appetite="conservative",
                temperature=0.3,
            ),
            PersonaPlugin(
                name="ict_purist",
                description="Strict ICT methodology adherent, rejects non-ICT setups",
                specialization="ICT",
                risk_appetite="moderate",
                temperature=0.15,
            ),
        ]

        for p in builtins:
            if p.name not in self._personas:
                self.register_persona(p)
                count += 1

        # Built-in data sources
        builtin_sources = [
            DataSourcePlugin(
                name="finnhub",
                description="Finnhub market data (equities, forex, crypto)",
                source_type="rest_api",
                base_url="https://finnhub.io/api/v1",
                auth_env_var="FINNHUB_API_KEY",
                refresh_interval_seconds=300,
                instruments=["SPX", "NQ", "XAUUSD", "EURUSD"],
            ),
            DataSourcePlugin(
                name="fred",
                description="Federal Reserve Economic Data (macro indicators)",
                source_type="rest_api",
                base_url="https://api.stlouisfed.org/fred",
                auth_env_var="FRED_API_KEY",
                refresh_interval_seconds=3600,
                instruments=["T10Y", "VIX", "DXY"],
            ),
            DataSourcePlugin(
                name="gdelt",
                description="GDELT Project (global news/events)",
                source_type="rest_api",
                base_url="https://api.gdeltproject.org/api/v2",
                auth_env_var="",  # no auth needed
                refresh_interval_seconds=900,
            ),
        ]

        for s in builtin_sources:
            if s.name not in self._data_sources:
                self.register_data_source(s)
                count += 1

        return count

    def discover_plugins(self, plugin_dir: Optional[Path] = None) -> int:
        """
        Scan a directory for plugin manifest files (*.plugin.json).

        Returns count of newly registered plugins.
        """
        dirs_to_scan: list[Path] = []

        # Default plugin directory
        project_root = Path(__file__).parent.parent.parent
        default_dir = project_root / "plugins"
        if default_dir.is_dir():
            dirs_to_scan.append(default_dir)

        # Custom directory from env
        env_dir = os.environ.get("AI_ANALYST_PLUGINS_DIR")
        if env_dir:
            custom = Path(env_dir)
            if custom.is_dir():
                dirs_to_scan.append(custom)

        # Explicit override
        if plugin_dir and plugin_dir.is_dir():
            dirs_to_scan.append(plugin_dir)

        count = 0
        for d in dirs_to_scan:
            for manifest_path in sorted(d.glob("*.plugin.json")):
                try:
                    count += self._load_manifest(manifest_path)
                except Exception as e:
                    logger.warning("Failed to load plugin %s: %s", manifest_path, e)

        return count

    def _load_manifest(self, path: Path) -> int:
        """Load a single plugin manifest file. Returns 1 if registered, 0 if skipped."""
        data = json.loads(path.read_text(encoding="utf-8"))
        ptype = data.get("type", "")
        name = data.get("name", "")

        if not name:
            logger.warning("Plugin manifest %s missing 'name' field", path)
            return 0

        if ptype == "persona":
            plugin = PersonaPlugin(
                name=name,
                version=data.get("version", "1.0.0"),
                description=data.get("description", ""),
                system_prompt=data.get("config", {}).get("system_prompt", ""),
                model_preference=data.get("config", {}).get("model_preference", ""),
                temperature=data.get("config", {}).get("temperature", 0.2),
                risk_appetite=data.get("config", {}).get("risk_appetite", "moderate"),
                specialization=data.get("config", {}).get("specialization", ""),
                config=data.get("config", {}),
            )
            self.register_persona(plugin)
            return 1

        elif ptype == "data_source":
            plugin = DataSourcePlugin(
                name=name,
                version=data.get("version", "1.0.0"),
                description=data.get("description", ""),
                source_type=data.get("config", {}).get("source_type", "rest_api"),
                base_url=data.get("config", {}).get("base_url", ""),
                auth_env_var=data.get("config", {}).get("auth_env_var", ""),
                refresh_interval_seconds=data.get("config", {}).get("refresh_interval_seconds", 300),
                instruments=data.get("config", {}).get("instruments", []),
                config=data.get("config", {}),
            )
            self.register_data_source(plugin)
            return 1

        elif ptype == "hook":
            events = []
            for e in data.get("config", {}).get("events", []):
                try:
                    events.append(HookEvent(e))
                except ValueError:
                    logger.warning("Unknown hook event '%s' in %s", e, path)

            plugin = HookPlugin(
                name=name,
                version=data.get("version", "1.0.0"),
                description=data.get("description", ""),
                events=events,
                webhook_url=data.get("config", {}).get("webhook_url", ""),
                method=data.get("config", {}).get("method", "POST"),
                headers=data.get("config", {}).get("headers", {}),
                config=data.get("config", {}),
            )
            self.register_hook(plugin)
            return 1

        else:
            logger.warning("Unknown plugin type '%s' in %s", ptype, path)
            return 0

    def format_summary(self) -> str:
        """Human-readable summary of all registered plugins."""
        lines = [
            "=" * 50,
            "  PLUGIN REGISTRY",
            "=" * 50,
            f"  Total plugins: {self.total_plugins}",
            "",
        ]

        if self._personas:
            lines.append("  -- PERSONAS " + "-" * 36)
            for p in self._personas.values():
                status = "ON" if p.enabled else "OFF"
                lines.append(f"    [{status}] {p.name} v{p.version}")
                if p.description:
                    lines.append(f"          {p.description}")
            lines.append("")

        if self._data_sources:
            lines.append("  -- DATA SOURCES " + "-" * 31)
            for s in self._data_sources.values():
                status = "ON" if s.enabled else "OFF"
                lines.append(f"    [{status}] {s.name} v{s.version} ({s.source_type})")
                if s.description:
                    lines.append(f"          {s.description}")
            lines.append("")

        if self._hooks:
            lines.append("  -- HOOKS " + "-" * 38)
            for h in self._hooks.values():
                status = "ON" if h.enabled else "OFF"
                events = ", ".join(e.value for e in h.events)
                lines.append(f"    [{status}] {h.name} v{h.version}")
                if events:
                    lines.append(f"          events: {events}")
                if h.description:
                    lines.append(f"          {h.description}")
            lines.append("")

        lines.append("=" * 50)
        return "\n".join(lines)


# Module-level singleton
registry = PluginRegistry()
