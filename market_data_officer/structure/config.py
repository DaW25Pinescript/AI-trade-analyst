"""Engine configuration surface for Phase 3A/3B.

Exposes only the narrow set of parameters defined in CONSTRAINTS.md.
No configuration sprawl — keep it minimal until logic is proven.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class StructureConfig:
    """All configurable parameters for the Phase 3A Structure Engine."""

    # Pivot confirmation
    pivot_left_bars: int = 3
    pivot_right_bars: int = 3

    # BOS confirmation mode — "close" only in 3A
    bos_confirmation: str = "close"

    # EQH/EQL tolerance — fixed pip/point value per instrument
    eqh_eql_tolerance: Dict[str, float] = field(default_factory=lambda: {
        "EURUSD": 0.00010,  # 1 pip
        "XAUUSD": 0.50,     # 50 cents
    })

    # Enabled timeframes
    timeframes: List[str] = field(default_factory=lambda: ["15m", "1h", "4h"])

    # Session calendar for prior high/low derivation (UTC hour of day session open)
    day_session_open_utc: int = 21  # Sunday 21:00 UTC = start of FX week
    week_session_open_day: int = 6  # Sunday = 6 (ISO weekday)

    # Phase 3B — Reclaim detection
    allow_same_bar_reclaim: bool = True
    reclaim_window_bars: int = 1
