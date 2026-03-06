"""Configuration and instrument metadata for the market data feed pipeline."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class InstrumentMeta:
    """Instrument-specific parsing metadata."""

    symbol: str
    price_scale: int
    volume_divisor: Optional[float] = None


INSTRUMENTS = {
    "EURUSD": InstrumentMeta(symbol="EURUSD", price_scale=100_000),
    # TODO Phase 1B — XAUUSD
    # DO NOT populate until the following are independently verified:
    #   1. Dukascopy price_scale for XAUUSD (likely 1000, but MUST be confirmed
    #      against a known reference bar — e.g. compare decoded close vs CMC/TradingView)
    #   2. Volume interpretation for XAUUSD (lots? units? divisor needed?)
    #   3. Any session/gap behaviour differences vs EURUSD
    # Populating with unverified values will silently corrupt the canonical archive.
    # "XAUUSD": InstrumentMeta(symbol="XAUUSD", price_scale=???, volume_divisor=???),
}

# Tick struct size: 5 fields × 4 bytes each = 20 bytes per tick
TICK_STRUCT_SIZE = 20

# Dukascopy base URL
DUKASCOPY_BASE_URL = "https://www.dukascopy.com/datafeed"

# Data directories
DATA_ROOT = Path("market_data")
RAW_DIR = DATA_ROOT / "raw" / "dukascopy"
CANONICAL_DIR = DATA_ROOT / "canonical"
DERIVED_DIR = DATA_ROOT / "derived"
PACKAGES_DIR = DATA_ROOT / "packages" / "latest"

# Rolling tail window sizes for hot package export
HOT_WINDOW_SIZES = {
    "1m": 3000,
    "5m": 1200,
    "15m": 600,
    "1h": 240,
    "4h": 120,
    "1d": 30,
}

# Derived timeframe resample rules
DERIVED_TIMEFRAMES = ["5min", "15min", "1h", "4h", "1D"]

# Mapping from resample rule to label
TIMEFRAME_LABELS = {
    "5min": "5m",
    "15min": "15m",
    "1h": "1h",
    "4h": "4h",
    "1D": "1d",
}
