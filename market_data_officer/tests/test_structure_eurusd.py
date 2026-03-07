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
        assert data["build"]["engine_version"] == "phase_3c"
        assert data["build"]["bos_confirmation"] == "close"


# ---------------------------------------------------------------------------
# Phase 3B — EURUSD cross-instrument tests (Groups F, G)
# ---------------------------------------------------------------------------

class TestGroup3B_F1_EURUSD:
    """TF.1 — EURUSD passes all 3B Groups A–E."""

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3b_eurusd_liquidity_scope_populated(self, config, tf):
        """3B F.1 — All EURUSD liquidity levels have liquidity_scope."""
        bars = generate_eurusd_bars(tf)
        packet = compute_structure_packet("EURUSD", tf, config, bars=bars)

        for level in packet.liquidity:
            assert level.liquidity_scope is not None, \
                f"Level {level.id} missing liquidity_scope"

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3b_eurusd_prior_levels_external(self, config, tf):
        """3B F.1 — Prior day/week levels tagged external for EURUSD."""
        bars = generate_eurusd_bars(tf)
        packet = compute_structure_packet("EURUSD", tf, config, bars=bars)

        for level in packet.liquidity:
            if level.type in ("prior_day_high", "prior_day_low",
                              "prior_week_high", "prior_week_low"):
                assert level.liquidity_scope == "external_liquidity"

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3b_eurusd_sweep_outcome_consistency(self, config, tf):
        """3B F.1 — Sweep outcome mirrors level outcome for EURUSD."""
        bars = generate_eurusd_bars(tf)
        packet = compute_structure_packet("EURUSD", tf, config, bars=bars)

        level_map = {l.id: l for l in packet.liquidity}
        for sw in packet.sweep_events:
            linked = level_map.get(sw.linked_liquidity_id)
            if linked:
                assert sw.outcome == linked.outcome
                assert sw.reclaim_time == linked.reclaim_time

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3b_eurusd_classification_valid(self, config, tf):
        """3B F.1 — All swept EURUSD levels have valid outcome."""
        bars = generate_eurusd_bars(tf)
        packet = compute_structure_packet("EURUSD", tf, config, bars=bars)

        for level in packet.liquidity:
            if level.outcome is not None:
                assert level.outcome in ("reclaimed", "accepted_beyond", "unresolved")


class TestGroup3B_G_EURUSD:
    """TG — JSON output 3B schema completeness for EURUSD."""

    def test_3b_tg1_liquidity_fields_complete(self, config, tmp_path):
        """TG.1 — JSON liquidity objects have all 3B required fields."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        bars = generate_eurusd_bars("1h")
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        path = get_output_path("EURUSD", "1h", output_dir=output_dir)
        write_packet_atomic(packet.to_dict(), path)

        with open(path) as f:
            data = json.load(f)

        required_liquidity_fields = {
            "id", "type", "price", "origin_time", "timeframe", "status",
            "swept_time",
            "liquidity_scope", "outcome", "reclaim_time", "reclaim_window_bars",
        }
        for level in data["liquidity"]:
            assert required_liquidity_fields.issubset(level.keys()), \
                f"Level {level['id']} missing fields: {required_liquidity_fields - set(level.keys())}"

    def test_3b_tg1_sweep_fields_complete(self, config, tmp_path):
        """TG.1 — JSON sweep objects have all 3B required fields."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        bars = generate_eurusd_bars("1h")
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        path = get_output_path("EURUSD", "1h", output_dir=output_dir)
        write_packet_atomic(packet.to_dict(), path)

        with open(path) as f:
            data = json.load(f)

        required_sweep_fields = {
            "id", "type", "time", "timeframe", "sweep_price", "linked_liquidity_id",
            "post_sweep_close", "reclaim_time", "outcome", "reclaim_window_bars",
        }
        for sweep in data["sweep_events"]:
            if sweep["type"] in ("sweep_high", "sweep_low"):
                assert required_sweep_fields.issubset(sweep.keys()), \
                    f"Sweep {sweep['id']} missing fields: {required_sweep_fields - set(sweep.keys())}"

    def test_3b_tg4_engine_version(self, config, tmp_path):
        """TG.4 — engine_version is phase_3b in EURUSD output."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        for tf in ["15m", "1h", "4h"]:
            bars = generate_eurusd_bars(tf)
            packet = compute_structure_packet("EURUSD", tf, config, bars=bars)
            path = get_output_path("EURUSD", tf, output_dir=output_dir)
            write_packet_atomic(packet.to_dict(), path)

            with open(path) as f:
                data = json.load(f)
            assert data["build"]["engine_version"] == "phase_3c"
