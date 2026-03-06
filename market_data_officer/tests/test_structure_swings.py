"""Group A — Swing detection tests.

Tests confirmed swing detection, confirmation timestamps, no lookahead,
ID stability, and empty-bar handling.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structure.config import StructureConfig
from structure.swings import detect_swings


def make_fixture_bars(prices: list, start: datetime) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame from a list of close prices."""
    rows = []
    for p in prices:
        rows.append({
            "open": p,
            "high": p + 0.0005,
            "low": p - 0.0005,
            "close": p,
            "volume": 100.0,
        })
    idx = pd.date_range(start=start, periods=len(prices), freq="1h", tz="UTC")
    return pd.DataFrame(rows, index=idx)


# Fixture: clear swing high at index 3 (price 1.085) and swing low at index 10 (price 1.075)
FIXTURE_PRICES = [
    1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,  # swing high at index 3
    1.080, 1.079, 1.078, 1.075, 1.077, 1.078, 1.079,   # swing low at index 10
]
FIXTURE_START = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def config():
    return StructureConfig(pivot_left_bars=3, pivot_right_bars=3)


@pytest.fixture
def bars():
    return make_fixture_bars(FIXTURE_PRICES, FIXTURE_START)


@pytest.fixture
def swings(bars, config):
    return detect_swings(bars, config, timeframe="1h")


class TestGroupA_SwingDetection:
    """Group A — Swing detection."""

    def test_a1_confirmed_swings_detected(self, swings):
        """A.1 — Confirmed swings detected on known fixture."""
        highs = [s for s in swings if s.type == "swing_high"]
        lows = [s for s in swings if s.type == "swing_low"]

        assert len(highs) >= 1, "Expected at least one swing high"
        assert abs(highs[0].price - (1.085 + 0.0005)) < 0.001, \
            f"Swing high price mismatch: {highs[0].price}"

        assert len(lows) >= 1, "Expected at least one swing low"
        assert abs(lows[0].price - (1.075 - 0.0005)) < 0.001, \
            f"Swing low price mismatch: {lows[0].price}"

    def test_a2_confirmation_timestamps(self, swings, config):
        """A.2 — Confirmation timestamps are correct."""
        highs = [s for s in swings if s.type == "swing_high"]
        assert len(highs) >= 1

        swing_high = highs[0]
        expected_confirm = swing_high.anchor_time + timedelta(hours=config.pivot_right_bars)
        assert swing_high.confirm_time == expected_confirm, \
            f"Expected confirm_time {expected_confirm}, got {swing_high.confirm_time}"

    def test_a3_no_lookahead(self, swings, config):
        """A.3 — No pre-confirmation lookahead."""
        for swing in swings:
            delta = (swing.confirm_time - swing.anchor_time).total_seconds() / 3600
            assert delta >= config.pivot_right_bars, \
                f"Lookahead detected: {swing.id} confirmed before right bars closed"

    def test_a4_id_stability(self, bars, config):
        """A.4 — Swing IDs are stable across reruns."""
        swings_run1 = detect_swings(bars, config, timeframe="1h")
        swings_run2 = detect_swings(bars, config, timeframe="1h")

        ids_run1 = {s.id for s in swings_run1}
        ids_run2 = {s.id for s in swings_run2}
        assert ids_run1 == ids_run2, "Swing IDs changed between runs"

    def test_a5_empty_bars(self, config):
        """A.5 — Empty bars return empty swing list, no crash."""
        empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = detect_swings(empty, config)
        assert result == []

    def test_a5_insufficient_bars(self, config):
        """A.5 extended — Fewer bars than minimum returns empty list."""
        prices = [1.080, 1.081, 1.082]  # only 3 bars, need at least 7
        bars = make_fixture_bars(prices, FIXTURE_START)
        result = detect_swings(bars, config)
        assert result == []
