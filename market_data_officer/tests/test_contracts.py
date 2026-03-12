"""Tests for officer.contracts and full packet assembly — Groups 4 & 6 acceptance criteria."""

import inspect
import json
from datetime import datetime, timezone

import pytest

from market_data_officer.officer.contracts import (
    CoreFeatures,
    FeatureBlock,
    MarketPacket,
    QualityBlock,
    StateSummary,
)
from market_data_officer.officer.loader import load_timeframe
from market_data_officer.officer.service import build_market_packet, write_packet
from market_data_officer.officer.structure.bos_detector import detect_bos
from market_data_officer.officer.structure.fvg_detector import detect_fvg
from market_data_officer.officer.structure.compression_detector import detect_compression
from market_data_officer.officer.structure.imbalance_detector import detect_imbalance


class TestStubModules:
    """Group 4 — Advanced feature stubs."""

    def test_stubs_return_none(self, hot_packages_dir):
        """T4.2 — All stubs return None without raising."""
        df_1h = load_timeframe("EURUSD", "1h", hot_packages_dir)
        assert detect_bos(df_1h) is None
        assert detect_fvg(df_1h) is None
        assert detect_compression(df_1h) is None
        assert detect_imbalance(df_1h) is None

    def test_stubs_have_docstrings(self):
        """T4.3 — All stubs have docstrings explaining Phase 3/4 intent."""
        assert detect_bos.__doc__ is not None
        assert len(detect_bos.__doc__) > 20

        assert detect_fvg.__doc__ is not None
        assert len(detect_fvg.__doc__) > 20

        assert detect_compression.__doc__ is not None
        assert len(detect_compression.__doc__) > 20

        assert detect_imbalance.__doc__ is not None
        assert len(detect_imbalance.__doc__) > 20


class TestStubFilesExist:
    """T4.1 — All stub modules exist as importable files."""

    def test_stub_files_importable(self):
        from market_data_officer.officer.structure import bos_detector
        from market_data_officer.officer.structure import fvg_detector
        from market_data_officer.officer.structure import compression_detector
        from market_data_officer.officer.structure import imbalance_detector

        assert hasattr(bos_detector, "detect_bos")
        assert hasattr(fvg_detector, "detect_fvg")
        assert hasattr(compression_detector, "detect_compression")
        assert hasattr(imbalance_detector, "detect_imbalance")


class TestMarketPacketAssembly:
    """Group 6 — Market Packet assembly."""

    def test_full_packet_builds(self, hot_packages_dir):
        """T6.1 — Full packet builds without exception."""
        packet = build_market_packet("EURUSD", hot_packages_dir)
        assert packet is not None

    def test_packet_serialises_to_valid_json(self, hot_packages_dir):
        """T6.2 — Packet serialises to valid JSON matching v1 schema."""
        packet = build_market_packet("EURUSD", hot_packages_dir)
        d = packet.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        # Top-level keys
        assert set(parsed.keys()) >= {
            "instrument", "as_of_utc", "source", "timeframes",
            "features", "state_summary", "quality",
        }

        # All four feature keys present
        assert set(parsed["features"].keys()) == {
            "core", "structure", "imbalance", "compression",
        }

        # Advanced features are null
        assert parsed["features"]["structure"] is None
        assert parsed["features"]["imbalance"] is None
        assert parsed["features"]["compression"] is None

        # Core features populated
        assert parsed["features"]["core"]["atr_14"] > 0

    def test_all_timeframes_present(self, hot_packages_dir):
        """T6.3 — All six timeframes present in packet."""
        packet = build_market_packet("EURUSD", hot_packages_dir)
        d = packet.to_dict()
        for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
            assert tf in d["timeframes"], f"Missing timeframe: {tf}"
            assert d["timeframes"][tf]["count"] > 0

    def test_timestamps_utc_iso8601(self, hot_packages_dir):
        """T6.4 — Timestamps in packet are UTC ISO8601 strings."""
        packet = build_market_packet("EURUSD", hot_packages_dir)
        as_of = datetime.fromisoformat(packet.as_of_utc.replace("Z", "+00:00"))
        assert as_of.tzinfo is not None

    def test_is_trusted_for_clean_packet(self, hot_packages_dir):
        """T6.5 — is_trusted() returns True for clean EURUSD packet."""
        packet = build_market_packet("EURUSD", hot_packages_dir)
        assert packet.is_trusted() is True

    def test_packet_written_to_output(self, hot_packages_dir, tmp_path):
        """T6.6 — Packet written to correct output path."""
        packet = build_market_packet("EURUSD", hot_packages_dir)
        output_dir = tmp_path / "state" / "packets"
        output_path = write_packet(packet, output_dir)
        assert output_path.exists()
        assert output_path.name == "EURUSD_market_packet.json"

        # Verify the written file is valid JSON
        parsed = json.loads(output_path.read_text())
        assert parsed["instrument"] == "EURUSD"


class TestUnverifiedInstrument:
    """T2.4 — Unverified instrument returns unverified quality, not crash."""

    def test_unknown_instrument_unverified(self, hot_packages_dir):
        """Unknown instrument (not in TRUSTED or PROVISIONAL) returns unverified."""
        packet = build_market_packet("NZDUSD", hot_packages_dir)
        assert packet.quality.flags  # must have at least one flag
        assert packet.state_summary.data_quality in ("unverified", "partial")
