"""Tests for Market Packet v2 — Groups B through G acceptance criteria."""

import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from market_data_officer.officer.contracts import (
    ActiveFVGZone,
    LiquidityNearest,
    LiquidityTimeframeSummary,
    MarketPacketV2,
    StructureBlock,
    StructureRecentEvent,
    StructureRegime,
)
from market_data_officer.officer.service import (
    assemble_structure_block,
    build_market_packet,
    write_packet,
)


def _make_structure_packet(instrument, timeframe, as_of=None, num_events=3,
                           base_price=1.0850, include_fvg=True,
                           fvg_statuses=None):
    """Create a valid structure packet dict for testing."""
    if as_of is None:
        as_of = datetime.now(timezone.utc).isoformat()
    if fvg_statuses is None:
        fvg_statuses = ["open", "partially_filled", "invalidated"]

    events = []
    base_time = datetime(2026, 3, 7, 8, 0, 0, tzinfo=timezone.utc)
    for i in range(num_events):
        event_type = "bos_bull" if i % 2 == 0 else "mss_bear"
        t = (base_time - timedelta(hours=i)).isoformat()
        events.append({
            "id": f"ev_{i:03d}",
            "type": event_type,
            "time": t,
            "timeframe": timeframe,
            "reference_swing_id": f"sw_{i:03d}",
            "reference_price": round(base_price + i * 0.001, 5),
            "break_close": round(base_price + i * 0.001 + 0.0005, 5),
            "prior_bias": "bullish",
            "status": "confirmed",
        })

    liquidity = [
        {
            "id": "liq_above",
            "type": "prior_day_high",
            "price": round(base_price + 0.002, 5),
            "origin_time": "2026-03-06T00:00:00+00:00",
            "timeframe": timeframe,
            "status": "active",
            "liquidity_scope": "external_liquidity",
        },
        {
            "id": "liq_below",
            "type": "equal_lows",
            "price": round(base_price - 0.004, 5),
            "origin_time": "2026-03-06T00:00:00+00:00",
            "timeframe": timeframe,
            "status": "active",
            "liquidity_scope": "internal_liquidity",
        },
    ]

    imbalance = []
    if include_fvg:
        for idx, status in enumerate(fvg_statuses):
            imbalance.append({
                "id": f"fvg_{idx:03d}_{timeframe}",
                "fvg_type": "bullish_fvg" if idx % 2 == 0 else "bearish_fvg",
                "zone_high": round(base_price + 0.001 * (idx + 1), 5),
                "zone_low": round(base_price - 0.001 * idx, 5),
                "zone_size": round(0.001 * (idx + 1), 5),
                "origin_time": "2026-03-07T06:00:00+00:00",
                "confirm_time": "2026-03-07T07:00:00+00:00",
                "timeframe": timeframe,
                "status": status,
            })

    return {
        "schema_version": "structure_packet_v1",
        "instrument": instrument,
        "timeframe": timeframe,
        "as_of": as_of,
        "build": {"engine_version": "phase_3c"},
        "swings": [],
        "events": events,
        "liquidity": liquidity,
        "sweep_events": [],
        "imbalance": imbalance,
        "active_zones": {"count": 0, "zones": []},
        "regime": {
            "bias": "bullish",
            "last_bos_direction": "bullish",
            "last_mss_direction": None,
            "trend_state": "trending",
            "structure_quality": "clean",
        },
        "diagnostics": {},
    }


def _make_xauusd_structure_packet(timeframe, as_of=None):
    """Create a XAUUSD structure packet with gold prices."""
    return _make_structure_packet(
        "XAUUSD", timeframe, as_of=as_of,
        base_price=2650.0,
        fvg_statuses=["open", "partially_filled"],
    )


