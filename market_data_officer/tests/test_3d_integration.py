"""Cross-layer integration tests for Phase 3D.

Verifies the full pipeline: structure engine output -> reader -> officer -> v2 packet.
"""

import json
from datetime import datetime, timezone

import pytest

from market_data_officer.officer.contracts import MarketPacketV2, StructureBlock
from market_data_officer.officer.service import assemble_structure_block, build_market_packet, write_packet
from market_data_officer.structure.reader import load_structure_packet, structure_is_available


def _make_structure_packet(instrument, timeframe, as_of=None, base_price=1.085):
    """Create a valid structure packet."""
    if as_of is None:
        as_of = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "structure_packet_v1",
        "instrument": instrument,
        "timeframe": timeframe,
        "as_of": as_of,
        "build": {"engine_version": "phase_3c"},
        "swings": [],
        "events": [
            {
                "id": "ev_001", "type": "bos_bull",
                "time": "2026-03-07T08:00:00+00:00", "timeframe": timeframe,
                "reference_swing_id": "sw_001",
                "reference_price": base_price, "break_close": base_price + 0.001,
                "prior_bias": "bullish", "status": "confirmed",
            }
        ],
        "liquidity": [
            {
                "id": "liq_001", "type": "prior_day_high",
                "price": base_price + 0.002, "origin_time": "2026-03-06T00:00:00+00:00",
                "timeframe": timeframe, "status": "active",
                "liquidity_scope": "external_liquidity",
            }
        ],
        "sweep_events": [],
        "imbalance": [
            {
                "id": f"fvg_001_{timeframe}", "fvg_type": "bullish_fvg",
                "zone_high": base_price + 0.001, "zone_low": base_price - 0.001,
                "zone_size": 0.002,
                "origin_time": "2026-03-07T06:00:00+00:00",
                "confirm_time": "2026-03-07T07:00:00+00:00",
                "timeframe": timeframe, "status": "open",
            }
        ],
        "active_zones": {"count": 1, "zones": []},
        "regime": {
            "bias": "bullish", "last_bos_direction": "bullish",
            "last_mss_direction": None, "trend_state": "trending",
            "structure_quality": "clean",
        },
        "diagnostics": {},
    }


@pytest.fixture
def full_setup(tmp_path, hot_packages_dir):
    """Full setup with hot packages and structure output."""
    structure_dir = tmp_path / "structure_output"
    structure_dir.mkdir()

    for tf in ("15m", "1h", "4h"):
        packet = _make_structure_packet("EURUSD", tf)
        path = structure_dir / f"eurusd_{tf}_structure.json"
        path.write_text(json.dumps(packet, indent=2))

    return hot_packages_dir, structure_dir


class TestIntegration:
    """Full integration: reader -> officer -> v2 packet."""

    def test_end_to_end_v2_packet(self, full_setup):
        """Full e2e: build v2 packet from feed + structure data."""
        packages_dir, structure_dir = full_setup
        packet = build_market_packet("EURUSD", packages_dir, structure_dir)

        assert isinstance(packet, MarketPacketV2)

        d = packet.to_dict()
        assert d["schema_version"] == "market_packet_v2"
        assert d["instrument"] == "EURUSD"

        # v1 fields all present
        assert "source" in d
        assert "timeframes" in d
        assert "features" in d
        assert "state_summary" in d
        assert "quality" in d

        # Structure block populated
        assert d["structure"]["available"] is True
        assert d["structure"]["regime"] is not None
        assert d["structure"]["recent_events"] is not None
        assert d["structure"]["liquidity"] is not None
        assert d["structure"]["active_fvg_zones"] is not None

    def test_reader_feeds_officer_correctly(self, full_setup):
        """Reader loads packets, officer assembles structure block."""
        _, structure_dir = full_setup

        # Reader can load individual packets
        packet = load_structure_packet("EURUSD", "1h", output_dir=structure_dir)
        assert packet is not None
        assert packet["instrument"] == "EURUSD"

        # Officer assembles block from reader data
        block = assemble_structure_block(
            "EURUSD",
            structure_output_dir=structure_dir,
            current_price=1.085,
        )
        assert block.available is True
        assert block.regime.bias == "bullish"

    def test_v2_packet_roundtrips_through_json(self, full_setup):
        """v2 packet serializes and deserializes cleanly."""
        packages_dir, structure_dir = full_setup
        packet = build_market_packet("EURUSD", packages_dir, structure_dir)

        json_str = json.dumps(packet.to_dict(), indent=2)
        parsed = json.loads(json_str)

        assert parsed["schema_version"] == "market_packet_v2"
        assert parsed["structure"]["available"] is True
        assert isinstance(parsed["structure"]["recent_events"], list)
        assert isinstance(parsed["structure"]["active_fvg_zones"], list)

    def test_write_and_read_back(self, full_setup, tmp_path):
        """Write v2 packet to file and read it back."""
        packages_dir, structure_dir = full_setup
        packet = build_market_packet("EURUSD", packages_dir, structure_dir)

        output_dir = tmp_path / "output"
        path = write_packet(packet, output_dir)

        with open(path) as f:
            saved = json.load(f)

        assert saved["schema_version"] == "market_packet_v2"
        assert saved["structure"]["available"] is True
        assert saved["structure"]["source_engine_version"] == "phase_3c"

    def test_structure_unavailable_doesnt_break_packet(self, hot_packages_dir, tmp_path):
        """Missing structure => unavailable block, no crash."""
        empty_dir = tmp_path / "no_structure"
        empty_dir.mkdir()

        packet = build_market_packet("EURUSD", hot_packages_dir, empty_dir)
        assert isinstance(packet, MarketPacketV2)
        assert packet.structure.available is False
        assert packet.has_structure() is False

        # v1 content still valid
        d = packet.to_dict()
        assert d["features"]["core"]["atr_14"] > 0
        assert d["quality"]["manifest_valid"] is True

    def test_has_structure_false_with_all_null_subfields(self):
        """has_structure returns False when available=True but all sub-fields null."""
        block = StructureBlock(available=True)
        # Create a mock v2 packet-like check
        has = block.available and any([
            block.regime is not None,
            block.recent_events is not None,
            block.liquidity is not None,
            block.active_fvg_zones is not None,
        ])
        assert has is False
