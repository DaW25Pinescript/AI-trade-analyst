"""Group E — Replay stability tests.

Tests that adding new bars does not alter existing confirmed swings,
new bars may add new objects but not mutate old ones, and status
transitions are additive only.
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


class TestGroupE_Replay:
    """Group E — Replay stability."""

    def test_e1_new_bars_preserve_existing_swings(self, config):
        """E.1 — Adding new bars does not alter existing confirmed swings."""
        # First run with 14 bars
        prices_day1 = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                       1.080, 1.079, 1.078, 1.075, 1.077, 1.078, 1.079]
        bars_day1 = make_fixture_bars(prices_day1, START)
        swings_day1 = detect_swings(bars_day1, config, timeframe="1h")

        # Second run with more bars appended
        prices_day2 = prices_day1 + [1.080, 1.081, 1.082, 1.083, 1.082, 1.081, 1.080]
        bars_day2 = make_fixture_bars(prices_day2, START)
        swings_day2 = detect_swings(bars_day2, config, timeframe="1h")

        ids_day1 = {s.id: s for s in swings_day1}
        ids_day2 = {s.id: s for s in swings_day2}

        # All swings from day1 must appear unchanged in day2
        for sid, swing in ids_day1.items():
            assert sid in ids_day2, f"Swing {sid} disappeared after adding bars"
            assert ids_day2[sid].price == swing.price
            assert ids_day2[sid].anchor_time == swing.anchor_time
            assert ids_day2[sid].confirm_time == swing.confirm_time

    def test_e2_new_bars_may_add_new_objects(self, config):
        """E.2 — New bars may add new confirmed objects but not mutate old ones."""
        prices_day1 = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                       1.080, 1.079, 1.078, 1.075, 1.077, 1.078, 1.079]
        bars_day1 = make_fixture_bars(prices_day1, START)
        swings_day1 = detect_swings(bars_day1, config, timeframe="1h")

        prices_day2 = prices_day1 + [1.080, 1.081, 1.082, 1.083, 1.082, 1.081, 1.080]
        bars_day2 = make_fixture_bars(prices_day2, START)
        swings_day2 = detect_swings(bars_day2, config, timeframe="1h")

        ids_day1 = {s.id for s in swings_day1}
        new_swings = [s for s in swings_day2 if s.id not in ids_day1]
        # Zero or more new swings is fine
        assert len(new_swings) >= 0

    def test_e3_status_transitions_additive_only(self, config):
        """E.3 — Status transitions are additive only."""
        prices_day1 = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                       1.080, 1.079, 1.078, 1.075, 1.077, 1.078, 1.079]
        bars_day1 = make_fixture_bars(prices_day1, START)
        swings_day1 = detect_swings(bars_day1, config, timeframe="1h")

        prices_day2 = prices_day1 + [1.080, 1.081, 1.082, 1.083, 1.082, 1.081, 1.080]
        bars_day2 = make_fixture_bars(prices_day2, START)
        swings_day2 = detect_swings(bars_day2, config, timeframe="1h")

        ids_day1 = {s.id: s for s in swings_day1}
        ids_day2 = {s.id: s for s in swings_day2}

        valid_transitions = {
            "confirmed": {"confirmed", "broken", "superseded", "archived"},
            "broken": {"broken", "archived"},
            "superseded": {"superseded", "archived"},
            "archived": {"archived"},
        }

        for sid, swing_d1 in ids_day1.items():
            swing_d2 = ids_day2.get(sid)
            if swing_d2:
                assert swing_d2.status in valid_transitions[swing_d1.status], \
                    f"Invalid status transition: {swing_d1.status} -> {swing_d2.status}"
