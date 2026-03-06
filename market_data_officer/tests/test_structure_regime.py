"""Group D — Determinism tests and regime summary.

Tests that identical inputs produce identical packets, IDs are stable,
and regime summary is correctly derived.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structure.config import StructureConfig
from structure.events import detect_events
from structure.liquidity import detect_liquidity
from structure.regime import compute_regime
from structure.schemas import StructureEvent
from structure.swings import detect_swings


def make_fixture_bars(prices: list, start: datetime) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame."""
    rows = []
    for p in prices:
        rows.append({
            "open": p, "high": p + 0.0005, "low": p - 0.0005,
            "close": p, "volume": 100.0,
        })
    idx = pd.date_range(start=start, periods=len(prices), freq="1h", tz="UTC")
    return pd.DataFrame(rows, index=idx)


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def config():
    return StructureConfig(pivot_left_bars=3, pivot_right_bars=3)


class TestGroupD_Determinism:
    """Group D — Determinism."""

    def test_d1_identical_inputs_identical_output(self, config):
        """D.1 — Identical inputs produce identical packet."""
        prices = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                  1.080, 1.079, 1.078, 1.075, 1.077, 1.078, 1.079]
        bars = make_fixture_bars(prices, START)

        swings_a = detect_swings(bars, config, timeframe="1h")
        events_a = detect_events(bars, swings_a, config, timeframe="1h")

        swings_b = detect_swings(bars, config, timeframe="1h")
        events_b = detect_events(bars, swings_b, config, timeframe="1h")

        # Swing objects must be identical
        assert len(swings_a) == len(swings_b)
        for sa, sb in zip(swings_a, swings_b):
            assert sa.to_dict() == sb.to_dict()

        # Event objects must be identical
        assert len(events_a) == len(events_b)
        for ea, eb in zip(events_a, events_b):
            assert ea.to_dict() == eb.to_dict()

    def test_d2_swing_ids_hash_stable(self, config):
        """D.2 — Swing IDs are hash-stable from bar data."""
        prices = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                  1.080, 1.079, 1.078, 1.075, 1.077, 1.078, 1.079]
        bars = make_fixture_bars(prices, START)

        swings = detect_swings(bars, config, timeframe="1h")
        highs = [s for s in swings if s.type == "swing_high"]

        if highs:
            anchor_time = highs[0].anchor_time
            expected_id = f"sw_1h_{anchor_time.strftime('%Y%m%dT%H%M')}_sh"
            assert highs[0].id == expected_id

    def test_d3_as_of_differs_but_structure_same(self, config):
        """D.3 — as_of field may differ but structure objects don't change."""
        prices = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                  1.080, 1.079, 1.078, 1.075, 1.077, 1.078, 1.079]
        bars = make_fixture_bars(prices, START)

        swings_a = detect_swings(bars, config, timeframe="1h")
        swings_b = detect_swings(bars, config, timeframe="1h")

        ids_a = [s.id for s in swings_a]
        ids_b = [s.id for s in swings_b]
        assert ids_a == ids_b

    def test_regime_neutral_on_no_events(self, config):
        """Regime returns neutral when no events exist."""
        regime = compute_regime([], [])
        assert regime.bias == "neutral"
        assert regime.last_bos_direction is None
        assert regime.last_mss_direction is None
        assert regime.trend_state == "unknown"
        assert regime.structure_quality == "unknown"

    def test_regime_bullish_on_bull_bos(self, config):
        """Regime reflects bullish bias after bos_bull."""
        event = StructureEvent(
            id="ev_1h_test_bos_bull",
            type="bos_bull",
            time=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
            timeframe="1h",
            reference_swing_id="sw_test",
            reference_price=1.085,
            break_close=1.086,
        )
        regime = compute_regime([], [event])
        assert regime.bias == "bullish"
        assert regime.last_bos_direction == "bullish"
