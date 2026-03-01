"""Chart-analysis prompt orchestration helpers.

This module wires the modular chart-analysis prompt pack into the existing
lens/persona pipeline without changing the external CLI contract.
"""
from __future__ import annotations

from pathlib import Path

from ..models.ground_truth import GroundTruthPacket
from ..models.lens_config import LensConfig

CHART_ANALYSIS_DIR = Path(__file__).parent.parent / "prompt_library" / "chart_analysis"

_COMPONENTS = {
    "runtime_orchestrator": "runtime.orchestrator.md",
    "base": "base.md",
    "arbiter": "arbiter.md",
    "auto_detect": "lens.auto_detect.md",
    "market_structure": "lens.market_structure.md",
    "trendlines": "lens.trendlines.md",
    "ict_smc": "lens.ict_smc.md",
    "icc_cct": "lens.icc_cct.md",
    "pinekraft_bridge": "bridge.pinekraft.md",
    "schemas": "schemas.md",
}


def load_chart_analysis_component(name: str) -> str:
    """Load a chart-analysis markdown component by logical name."""
    if name not in _COMPONENTS:
        raise KeyError(f"Unknown chart analysis component: {name}")
    path = CHART_ANALYSIS_DIR / _COMPONENTS[name]
    if not path.exists():
        raise FileNotFoundError(f"Chart analysis component not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def resolve_chart_lenses(ground_truth: GroundTruthPacket, lens_config: LensConfig) -> list[str]:
    """Resolve final chart-analysis lenses from explicit user flags + conservative auto-detect.

    User CLI flags in ``LensConfig`` are treated as explicit overrides.
    Auto-detect then opportunistically enables compatible lenses when there is typed
    evidence (e.g. ICT overlay metadata) and no explicit disable flag.
    """
    resolved: list[str] = []

    # Explicit override path from existing CLI flags.
    if lens_config.MarketStructure:
        resolved.append("market_structure")
    if lens_config.Trendlines:
        resolved.append("trendlines")

    ict_enabled = lens_config.ICT_ICC
    if ict_enabled:
        resolved.append("ict_smc")
        # ICC/CCT rides with ICT/ICC user intent by default in the modular pack.
        resolved.append("icc_cct")

    # Conservative detector: overlay metadata indicates ICT constructs.
    if ground_truth.m15_overlay_metadata and ground_truth.m15_overlay_metadata.lens == "ICT":
        if lens_config.ICT_ICC and "ict_smc" not in resolved:
            resolved.append("ict_smc")
        if lens_config.ICT_ICC and "icc_cct" not in resolved:
            resolved.append("icc_cct")

    if not resolved:
        # Guardrail in runtime.orchestrator.md: market structure stays default-on.
        resolved.append("market_structure")

    # stable deterministic order
    ordering = ["market_structure", "trendlines", "ict_smc", "icc_cct"]
    return [lens for lens in ordering if lens in resolved]
