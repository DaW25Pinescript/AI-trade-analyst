"""Group B — BOS and MSS event tests.

Tests BOS close-confirmation, wick-only rejection, MSS directional
transitions, and event ordering constraints.
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from market_data_officer.structure.config import StructureConfig
from market_data_officer.structure.events import detect_events
from market_data_officer.structure.swings import detect_swings


def make_bars_with_wicks(
    prices: list,
    wicks: dict,
    start: datetime,
) -> pd.DataFrame:
    """Build OHLCV bars with custom wicks at specified indices.

    Args:
        prices: List of close prices.
        wicks: Dict mapping index -> (high_override, low_override).
        start: Start timestamp.
    """
    rows = []
    for i, p in enumerate(prices):
        high = p + 0.0005
        low = p - 0.0005
        if i in wicks:
            if wicks[i][0] is not None:
                high = wicks[i][0]
            if wicks[i][1] is not None:
                low = wicks[i][1]
        rows.append({
            "open": p,
            "high": high,
            "low": low,
            "close": p,
            "volume": 100.0,
        })
    idx = pd.date_range(start=start, periods=len(prices), freq="1h", tz="UTC")
    return pd.DataFrame(rows, index=idx)


@pytest.fixture
def config():
    return StructureConfig(pivot_left_bars=3, pivot_right_bars=3)


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestGroupB_BOS_MSS:
    """Group B — BOS and MSS events."""

    def test_b1_bos_wick_only_rejected(self, config):
        """B.1 — BOS does not fire on wick-only breach."""
        # Swing high at index 3 with high = 1.085 + 0.0005 = 1.0855
        prices = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                  1.082, 1.083, 1.084]
        # Bar 9: wick to 1.0860 but close at 1.084 (below swing high of 1.0855)
        wicks = {9: (1.0860, None)}
        bars = make_bars_with_wicks(prices, wicks, START)

        swings = detect_swings(bars, config, timeframe="1h")
        events = detect_events(bars, swings, config, timeframe="1h")

        bos_events = [e for e in events if "bos" in e.type]
        assert len(bos_events) == 0, "BOS must not fire on wick-only breach"

    def test_b1_bos_fires_on_close_break(self, config):
        """B.1 — BOS fires when close breaks above swing high."""
        # Swing high at index 3, high = 1.0855
        # Bar 9: close at 1.086 (above 1.0855)
        prices = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                  1.082, 1.083, 1.086]
        bars = make_bars_with_wicks(prices, {}, START)

        swings = detect_swings(bars, config, timeframe="1h")
        events = detect_events(bars, swings, config, timeframe="1h")

        bos_bull = [e for e in events if e.type == "bos_bull"]
        assert len(bos_bull) >= 1, "Expected at least one bos_bull event"
        assert bos_bull[0].break_close > 1.085

    def test_b2_bos_links_to_correct_swing(self, config):
        """B.2 — BOS event links to correct reference swing."""
        prices = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                  1.082, 1.083, 1.086]
        bars = make_bars_with_wicks(prices, {}, START)

        swings = detect_swings(bars, config, timeframe="1h")
        events = detect_events(bars, swings, config, timeframe="1h")

        bos_bull = [e for e in events if e.type == "bos_bull"]
        assert len(bos_bull) >= 1

        bos = bos_bull[0]
        ref_swing = next(s for s in swings if s.id == bos.reference_swing_id)
        assert abs(bos.reference_price - ref_swing.price) < 0.00001

    def test_b3_mss_fires_on_direction_change(self, config):
        """B.3 — MSS fires only on valid directional transition."""
        # Build sequence: bearish BOS first, then bullish BOS → should emit mss_bull
        # Structure: swing high at idx 3, then swing low at idx 10,
        # close below swing low (bos_bear), then new swing high + close above (bos_bull → mss_bull)
        prices = [
            1.085, 1.086, 1.087, 1.090, 1.088, 1.087, 1.086,  # swing high at 3
            1.084, 1.083, 1.082, 1.079, 1.081, 1.082, 1.083,   # swing low at 10
            1.078,                                               # close below SL → bos_bear
            1.080, 1.082, 1.084, 1.087, 1.085, 1.084, 1.083,   # swing high at 18
            1.085, 1.086, 1.088,                                 # close above → mss_bull
        ]
        bars = make_bars_with_wicks(prices, {}, START)

        swings = detect_swings(bars, config, timeframe="1h")
        events = detect_events(bars, swings, config, timeframe="1h")

        mss_events = [e for e in events if "mss" in e.type]
        assert len(mss_events) >= 1, "Expected at least one MSS event"
        assert mss_events[0].type == "mss_bull"
        assert mss_events[0].prior_bias == "bearish"

    def test_b4_mss_prior_bias_populated(self, config):
        """B.4 — MSS prior_bias field is populated."""
        prices = [
            1.085, 1.086, 1.087, 1.090, 1.088, 1.087, 1.086,
            1.084, 1.083, 1.082, 1.079, 1.081, 1.082, 1.083,
            1.078,
            1.080, 1.082, 1.084, 1.087, 1.085, 1.084, 1.083,
            1.085, 1.086, 1.088,
        ]
        bars = make_bars_with_wicks(prices, {}, START)
        swings = detect_swings(bars, config, timeframe="1h")
        events = detect_events(bars, swings, config, timeframe="1h")

        for mss in [e for e in events if "mss" in e.type]:
            assert mss.prior_bias in ("bullish", "bearish"), \
                f"MSS missing prior_bias: {mss.id}"

    def test_b5_no_bos_before_swing_confirmed(self, config):
        """B.5 — No BOS before its reference swing is confirmed."""
        prices = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                  1.082, 1.083, 1.086]
        bars = make_bars_with_wicks(prices, {}, START)

        swings = detect_swings(bars, config, timeframe="1h")
        events = detect_events(bars, swings, config, timeframe="1h")

        for event in [e for e in events if "bos" in e.type or "mss" in e.type]:
            ref_swing = next(
                (s for s in swings if s.id == event.reference_swing_id), None
            )
            if ref_swing:
                assert event.time >= ref_swing.confirm_time, \
                    f"BOS {event.id} fires before reference swing confirmed"