@pytest.fixture
def structure_output_dir(tmp_path):
    """Create structure output with EURUSD and XAUUSD packets."""
    output_dir = tmp_path / "structure_output"
    output_dir.mkdir()

    for tf in ("15m", "1h", "4h"):
        # EURUSD
        packet = _make_structure_packet("EURUSD", tf)
        path = output_dir / f"eurusd_{tf}_structure.json"
        path.write_text(json.dumps(packet, indent=2))

        # XAUUSD
        packet = _make_xauusd_structure_packet(tf)
        path = output_dir / f"xauusd_{tf}_structure.json"
        path.write_text(json.dumps(packet, indent=2))

    return output_dir


@pytest.fixture
def empty_structure_dir(tmp_path):
    """Structure output directory with no packets."""
    d = tmp_path / "empty_structure"
    d.mkdir()
    return d


# --- Group B — StructureBlock assembly ---


class TestGroupB_StructureBlock:
    """Group B — StructureBlock assembly."""

    def test_tb1_unavailable_shape(self):
        """TB.1 — StructureBlock.unavailable() produces correct shape."""
        block = StructureBlock.unavailable()
        assert block.available is False
        assert block.source_engine_version is None
        assert block.regime is None
        assert block.recent_events is None
        assert block.liquidity is None
        assert block.active_fvg_zones is None

    def test_tb2_available_all_fields(self, structure_output_dir):
        """TB.2 — Available StructureBlock has all fields populated."""
        block = assemble_structure_block(
            "EURUSD",
            structure_output_dir=structure_output_dir,
            current_price=1.085,
        )
        assert block.available is True
        assert block.source_engine_version is not None
        assert block.regime is not None
        assert block.recent_events is not None
        assert block.liquidity is not None
        assert block.active_fvg_zones is not None

    def test_tb3_recent_events_capped_at_5(self, structure_output_dir):
        """TB.3 — recent_events capped at 5."""
        block = assemble_structure_block(
            "EURUSD",
            structure_output_dir=structure_output_dir,
            current_price=1.085,
        )
        assert len(block.recent_events) <= 5

    def test_tb4_recent_events_sorted_desc(self, structure_output_dir):
        """TB.4 — recent_events sorted by time descending."""
        block = assemble_structure_block(
            "EURUSD",
            structure_output_dir=structure_output_dir,
            current_price=1.085,
        )
        times = [e.time for e in block.recent_events]
        assert times == sorted(times, reverse=True)

    def test_tb5_fvg_only_open_and_partial(self, structure_output_dir):
        """TB.5 — active_fvg_zones contains only open and partially_filled."""
        block = assemble_structure_block(
            "EURUSD",
            structure_output_dir=structure_output_dir,
            current_price=1.085,
        )
        for zone in block.active_fvg_zones:
            assert zone.status in ("open", "partially_filled")

    def test_tb6_regime_prefers_4h(self, structure_output_dir):
        """TB.6 — Regime source timeframe follows 4h > 1h > 15m preference."""
        block = assemble_structure_block(
            "EURUSD",
            structure_output_dir=structure_output_dir,
            current_price=1.085,
        )
        assert block.regime.source_timeframe == "4h"

    def test_tb6_regime_falls_back_to_1h(self, structure_output_dir):
        """TB.6 — When 4h missing, regime uses 1h."""
        # Remove 4h packet
        (structure_output_dir / "eurusd_4h_structure.json").unlink()
        block = assemble_structure_block(
            "EURUSD",
            structure_output_dir=structure_output_dir,
            current_price=1.085,
            available_timeframes=("15m", "1h"),
        )
        assert block.regime.source_timeframe == "1h"

    def test_tb7_liquidity_nearest_prices(self, structure_output_dir):
        """TB.7 — Liquidity nearest_above and nearest_below price orientation."""
        current_price = 1.085
        block = assemble_structure_block(
            "EURUSD",
            structure_output_dir=structure_output_dir,
            current_price=current_price,
        )
        for tf, summary in block.liquidity.items():
            if summary.nearest_above:
                assert summary.nearest_above.price > current_price
            if summary.nearest_below:
                assert summary.nearest_below.price < current_price


