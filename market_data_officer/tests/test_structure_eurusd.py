"""Group F (F.1) + Group G — EURUSD cross-instrument and timeframe tests.

Tests full structure suite on EURUSD across 15m, 1h, 4h using
synthetic data (hot packages not available in test environment).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structure.config import StructureConfig
from structure.engine import compute_structure_packet
from structure.io import get_output_path, write_packet_atomic


def generate_eurusd_bars(
    timeframe: str,
    periods: int = 240,
    base_price: float = 1.0850,
) -> pd.DataFrame:
    """Generate synthetic EURUSD OHLCV bars for testing."""
    rng = np.random.RandomState(42)

    freq_map = {"15m": "15min", "1h": "1h", "4h": "4h"}
    freq = freq_map[timeframe]

    # Start on a Monday at 21:00 UTC
    start = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)
    idx = pd.date_range(start=start, periods=periods, freq=freq, tz="UTC")

    volatility = 0.0005
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


class TestGroupF1_EURUSD:
    """Group F.1 — EURUSD passes full structure suite on 15m, 1h, 4h."""

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_eurusd_structure_packet(self, config, tf):
        """Full structure computation completes without error."""
        bars = generate_eurusd_bars(tf)
        packet = compute_structure_packet("EURUSD", tf, config, bars=bars)

        assert packet.schema_version == "structure_packet_v1"
        assert packet.instrument == "EURUSD"
        assert packet.timeframe == tf
        assert len(packet.swings) > 0, f"No swings detected for EURUSD {tf}"

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_eurusd_timeframe_consistency(self, config, tf):
        """G.1 — Each timeframe packet has correct timeframe field."""
        bars = generate_eurusd_bars(tf)
        packet = compute_structure_packet("EURUSD", tf, config, bars=bars)

        assert packet.timeframe == tf
        for swing in packet.swings:
            assert swing.timeframe == tf
        for event in packet.events:
            assert event.timeframe == tf

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_eurusd_no_impossible_ordering(self, config, tf):
        """G.2 — No impossible event ordering within a packet."""
        bars = generate_eurusd_bars(tf)
        packet = compute_structure_packet("EURUSD", tf, config, bars=bars)

        for event in packet.events:
            ref_swing = next(
                (s for s in packet.swings if s.id == event.reference_swing_id), None,
            )
            if ref_swing:
                assert event.time >= ref_swing.confirm_time, \
                    f"Event {event.id} fires before reference swing confirmed"

    def test_eurusd_eqh_tolerance(self, config):
        """F.4 — Engine uses correct EQH/EQL tolerance for EURUSD."""
        bars = generate_eurusd_bars("1h")
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)

        eqh_levels = [l for l in packet.liquidity if l.type == "equal_highs"]
        for level in eqh_levels:
            assert level.tolerance_used == 0.00010


class TestGroupG_Output_EURUSD:
    """Group G — JSON output tests for EURUSD."""

    def test_g3_json_written_to_correct_paths(self, config, tmp_path):
        """G.3 — JSON packets are written to correct paths."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        for tf in ["15m", "1h", "4h"]:
            bars = generate_eurusd_bars(tf)
            packet = compute_structure_packet("EURUSD", tf, config, bars=bars)
            path = get_output_path("EURUSD", tf, output_dir=output_dir)
            write_packet_atomic(packet.to_dict(), path)

            assert os.path.exists(path), f"Missing: {path}"

    def test_g4_json_schema_complete(self, config, tmp_path):
        """G.4 — JSON packets are valid and schema-complete."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        bars = generate_eurusd_bars("1h")
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        path = get_output_path("EURUSD", "1h", output_dir=output_dir)
        write_packet_atomic(packet.to_dict(), path)

        with open(path) as f:
            data = json.load(f)

        assert data["schema_version"] == "structure_packet_v1"
        assert data["instrument"] == "EURUSD"
        assert data["timeframe"] == "1h"
        assert "swings" in data
        assert "events" in data
        assert "liquidity" in data
        assert "regime" in data
        assert "diagnostics" in data
        assert "build" in data
        assert data["build"]["engine_version"] == "phase_3a"
        assert data["build"]["bos_confirmation"] == "close"
