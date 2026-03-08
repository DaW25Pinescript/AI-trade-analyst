"""Engine configuration surface for Phase 3A/3B.

Exposes only the narrow set of parameters defined in CONSTRAINTS.md.
No configuration sprawl — keep it minimal until logic is proven.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from instrument_registry import INSTRUMENT_REGISTRY


@dataclass
class StructureConfig:
    """All configurable parameters for the Phase 3A Structure Engine."""

    # Pivot confirmation
    pivot_left_bars: int = 3
    pivot_right_bars: int = 3

    # BOS confirmation mode — "close" only in 3A
    bos_confirmation: str = "close"

    # EQH/EQL tolerance — derived from central registry
    eqh_eql_tolerance: Dict[str, float] = field(default_factory=lambda: {
        sym: meta.eqh_eql_tolerance
        for sym, meta in INSTRUMENT_REGISTRY.items()
        if meta.eqh_eql_tolerance > 0
    })

    # Enabled timeframes
    timeframes: List[str] = field(default_factory=lambda: ["15m", "1h", "4h"])

    # Session calendar for prior high/low derivation (UTC hour of day session open)
    day_session_open_utc: int = 21  # Sunday 21:00 UTC = start of FX week
    week_session_open_day: int = 6  # Sunday = 6 (ISO weekday)

    # Phase 3B — Reclaim detection
    allow_same_bar_reclaim: bool = True
    reclaim_window_bars: int = 1

    # Phase 3C — FVG detection (derived from central registry)
    fvg_min_size_eurusd: float = INSTRUMENT_REGISTRY["EURUSD"].fvg_min_size
    fvg_min_size_xauusd: float = INSTRUMENT_REGISTRY["XAUUSD"].fvg_min_size
    fvg_use_body_only: bool = True          # always True in 3C, wick mode deferred