# --- Group C — Market Packet v2 schema ---


class TestGroupC_V2Schema:
    """Group C — Market Packet v2 schema."""

    def test_tc1_schema_version(self, hot_packages_dir, structure_output_dir):
        """TC.1 — schema_version is market_packet_v2."""
        packet = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir)
        d = packet.to_dict()
        assert d["schema_version"] == "market_packet_v2"

    def test_tc2_v1_fields_present(self, hot_packages_dir, structure_output_dir):
        """TC.2 — All v1 fields present in v2."""
        packet = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir)
        d = packet.to_dict()
        v1_required_keys = {
            "instrument", "as_of_utc", "source",
            "timeframes", "features", "state_summary", "quality",
        }
        assert v1_required_keys.issubset(d.keys())

    def test_tc3_structure_top_level(self, hot_packages_dir, structure_output_dir):
        """TC.3 — structure is a top-level key."""
        packet = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir)
        d = packet.to_dict()
        assert "structure" in d
        assert "available" in d["structure"]

    def test_tc4_serializes_to_json(self, hot_packages_dir, structure_output_dir):
        """TC.4 — v2 serializes to valid JSON."""
        packet = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir)
        json_str = json.dumps(packet.to_dict())
        assert len(json_str) > 100

    def test_tc5_has_structure_true(self, hot_packages_dir, structure_output_dir):
        """TC.5 — has_structure() returns True when structure is available."""
        packet = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir)
        assert packet.has_structure() is True

    def test_tc6_is_trusted(self, hot_packages_dir, structure_output_dir):
        """TC.6 — is_trusted() still works on v2 packet."""
        packet = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir)
        assert packet.is_trusted() is True


# --- Group D — Graceful degradation ---


class TestGroupD_Degradation:
    """Group D — Graceful degradation."""

    def test_td1_builds_without_structure(self, hot_packages_dir, empty_structure_dir):
        """TD.1 — Packet builds successfully when no structure packets exist."""
        packet = build_market_packet("EURUSD", hot_packages_dir, empty_structure_dir)
        d = packet.to_dict()
        assert d["schema_version"] == "market_packet_v2"
        assert d["structure"]["available"] is False
        assert d["structure"]["regime"] is None
        assert d["structure"]["active_fvg_zones"] is None

    def test_td2_has_structure_false(self, hot_packages_dir, empty_structure_dir):
        """TD.2 — has_structure() returns False when unavailable."""
        packet = build_market_packet("EURUSD", hot_packages_dir, empty_structure_dir)
        assert packet.has_structure() is False

    def test_td3_feed_features_still_populated(self, hot_packages_dir, empty_structure_dir):
        """TD.3 — Feed features and state summary still populated when structure missing."""
        packet = build_market_packet("EURUSD", hot_packages_dir, empty_structure_dir)
        d = packet.to_dict()
        assert d["features"]["core"]["atr_14"] > 0
        assert d["state_summary"]["trend_1h"] in ("bullish", "bearish", "neutral")
        assert d["quality"]["manifest_valid"] is True

    def test_td4_stale_structure_treated_as_unavailable(self, hot_packages_dir, tmp_path):
        """TD.4 — Stale structure packets treated as unavailable."""
        stale_dir = tmp_path / "stale_structure"
        stale_dir.mkdir()
        three_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        for tf in ("15m", "1h", "4h"):
            packet = _make_structure_packet("EURUSD", tf, as_of=three_hours_ago)
            path = stale_dir / f"eurusd_{tf}_structure.json"
            path.write_text(json.dumps(packet, indent=2))

        packet = build_market_packet("EURUSD", hot_packages_dir, stale_dir)
        assert packet.structure.available is False


# --- Group E — Determinism ---


