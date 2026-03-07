"""Group F (F.2, F.3, F.4) — XAUUSD cross-instrument tests.

Tests full structure suite on XAUUSD across 15m, 1h, 4h,
including price range guard and instrument-specific tolerance.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structure.config import StructureConfig
from structure.engine import compute_structure_packet


def generate_xauusd_bars(
    timeframe: str,
    periods: int = 240,
    base_price: float = 2650.0,
) -> pd.DataFrame:
    """Generate synthetic XAUUSD OHLCV bars for testing."""
    rng = np.random.RandomState(42)

    freq_map = {"15m": "15min", "1h": "1h", "4h": "4h"}
    freq = freq_map[timeframe]

    start = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)
    idx = pd.date_range(start=start, periods=periods, freq=freq, tz="UTC")

    volatility = 2.0  # Gold moves in dollars
    returns = rng.normal(0, volatility, periods)
    close = base_price + np.cumsum(returns)
    high = close + rng.uniform(0, volatility * 2, periods)
    low = close - rng.uniform(0, volatility * 2, periods)
    open_ = close + rng.normal(0, volatility * 0.5, periods)
    volume = rng.uniform(100, 5000, periods)

    return pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume,
    }, index=idx)


@pytest.fixture
def config():
    return StructureConfig(pivot_left_bars=3, pivot_right_bars=3)


class TestGroupF2_XAUUSD:
    """Group F.2 — XAUUSD passes full structure suite on 15m, 1h, 4h."""

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_xauusd_structure_packet(self, config, tf):
        """Full structure computation completes without error."""
        bars = generate_xauusd_bars(tf)
        packet = compute_structure_packet("XAUUSD", tf, config, bars=bars)

        assert packet.schema_version == "structure_packet_v1"
        assert packet.instrument == "XAUUSD"
        assert packet.timeframe == tf
        assert len(packet.swings) > 0, f"No swings detected for XAUUSD {tf}"


class TestGroupF3_XAUUSD_PriceRange:
    """Group F.3 — XAUUSD price range guard."""

    def test_xauusd_price_range(self, config):
        """F.3 — All XAUUSD swing prices within plausible range."""
        bars = generate_xauusd_bars("1h")
        packet = compute_structure_packet("XAUUSD", "1h", config, bars=bars)

        all_swing_prices = [s.price for s in packet.swings]
        for price in all_swing_prices:
            assert 1_500.0 < price < 3_500.0, \
                f"XAUUSD swing price out of plausible range: {price}"


class TestGroupF4_Tolerance:
    """Group F.4 — Engine uses correct EQH/EQL tolerance per instrument."""

    def test_xauusd_tolerance(self, config):
        """XAUUSD uses 0.50 tolerance, not EURUSD tolerance."""
        bars = generate_xauusd_bars("1h")
        packet = compute_structure_packet("XAUUSD", "1h", config, bars=bars)

        eqh_levels = [l for l in packet.liquidity if l.type == "equal_highs"]
        for level in eqh_levels:
            assert level.tolerance_used == 0.50

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_xauusd_timeframe_consistency(self, config, tf):
        """G.1 for XAUUSD — Each timeframe packet has correct timeframe field."""
        bars = generate_xauusd_bars(tf)
        packet = compute_structure_packet("XAUUSD", tf, config, bars=bars)

        assert packet.timeframe == tf
        for swing in packet.swings:
            assert swing.timeframe == tf
        for event in packet.events:
            assert event.timeframe == tf

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_xauusd_no_impossible_ordering(self, config, tf):
        """G.2 for XAUUSD — No impossible event ordering."""
        bars = generate_xauusd_bars(tf)
        packet = compute_structure_packet("XAUUSD", tf, config, bars=bars)

        for event in packet.events:
            ref_swing = next(
                (s for s in packet.swings if s.id == event.reference_swing_id), None,
            )
            if ref_swing:
                assert event.time >= ref_swing.confirm_time, \
                    f"Event {event.id} fires before reference swing confirmed"


# ---------------------------------------------------------------------------
# Phase 3B — XAUUSD cross-instrument tests (Groups F, G)
# ---------------------------------------------------------------------------

class TestGroup3B_F2_XAUUSD:
    """TF.2 — XAUUSD passes all 3B Groups A–E."""

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3b_xauusd_liquidity_scope_populated(self, config, tf):
        """3B F.2 — All XAUUSD liquidity levels have liquidity_scope."""
        bars = generate_xauusd_bars(tf)
        packet = compute_structure_packet("XAUUSD", tf, config, bars=bars)

        for level in packet.liquidity:
            assert level.liquidity_scope is not None, \
                f"Level {level.id} missing liquidity_scope"

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3b_xauusd_prior_levels_external(self, config, tf):
        """3B F.2 — Prior day/week levels tagged external for XAUUSD."""
        bars = generate_xauusd_bars(tf)
        packet = compute_structure_packet("XAUUSD", tf, config, bars=bars)

        for level in packet.liquidity:
            if level.type in ("prior_day_high", "prior_day_low",
                              "prior_week_high", "prior_week_low"):
                assert level.liquidity_scope == "external_liquidity"

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3b_xauusd_sweep_outcome_consistency(self, config, tf):
        """3B F.2 — Sweep outcome mirrors level outcome for XAUUSD."""
        bars = generate_xauusd_bars(tf)
        packet = compute_structure_packet("XAUUSD", tf, config, bars=bars)

        level_map = {l.id: l for l in packet.liquidity}
        for sw in packet.sweep_events:
            linked = level_map.get(sw.linked_liquidity_id)
            if linked:
                assert sw.outcome == linked.outcome
                assert sw.reclaim_time == linked.reclaim_time

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3b_xauusd_classification_valid(self, config, tf):
        """3B F.2 — All swept XAUUSD levels have valid outcome."""
        bars = generate_xauusd_bars(tf)
        packet = compute_structure_packet("XAUUSD", tf, config, bars=bars)

        for level in packet.liquidity:
            if level.outcome is not None:
                assert level.outcome in ("reclaimed", "accepted_beyond", "unresolved")

    def test_3b_tf3_xauusd_uses_own_tolerance(self, config):
        """TF.3 — XAUUSD uses its own tolerance, not EURUSD tolerance."""
        assert config.eqh_eql_tolerance["EURUSD"] != config.eqh_eql_tolerance["XAUUSD"]

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3b_xauusd_engine_version(self, config, tf):
        """TG.4 — engine_version is phase_3b in XAUUSD packets."""
        bars = generate_xauusd_bars(tf)
        packet = compute_structure_packet("XAUUSD", tf, config, bars=bars)
        assert packet.build["engine_version"] == "phase_3c"
