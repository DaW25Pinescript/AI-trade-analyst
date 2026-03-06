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
    # Phase 1B — XAUUSD (verified)
    # Verification performed against Dukascopy bi5 data for 2025-01-16 14:00 UTC:
    #   1. price_scale=1000 CONFIRMED: raw ask=2715695 / 1000 = $2715.695,
    #      consistent with known XAUUSD spot ~$2702-2720 mid-January 2025.
    #   2. Volume: raw float lots, no divisor needed. XAUUSD tick volumes are
    #      naturally smaller (~0.0006/tick) vs EURUSD (~5.3/tick). This is expected
    #      for gold spot on Dukascopy and does not indicate a scale error.
    #   3. Session/gap behaviour: XAUUSD trades ~23h/day (Sun 22:00–Fri 22:00 UTC)
    #      similar to EURUSD. Weekend gaps are handled identically by the pipeline.
    # UNVERIFIED / TODO:
    #   - Volume units have not been cross-checked against a trusted external
    #     reference (e.g. CME gold futures volume). The raw Dukascopy float values
    #     are ingested as-is. If a volume_divisor is later found to be needed,
    #     the canonical archive will need to be rebuilt for XAUUSD.
    "XAUUSD": InstrumentMeta(symbol="XAUUSD", price_scale=1_000),
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
REPORTS_DIR = DATA_ROOT / "reports"

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