class TestGroupE_Determinism:
    """Group E — Determinism."""

    def test_te1_identical_inputs_identical_output(self, hot_packages_dir, structure_output_dir):
        """TE.1 — Identical inputs produce identical v2 packets (excluding live timestamp)."""
        def packet_comparable(p):
            d = p.to_dict()
            # Remove the live timestamp which changes between calls
            d.pop("as_of_utc", None)
            return hashlib.md5(
                json.dumps(d, sort_keys=True).encode()
            ).hexdigest()

        p1 = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir)
        p2 = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir)
        assert packet_comparable(p1) == packet_comparable(p2)

    def test_te2_fvg_order_deterministic(self, hot_packages_dir, structure_output_dir):
        """TE.2 — active_fvg_zones order is deterministic."""
        zones_a = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir).to_dict()["structure"]["active_fvg_zones"]
        zones_b = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir).to_dict()["structure"]["active_fvg_zones"]
        assert [z["id"] for z in zones_a] == [z["id"] for z in zones_b]


# --- Group F — Cross-instrument coverage ---


class TestGroupF_CrossInstrument:
    """Group F — Cross-instrument coverage."""

    def test_tf1_eurusd_builds(self, hot_packages_dir, structure_output_dir):
        """TF.1 — EURUSD v2 packet builds."""
        packet = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir)
        d = packet.to_dict()
        assert d["schema_version"] == "market_packet_v2"
        assert d["instrument"] == "EURUSD"
        assert d["structure"]["available"] is True

    def test_tf2_xauusd_builds(self, hot_packages_dir, structure_output_dir):
        """TF.2 — XAUUSD v2 packet builds."""
        # Create XAUUSD hot packages
        from tests.conftest import _generate_ohlcv
        tf_configs = {
            "1m": ("1min", 3000),
            "5m": ("5min", 1200),
            "15m": ("15min", 600),
            "1h": ("1h", 240),
            "4h": ("4h", 120),
            "1d": ("1D", 30),
        }
        for tf_label, (freq, count) in tf_configs.items():
            df = _generate_ohlcv(count, freq, base_price=2650.0, volatility=5.0)
            filename = f"XAUUSD_{tf_label}_latest.csv"
            df.to_csv(hot_packages_dir / filename)

        manifest = {
            "instrument": "XAUUSD",
            "as_of_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "schema": "timestamp_utc,open,high,low,close,volume",
            "windows": {tf: {"count": c, "file": f"XAUUSD_{tf}_latest.csv"}
                        for tf, (_, c) in tf_configs.items()},
        }
        (hot_packages_dir / "XAUUSD_hot.json").write_text(json.dumps(manifest, indent=2))

        packet = build_market_packet("XAUUSD", hot_packages_dir, structure_output_dir)
        d = packet.to_dict()
        assert d["schema_version"] == "market_packet_v2"
        assert d["instrument"] == "XAUUSD"

    def test_tf3_xauusd_fvg_price_range(self, structure_output_dir):
        """TF.3 — XAUUSD active FVG prices are in plausible range."""
        block = assemble_structure_block(
            "XAUUSD",
            structure_output_dir=structure_output_dir,
            current_price=2650.0,
        )
        for zone in block.active_fvg_zones:
            assert 1_500.0 < zone.zone_low < 3_500.0
            assert 1_500.0 < zone.zone_high < 3_500.0


# --- Group G — Output and boundaries ---


class TestGroupG_OutputBoundaries:
    """Group G — Output and boundaries."""

    def test_tg1_packet_written(self, hot_packages_dir, structure_output_dir, tmp_path):
        """TG.1 — v2 packet written to correct path."""
        packet = build_market_packet("EURUSD", hot_packages_dir, structure_output_dir)
        output_dir = tmp_path / "state" / "packets"
        output_path = write_packet(packet, output_dir)
        assert output_path.exists()
        assert output_path.name == "EURUSD_market_packet.json"

        with open(output_path) as f:
            saved = json.load(f)
        assert saved["schema_version"] == "market_packet_v2"

    def test_tg5_run_officer_help(self):
        """TG.5 — run_officer.py --help works."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "run_officer.py", "--help"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
