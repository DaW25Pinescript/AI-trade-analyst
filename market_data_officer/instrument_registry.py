"""Centralised instrument metadata registry.

Single source of truth for per-instrument configuration consumed by
feed/, officer/, and structure/ sub-packages.  Phase E+ spec §8.1b.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class InstrumentMeta:
    """Instrument-specific metadata and parsing configuration.

    Attributes:
        symbol: Canonical instrument symbol (e.g. "EURUSD").
        price_scale: Dukascopy raw-integer divisor for bid/ask decoding.
        price_range: Plausible (low, high) sanity-check bounds.
        base_price: Fixture base price for deterministic test seeding.
        fixture_volatility: Fixture random-walk step size.
        fixture_volume_range: Fixture volume uniform-draw bounds.
        timeframes: Timeframes this instrument supports in the feed.
        yfinance_alias: yFinance ticker symbol (metadata only — no live calls).
        trust_level: One of "trusted", "provisional", "unverified".
        eqh_eql_tolerance: EQH/EQL tolerance for structure engine.
        fvg_min_size: Minimum FVG gap size for structure engine.
        volume_divisor: Optional volume divisor for Dukascopy decoding.
    """

    symbol: str
    price_scale: int
    price_range: Tuple[float, float] = (0.0, 0.0)
    base_price: float = 0.0
    fixture_volatility: float = 0.0
    fixture_volume_range: Tuple[float, float] = (0.0, 0.0)
    timeframes: Tuple[str, ...] = ()
    yfinance_alias: str = ""
    trust_level: str = "unverified"  # "trusted" | "provisional" | "unverified"
    eqh_eql_tolerance: float = 0.0
    fvg_min_size: float = 0.0
    volume_divisor: Optional[float] = None


# ── All timeframes used by the full FX feed pipeline ─────────────────
_FX_TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d")

# ── Metals use only the 4 analyst-target timeframes ──────────────────
_METAL_TIMEFRAMES = ("15m", "1h", "4h", "1d")


INSTRUMENT_REGISTRY: Dict[str, InstrumentMeta] = {
    "EURUSD": InstrumentMeta(
        symbol="EURUSD",
        price_scale=100_000,
        price_range=(0.8, 1.5),
        base_price=1.0850,
        fixture_volatility=0.0005,
        fixture_volume_range=(100, 5000),
        timeframes=_FX_TIMEFRAMES,
        yfinance_alias="EURUSD=X",
        trust_level="trusted",
        eqh_eql_tolerance=0.00010,
        fvg_min_size=0.0003,
    ),
    "XAUUSD": InstrumentMeta(
        symbol="XAUUSD",
        price_scale=1_000,
        price_range=(1_500.0, 3_500.0),
        base_price=2700.0,
        fixture_volatility=2.0,
        fixture_volume_range=(0.1, 10.0),
        timeframes=_METAL_TIMEFRAMES,
        yfinance_alias="GC=F",
        trust_level="trusted",
        eqh_eql_tolerance=0.50,
        fvg_min_size=0.30,
    ),
    "GBPUSD": InstrumentMeta(
        symbol="GBPUSD",
        price_scale=100_000,
        price_range=(1.15, 1.45),
        base_price=1.2700,
        fixture_volatility=0.0005,
        fixture_volume_range=(100, 5000),
        timeframes=_FX_TIMEFRAMES,
        yfinance_alias="GBPUSD=X",
        trust_level="trusted",
        eqh_eql_tolerance=0.00010,
        fvg_min_size=0.0003,
    ),
    "XAGUSD": InstrumentMeta(
        symbol="XAGUSD",
        price_scale=1_000,
        price_range=(18.00, 40.00),
        base_price=28.00,
        fixture_volatility=0.15,
        fixture_volume_range=(0.1, 50.0),
        timeframes=_METAL_TIMEFRAMES,
        yfinance_alias="SI=F",
        trust_level="trusted",
        eqh_eql_tolerance=0.10,
        fvg_min_size=0.05,
    ),
    "XPTUSD": InstrumentMeta(
        symbol="XPTUSD",
        price_scale=1_000,
        price_range=(700.00, 1_400.00),
        base_price=980.00,
        fixture_volatility=3.00,
        fixture_volume_range=(0.01, 5.0),
        timeframes=_METAL_TIMEFRAMES,
        yfinance_alias="PL=F",
        trust_level="trusted",
        eqh_eql_tolerance=0.50,
        fvg_min_size=0.30,
    ),
}


def get_meta(symbol: str) -> InstrumentMeta:
    """Look up instrument metadata by symbol.

    Raises:
        KeyError: If the symbol is not in the registry.
    """
    return INSTRUMENT_REGISTRY[symbol]
