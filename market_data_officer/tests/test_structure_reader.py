"""Tests for structure/reader.py — Group A acceptance criteria."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from market_data_officer.structure.reader import (
    load_structure_packet,
    load_structure_summary,
    structure_is_available,
    _is_fresh,
)


def _make_structure_packet(instrument, timeframe, as_of=None):
    """Create a minimal valid structure packet dict."""
    if as_of is None:
        as_of = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "structure_packet_v1",
        "instrument": instrument,
        "timeframe": timeframe,
        "as_of": as_of,
        "build": {"engine_version": "phase_3c", "source": f"hot_package_{timeframe}_csv"},
        "swings": [],
        "events": [
            {
                "id": "ev_001",
                "type": "bos_bull",
                "time": "2026-03-07T08:00:00+00:00",
                "timeframe": timeframe,
                "reference_swing_id": "sw_001",
                "reference_price": 1.08642,
                "break_close": 1.08700,
                "prior_bias": "bullish",
                "status": "confirmed",
            }
        ],
        "liquidity": [
            {
                "id": "liq_001",
                "type": "prior_day_high",
                "price": 1.08720,
                "origin_time": "2026-03-06T00:00:00+00:00",
                "timeframe": timeframe,
                "status": "active",
                "liquidity_scope": "external_liquidity",
            },
            {
                "id": "liq_002",
                "type": "equal_lows",
                "price": 1.08410,
                "origin_time": "2026-03-06T00:00:00+00:00",
                "timeframe": timeframe,
                "status": "active",
                "liquidity_scope": "internal_liquidity",
            },
        ],
        "sweep_events": [],
        "imbalance": [
            {
                "id": "fvg_001",
                "fvg_type": "bullish_fvg",
                "zone_high": 1.08620,
                "zone_low": 1.08475,
                "zone_size": 0.00145,
                "origin_time": "2026-03-07T06:00:00+00:00",
                "confirm_time": "2026-03-07T07:00:00+00:00",
                "timeframe": timeframe,
                "status": "open",
            }
        ],
        "active_zones": {"count": 1, "zones": []},
        "regime": {
            "bias": "bullish",
            "last_bos_direction": "bullish",
            "last_mss_direction": None,
            "trend_state": "trending",
            "structure_quality": "clean",
        },
        "diagnostics": {"bars_processed": 240, "swings_confirmed": 10},
    }


@pytest.fixture
def structure_output_dir(tmp_path):
    """Create a temporary structure output directory with EURUSD packets."""
    output_dir = tmp_path / "structure_output"
    output_dir.mkdir()

    for tf in ("15m", "1h", "4h"):
        packet = _make_structure_packet("EURUSD", tf)
        path = output_dir / f"eurusd_{tf}_structure.json"
        path.write_text(json.dumps(packet, indent=2))

    return output_dir


class TestGroupA_Reader:
    """Group A — Structure reader API."""

    def test_ta1_load_returns_dict(self, structure_output_dir):
        """TA.1 — load_structure_packet returns dict for existing packet."""
        packet = load_structure_packet("EURUSD", "1h", output_dir=structure_output_dir)
        assert packet is not None
        assert isinstance(packet, dict)
        assert "instrument" in packet
        assert "regime" in packet

    def test_ta2_missing_instrument_returns_none(self, structure_output_dir):
        """TA.2 — load_structure_packet returns None for missing instrument."""
        result = load_structure_packet("FAKEINSTRUMENT", "1h", output_dir=structure_output_dir)
        assert result is None

    def test_ta3_missing_timeframe_returns_none(self, structure_output_dir):
        """TA.3 — load_structure_packet returns None for missing timeframe."""
        result = load_structure_packet("EURUSD", "1d", output_dir=structure_output_dir)
        assert result is None

    def test_ta4_corrupt_json_returns_none(self, structure_output_dir):
        """TA.4 — load_structure_packet returns None for corrupt JSON."""
        corrupt_path = structure_output_dir / "eurusd_1h_structure.json"
        corrupt_path.write_text("{invalid json content!!! not valid")
        result = load_structure_packet("EURUSD", "1h", output_dir=structure_output_dir)
        assert result is None

    def test_ta5_available_returns_true(self, structure_output_dir):
        """TA.5 — structure_is_available returns True when fresh packets exist."""
        assert structure_is_available("EURUSD", output_dir=structure_output_dir) is True

    def test_ta6_unavailable_returns_false(self, structure_output_dir):
        """TA.6 — structure_is_available returns False when no packets exist."""
        assert structure_is_available("FAKEINSTRUMENT", output_dir=structure_output_dir) is False

    def test_ta7_reader_does_not_import_engine(self):
        """TA.7 — Reader does not import structure engine modules."""
        import inspect
        from market_data_officer.structure import reader
        source = inspect.getsource(reader)
        assert "from structure.engine" not in source
        assert "import engine" not in source
        assert "run_engine" not in source

    def test_load_structure_summary(self, structure_output_dir):
        """load_structure_summary returns dict keyed by timeframe."""
        summary = load_structure_summary("EURUSD", output_dir=structure_output_dir)
        assert isinstance(summary, dict)
        assert "1h" in summary
        assert "4h" in summary
        assert "15m" in summary

    def test_stale_packet_treated_as_unavailable(self, structure_output_dir):
        """Stale packets cause structure_is_available to return False."""
        # Overwrite all packets with stale as_of
        three_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        for tf in ("15m", "1h", "4h"):
            packet = _make_structure_packet("EURUSD", tf, as_of=three_hours_ago)
            path = structure_output_dir / f"eurusd_{tf}_structure.json"
            path.write_text(json.dumps(packet, indent=2))

        assert structure_is_available("EURUSD", output_dir=structure_output_dir) is False

    def test_is_fresh_valid_packet(self):
        """_is_fresh returns True for recent packet."""
        packet = {"as_of": datetime.now(timezone.utc).isoformat()}
        assert _is_fresh(packet) is True

    def test_is_fresh_stale_packet(self):
        """_is_fresh returns False for old packet."""
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        packet = {"as_of": old}
        assert _is_fresh(packet) is False

    def test_is_fresh_missing_as_of(self):
        """_is_fresh returns False when as_of is missing."""
        assert _is_fresh({}) is False
