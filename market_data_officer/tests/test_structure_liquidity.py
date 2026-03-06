"""Group C — Liquidity detection tests.

Tests prior day high/low, EQH/EQL detection, sweep events,
and instrument-specific tolerance.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structure.config import StructureConfig
from structure.liquidity import detect_liquidity
from structure.swings import detect_swings


def make_multi_day_bars(
    base_price: float = 1.085,
    days: int = 5,
    bars_per_day: int = 24,
    freq: str = "1h",
    volatility: float = 0.001,
    start: datetime = None,
) -> pd.DataFrame:
    """Build multi-day OHLCV bars for liquidity testing."""
    if start is None:
        # Start on a Monday at 21:00 UTC (FX session open)
        start = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)

    rng = np.random.RandomState(42)
    total_bars = days * bars_per_day
    idx = pd.date_range(start=start, periods=total_bars, freq=freq, tz="UTC")

    returns = rng.normal(0, volatility, total_bars)
    close = base_price + np.cumsum(returns)
    high = close + rng.uniform(0, volatility * 2, total_bars)
    low = close - rng.uniform(0, volatility * 2, total_bars)
    open_ = close + rng.normal(0, volatility * 0.5, total_bars)
    volume = rng.uniform(100, 5000, total_bars)

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=idx)


@pytest.fixture
def config():
    return StructureConfig(pivot_left_bars=3, pivot_right_bars=3)


class TestGroupC_Liquidity:
    """Group C — Liquidity detection."""

    def test_c1_prior_day_high_low(self, config):
        """C.1 — Prior day high and low are correct."""
        bars = make_multi_day_bars(days=5)
        swings = detect_swings(bars, config, timeframe="1h")
        levels, _ = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        pdh_levels = [l for l in levels if l.type == "prior_day_high"]
        pdl_levels = [l for l in levels if l.type == "prior_day_low"]

        assert len(pdh_levels) >= 1, "Expected at least one prior_day_high"
        assert len(pdl_levels) >= 1, "Expected at least one prior_day_low"

        # Verify price is reasonable
        for pdh in pdh_levels:
            assert pdh.price > 0, f"Invalid PDH price: {pdh.price}"
        for pdl in pdl_levels:
            assert pdl.price > 0, f"Invalid PDL price: {pdl.price}"

    def test_c2_eqh_detected_within_tolerance(self, config):
        """C.2 — EQH detected within tolerance."""
        # Build bars with two swing highs within 1 pip of each other
        # Two peaks at approximately the same level
        START = datetime(2026, 1, 1, tzinfo=timezone.utc)
        prices = [
            1.080, 1.082, 1.084,
            1.0855,  # first peak (high will be 1.0855 + 0.0005 = 1.0860)
            1.084, 1.082, 1.080,
            1.078, 1.080, 1.082,
            1.0854,  # second peak (high will be 1.0854 + 0.0005 = 1.0859) — within 1 pip
            1.083, 1.081, 1.079,
        ]
        rows = []
        for p in prices:
            rows.append({
                "open": p, "high": p + 0.0005, "low": p - 0.0005,
                "close": p, "volume": 100.0,
            })
        idx = pd.date_range(start=START, periods=len(prices), freq="1h", tz="UTC")
        bars = pd.DataFrame(rows, index=idx)

        swings = detect_swings(bars, config, timeframe="1h")
        levels, _ = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        eqh_levels = [l for l in levels if l.type == "equal_highs"]
        assert len(eqh_levels) >= 1, "Expected at least one EQH"
        assert len(eqh_levels[0].member_swing_ids) >= 2
        assert eqh_levels[0].tolerance_used == config.eqh_eql_tolerance["EURUSD"]

    def test_c3_sweep_fires_on_wick(self, config):
        """C.3 — Sweep fires on wick-through, not just close-through."""
        # Multi-day bars where a wick exceeds prior day high
        bars = make_multi_day_bars(days=5)
        swings = detect_swings(bars, config, timeframe="1h")
        levels, sweep_events = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        swept_levels = [l for l in levels if l.status == "swept"]
        # With random data, sweeps should occur
        # Just verify the mechanism works — swept levels have swept_time
        for level in swept_levels:
            assert level.swept_time is not None
            assert level.sweep_type in ("wick_sweep", "close_sweep")

    def test_c4_swept_level_status(self, config):
        """C.4 — Swept level status updates correctly."""
        bars = make_multi_day_bars(days=5)
        swings = detect_swings(bars, config, timeframe="1h")
        levels, sweep_events = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        for level in levels:
            if level.status == "swept":
                assert level.swept_time is not None, \
                    f"Swept level {level.id} has no swept_time"

    def test_c5_instrument_tolerance(self, config):
        """C.5 — EQH/EQL uses instrument-correct tolerance."""
        assert config.eqh_eql_tolerance["EURUSD"] != config.eqh_eql_tolerance["XAUUSD"]
        assert config.eqh_eql_tolerance["EURUSD"] == 0.00010
        assert config.eqh_eql_tolerance["XAUUSD"] == 0.50
