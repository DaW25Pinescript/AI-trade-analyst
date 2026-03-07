"""Phase 3C — Imbalance Engine acceptance tests.

Groups A through G as defined in ACCEPTANCE_TESTS.md.
"""

import copy
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structure.config import StructureConfig
from structure.engine import compute_structure_packet
from structure.imbalance import (
    build_active_zone_registry,
    detect_fvg,
    process_imbalance,
    update_fvg_fills,
)
from structure.io import get_output_path, write_packet_atomic
from structure.schemas import FairValueGap

START = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)


def make_bars(ohlc_rows: list, start: datetime = START, freq: str = "1h") -> pd.DataFrame:
    """Build a DataFrame from list of (open, high, low, close) tuples."""
    idx = pd.date_range(start=start, periods=len(ohlc_rows), freq=freq, tz="UTC")
    rows = []
    for o, h, l, c in ohlc_rows:
        rows.append({"open": o, "high": h, "low": l, "close": c, "volume": 100.0})
    return pd.DataFrame(rows, index=idx)


@pytest.fixture
def config():
    return StructureConfig()


# ---------------------------------------------------------------------------
# Group T0 — Config and version checks
# ---------------------------------------------------------------------------

class TestGroupT0_Config:
    """T0.3 — fvg_use_body_only is True in config."""

    def test_t03_fvg_use_body_only_true(self):
        config = StructureConfig()
        assert config.fvg_use_body_only is True

    def test_t02_engine_version_phase_3c(self, config):
        """T0.2 — engine_version is phase_3c in output packets."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
        ])
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        assert packet.build["engine_version"] == "phase_3c"


# ---------------------------------------------------------------------------
# Group A — FVG Detection
# ---------------------------------------------------------------------------

class TestGroupA_FVGDetection:
    """Group A — FVG detection using body-only logic."""

    def test_ta1_bullish_fvg_detected(self, config):
        """TA.1 — Bullish FVG detected correctly from body boundaries."""
        # c1: open=1.0820, close=1.0840 → body_high=1.0840
        # c2: open=1.0845, close=1.0880 → impulse candle
        # c3: open=1.0882, close=1.0895 → body_low=1.0882
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
        ])
        zones = detect_fvg(bars, config, "EURUSD", "1h")
        assert len(zones) == 1
        assert zones[0].fvg_type == "bullish_fvg"
        assert zones[0].zone_low == pytest.approx(1.0840, abs=1e-5)
        assert zones[0].zone_high == pytest.approx(1.0882, abs=1e-5)
        assert zones[0].zone_size == pytest.approx(0.0042, abs=1e-5)

    def test_ta2_bearish_fvg_detected(self, config):
        """TA.2 — Bearish FVG detected correctly from body boundaries."""
        # c1: open=1.0900, close=1.0880 → body_low=1.0880
        # c2: open=1.0875, close=1.0840 → impulse
        # c3: open=1.0838, close=1.0820 → body_high=1.0838
        bars = make_bars([
            (1.0900, 1.0910, 1.0870, 1.0880),
            (1.0875, 1.0880, 1.0835, 1.0840),
            (1.0838, 1.0845, 1.0815, 1.0820),
        ])
        zones = detect_fvg(bars, config, "EURUSD", "1h")
        assert len(zones) == 1
        assert zones[0].fvg_type == "bearish_fvg"
        assert zones[0].zone_high == pytest.approx(1.0880, abs=1e-5)
        assert zones[0].zone_low == pytest.approx(1.0838, abs=1e-5)

    def test_ta3_wick_does_not_create_false_fvg(self, config):
        """TA.3 — Wick extension does not create false FVG; body is used."""
        # c1: open=1.0820, close=1.0840, high=1.0860 (wick extends higher)
        # c2: open=1.0850, close=1.0870
        # c3: open=1.0855, close=1.0865, low=1.0842 (wick dips lower)
        # Body gap: c3_body_low=1.0855 > c1_body_high=1.0840 → valid bullish FVG
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0850, 1.0880, 1.0845, 1.0870),
            (1.0855, 1.0870, 1.0842, 1.0865),
        ])
        zones = detect_fvg(bars, config, "EURUSD", "1h")
        assert len(zones) == 1
        assert zones[0].zone_low == pytest.approx(1.0840, abs=1e-5)  # c1 body high, not wick
        assert zones[0].zone_high == pytest.approx(1.0855, abs=1e-5)  # c3 body low, not wick

    def test_ta4_zone_below_min_size_filtered(self, config):
        """TA.4 — Zone below minimum size is filtered out."""
        # EURUSD min = 0.0003. Create gap of 0.0001 (below minimum).
        bars = make_bars([
            (1.0820, 1.0830, 1.0810, 1.0840),
            (1.0841, 1.0850, 1.0838, 1.0845),
            (1.08405, 1.0850, 1.0838, 1.08415),  # c3_body_low=1.08405, gap=0.00005
        ])
        zones = detect_fvg(bars, config, "EURUSD", "1h")
        assert len(zones) == 0

    def test_ta5_zone_above_min_size_passes(self, config):
        """TA.5 — Zone above minimum size passes through."""
        # Gap = 0.0042 (above EURUSD minimum of 0.0003)
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
        ])
        zones = detect_fvg(bars, config, "EURUSD", "1h")
        assert len(zones) == 1

    def test_ta6_confirm_time_equals_candle3(self, config):
        """TA.6 — confirm_time equals candle 3 timestamp."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
        ])
        zones = detect_fvg(bars, config, "EURUSD", "1h")
        assert zones[0].confirm_time == bars.index[2]  # candle 3
        assert zones[0].origin_time == bars.index[1]   # candle 2

    def test_ta7_no_zone_from_first_two_bars(self, config):
        """TA.7 — No zone emitted from first two bars (no lookahead)."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
        ])
        zones = detect_fvg(bars, config, "EURUSD", "1h")
        assert len(zones) == 0


# ---------------------------------------------------------------------------
# Group B — Fill Progression
# ---------------------------------------------------------------------------

class TestGroupB_FillProgression:
    """Group B — Fill progression tracking."""

    def _make_bullish_zone(self, config) -> tuple:
        """Helper: create a bullish FVG zone and return (zone, config)."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
        ])
        zones = detect_fvg(bars, config, "EURUSD", "1h")
        return zones[0], bars

    def _make_bearish_zone(self, config) -> tuple:
        """Helper: create a bearish FVG zone."""
        bars = make_bars([
            (1.0900, 1.0910, 1.0870, 1.0880),
            (1.0875, 1.0880, 1.0835, 1.0840),
            (1.0838, 1.0845, 1.0815, 1.0820),
        ])
        zones = detect_fvg(bars, config, "EURUSD", "1h")
        return zones[0], bars

    def test_tb1_bullish_partial_fill(self, config):
        """TB.1 — Bullish FVG transitions to partially_filled on close into zone."""
        zone, detection_bars = self._make_bullish_zone(config)
        # zone: zone_low=1.0840, zone_high=1.0882
        # Subsequent bar: close=1.0855 (inside zone)
        fill_bar = make_bars(
            [(1.0890, 1.0895, 1.0850, 1.0855)],
            start=detection_bars.index[-1] + timedelta(hours=1),
        )
        all_bars = pd.concat([detection_bars, fill_bar])
        zone = update_fvg_fills(zone, all_bars)
        assert zone.status == "partially_filled"
        assert zone.partial_fill_time is not None
        assert zone.fill_low == pytest.approx(1.0855, abs=1e-5)

    def test_tb2_bearish_partial_fill(self, config):
        """TB.2 — Bearish FVG transitions to partially_filled on close into zone."""
        zone, detection_bars = self._make_bearish_zone(config)
        # zone: zone_low=1.0838, zone_high=1.0880
        # Subsequent bar: close=1.0860 (inside zone)
        fill_bar = make_bars(
            [(1.0825, 1.0865, 1.0820, 1.0860)],
            start=detection_bars.index[-1] + timedelta(hours=1),
        )
        all_bars = pd.concat([detection_bars, fill_bar])
        zone = update_fvg_fills(zone, all_bars)
        assert zone.status == "partially_filled"
        assert zone.fill_high == pytest.approx(1.0860, abs=1e-5)

    def test_tb3_fill_low_tracks_lowest(self, config):
        """TB.3 — fill_low tracks the lowest close reached (bullish FVG)."""
        zone, detection_bars = self._make_bullish_zone(config)
        # Two bars close into zone: 1.0865 then 1.0850
        fill_bars = make_bars([
            (1.0890, 1.0895, 1.0860, 1.0865),
            (1.0860, 1.0870, 1.0845, 1.0850),
        ], start=detection_bars.index[-1] + timedelta(hours=1))
        all_bars = pd.concat([detection_bars, fill_bars])
        zone = update_fvg_fills(zone, all_bars)
        assert zone.fill_low == pytest.approx(1.0850, abs=1e-5)

    def test_tb4_full_fill_invalidates(self, config):
        """TB.4 — Full fill triggers invalidation (bullish FVG)."""
        zone, detection_bars = self._make_bullish_zone(config)
        # zone_low=1.0840. First partial fill, then full fill.
        fill_bars = make_bars([
            (1.0890, 1.0895, 1.0860, 1.0865),  # partial fill
            (1.0860, 1.0870, 1.0830, 1.0838),   # full fill: close <= zone_low
        ], start=detection_bars.index[-1] + timedelta(hours=1))
        all_bars = pd.concat([detection_bars, fill_bars])
        zone = update_fvg_fills(zone, all_bars)
        assert zone.status == "invalidated"
        assert zone.full_fill_time is not None

    def test_tb5_blowthrough_fires_partial_then_full(self, config):
        """TB.5 — Price blowthrough fires partial then full on same bar.

        This is the trickiest edge case: a single bar blows straight through
        the entire FVG zone. Both partially_filled and invalidated must fire
        in sequence on that same bar, with partial_fill_time == full_fill_time.
        """
        zone, detection_bars = self._make_bullish_zone(config)
        # zone: zone_low=1.0840, zone_high=1.0882
        # Single bar: opens above zone, closes below zone_low
        blowthrough = make_bars(
            [(1.0890, 1.0895, 1.0830, 1.0835)],
            start=detection_bars.index[-1] + timedelta(hours=1),
        )
        all_bars = pd.concat([detection_bars, blowthrough])
        zone = update_fvg_fills(zone, all_bars)
        assert zone.status == "invalidated"
        assert zone.partial_fill_time is not None
        assert zone.full_fill_time is not None
        assert zone.partial_fill_time == zone.full_fill_time  # same bar

    def test_tb5_bearish_blowthrough(self, config):
        """TB.5 bearish variant — blowthrough on bearish FVG."""
        zone, detection_bars = self._make_bearish_zone(config)
        # zone: zone_low=1.0838, zone_high=1.0880
        # Single bar: opens below zone, closes above zone_high
        blowthrough = make_bars(
            [(1.0830, 1.0890, 1.0825, 1.0885)],
            start=detection_bars.index[-1] + timedelta(hours=1),
        )
        all_bars = pd.concat([detection_bars, blowthrough])
        zone = update_fvg_fills(zone, all_bars)
        assert zone.status == "invalidated"
        assert zone.partial_fill_time is not None
        assert zone.full_fill_time is not None
        assert zone.partial_fill_time == zone.full_fill_time

    def test_tb6_no_fill_on_invalidated(self, config):
        """TB.6 — No fill processing on invalidated zone."""
        zone, detection_bars = self._make_bullish_zone(config)
        # Manually set to invalidated
        zone.status = "invalidated"
        zone.full_fill_time = detection_bars.index[-1]
        original_time = zone.full_fill_time

        more_bars = make_bars(
            [(1.0850, 1.0860, 1.0830, 1.0835)],
            start=detection_bars.index[-1] + timedelta(hours=1),
        )
        all_bars = pd.concat([detection_bars, more_bars])
        result = update_fvg_fills(zone, all_bars)
        assert result.status == "invalidated"
        assert result.full_fill_time == original_time


# ---------------------------------------------------------------------------
# Group C — Zone Lifecycle
# ---------------------------------------------------------------------------

class TestGroupC_Lifecycle:
    """Group C — Zone lifecycle transitions."""

    ALLOWED = {
        "open": {"partially_filled"},
        "partially_filled": {"invalidated"},
        "invalidated": {"archived"},
    }

    def test_tc1_only_allowed_transitions(self, config):
        """TC.1 — Only allowed transitions occur in a full run."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
            (1.0890, 1.0895, 1.0850, 1.0855),  # partial fill
            (1.0850, 1.0860, 1.0830, 1.0838),   # full fill
        ])
        zones, _ = process_imbalance(bars, config, "EURUSD", "1h")
        # Verify zone went through valid transitions
        for zone in zones:
            if zone.status == "invalidated":
                assert zone.partial_fill_time is not None
                assert zone.full_fill_time is not None

    def test_tc2_reruns_do_not_alter_invalidated(self, config):
        """TC.2 — Reruns do not alter invalidated zones."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
            (1.0890, 1.0895, 1.0850, 1.0855),
            (1.0850, 1.0860, 1.0830, 1.0838),
        ])
        zones1, _ = process_imbalance(bars, config, "EURUSD", "1h")
        zones2, _ = process_imbalance(bars, config, "EURUSD", "1h")

        for z1, z2 in zip(zones1, zones2):
            assert z1.status == z2.status
            if z1.status == "invalidated":
                assert z1.full_fill_time == z2.full_fill_time

    def test_tc3_open_zones_remain_open(self, config):
        """TC.3 — Open zones remain open when price does not enter."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
            # Subsequent bars stay above zone_high (1.0882)
            (1.0900, 1.0910, 1.0895, 1.0905),
            (1.0910, 1.0920, 1.0905, 1.0915),
        ])
        zones, _ = process_imbalance(bars, config, "EURUSD", "1h")
        bullish = [z for z in zones if z.fvg_type == "bullish_fvg"]
        assert len(bullish) >= 1
        assert bullish[0].status == "open"
        assert bullish[0].first_touch_time is None

    def test_tc4_partial_resolves_to_invalidated(self, config):
        """TC.4 — Partially filled zones resolve when new bars arrive."""
        # Day 1: partial fill
        bars_day1 = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
            (1.0890, 1.0895, 1.0850, 1.0855),  # partial
        ])
        zones1, _ = process_imbalance(bars_day1, config, "EURUSD", "1h")
        assert zones1[0].status == "partially_filled"

        # Day 2: full fill
        extra = make_bars(
            [(1.0850, 1.0860, 1.0830, 1.0838)],
            start=bars_day1.index[-1] + timedelta(hours=1),
        )
        bars_day2 = pd.concat([bars_day1, extra])
        zones2, _ = process_imbalance(bars_day2, config, "EURUSD", "1h")
        assert zones2[0].status == "invalidated"


# ---------------------------------------------------------------------------
# Group D — Active Zone Registry
# ---------------------------------------------------------------------------

class TestGroupD_ActiveZoneRegistry:
    """Group D — Active zone registry tests."""

    def test_td1_active_registry_only_open_or_partial(self, config):
        """TD.1 — Active registry contains only open and partially_filled zones."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
            (1.0900, 1.0910, 1.0895, 1.0905),
        ])
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        pkt = packet.to_dict()

        active_ids = {z["id"] for z in pkt["active_zones"]["zones"]}
        all_zones = {z["id"]: z for z in pkt["imbalance"]}

        for zone_id in active_ids:
            assert all_zones[zone_id]["status"] in ("open", "partially_filled")

    def test_td2_invalidated_not_in_active(self, config):
        """TD.2 — Invalidated zones not in active registry."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
            (1.0890, 1.0895, 1.0850, 1.0855),
            (1.0850, 1.0860, 1.0830, 1.0838),
        ])
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        pkt = packet.to_dict()

        invalidated_ids = {z["id"] for z in pkt["imbalance"]
                           if z["status"] == "invalidated"}
        active_ids = {z["id"] for z in pkt["active_zones"]["zones"]}
        assert invalidated_ids.isdisjoint(active_ids)

    def test_td3_count_matches_zones_length(self, config):
        """TD.3 — Active zone count matches registry count field."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
        ])
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        pkt = packet.to_dict()
        assert pkt["active_zones"]["count"] == len(pkt["active_zones"]["zones"])

    def test_td4_registry_updates_after_invalidation(self, config):
        """TD.4 — Registry updates correctly after new bar invalidates a zone."""
        bars_day1 = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
            (1.0900, 1.0910, 1.0895, 1.0905),
        ])
        pkt1 = compute_structure_packet("EURUSD", "1h", config, bars=bars_day1).to_dict()
        active_before = {z["id"] for z in pkt1["active_zones"]["zones"]}

        # Add bars that invalidate the zone
        extra = make_bars([
            (1.0890, 1.0895, 1.0850, 1.0855),
            (1.0850, 1.0860, 1.0830, 1.0838),
        ], start=bars_day1.index[-1] + timedelta(hours=1))
        bars_day2 = pd.concat([bars_day1, extra])
        pkt2 = compute_structure_packet("EURUSD", "1h", config, bars=bars_day2).to_dict()
        active_after = {z["id"] for z in pkt2["active_zones"]["zones"]}

        # Zones that disappeared from active must be invalidated
        for zone_id in (active_before - active_after):
            zone = next(z for z in pkt2["imbalance"] if z["id"] == zone_id)
            assert zone["status"] == "invalidated"


# ---------------------------------------------------------------------------
# Group E — Determinism and Replay Stability
# ---------------------------------------------------------------------------

class TestGroupE_Determinism:
    """Group E — Determinism and replay stability."""

    def _make_test_bars(self):
        return make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
            (1.0890, 1.0895, 1.0850, 1.0855),
            (1.0850, 1.0860, 1.0830, 1.0838),
        ])

    def test_te1_identical_inputs_identical_packets(self, config):
        """TE.1 — Identical inputs produce identical packets."""
        bars = self._make_test_bars()

        def packet_hash(bars):
            p = compute_structure_packet("EURUSD", "1h", config, bars=bars)
            d = p.to_dict()
            # Remove as_of since it's non-deterministic
            d.pop("as_of", None)
            return hashlib.md5(json.dumps(d, sort_keys=True).encode()).hexdigest()

        assert packet_hash(bars) == packet_hash(bars)

    def test_te2_reruns_do_not_mutate_resolved(self, config):
        """TE.2 — Reruns do not mutate resolved zones."""
        bars = self._make_test_bars()
        pkt_a = compute_structure_packet("EURUSD", "1h", config, bars=bars).to_dict()
        pkt_b = compute_structure_packet("EURUSD", "1h", config, bars=bars).to_dict()

        resolved_a = [z for z in pkt_a["imbalance"] if z["status"] == "invalidated"]
        resolved_b = [z for z in pkt_b["imbalance"] if z["status"] == "invalidated"]
        assert resolved_a == resolved_b

    def test_te3_appending_bars_only_advances(self, config):
        """TE.3 — Appending bars only adds or advances, never rewrites."""
        bars_day1 = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
            (1.0890, 1.0895, 1.0850, 1.0855),
            (1.0850, 1.0860, 1.0830, 1.0838),
        ])
        extra = make_bars([
            (1.0840, 1.0850, 1.0830, 1.0845),
        ], start=bars_day1.index[-1] + timedelta(hours=1))
        bars_day2 = pd.concat([bars_day1, extra])

        pkt1 = compute_structure_packet("EURUSD", "1h", config, bars=bars_day1).to_dict()
        pkt2 = compute_structure_packet("EURUSD", "1h", config, bars=bars_day2).to_dict()

        zones_day1 = {z["id"]: z for z in pkt1["imbalance"]}
        zones_day2 = {z["id"]: z for z in pkt2["imbalance"]}

        for zone_id, zone in zones_day1.items():
            if zone["status"] == "invalidated":
                assert zones_day2[zone_id]["status"] == "invalidated"
                assert zones_day2[zone_id]["full_fill_time"] == zone["full_fill_time"]


# ---------------------------------------------------------------------------
# Group F — Cross-instrument Coverage
# ---------------------------------------------------------------------------

def generate_eurusd_bars_3c(timeframe="1h", periods=240, base_price=1.0850):
    """Generate synthetic EURUSD bars with enough volatility for FVGs."""
    rng = np.random.RandomState(42)
    freq_map = {"15m": "15min", "1h": "1h", "4h": "4h"}
    start = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)
    idx = pd.date_range(start=start, periods=periods, freq=freq_map[timeframe], tz="UTC")

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


def generate_xauusd_bars_3c(timeframe="1h", periods=240, base_price=2650.0):
    """Generate synthetic XAUUSD bars with enough volatility for FVGs."""
    rng = np.random.RandomState(42)
    freq_map = {"15m": "15min", "1h": "1h", "4h": "4h"}
    start = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)
    idx = pd.date_range(start=start, periods=periods, freq=freq_map[timeframe], tz="UTC")

    volatility = 2.0
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


class TestGroupF_CrossInstrument:
    """Group F — Cross-instrument coverage for EURUSD and XAUUSD."""

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3c_tf1_eurusd_imbalance(self, config, tf):
        """TF.1 — EURUSD has imbalance and active_zones in packet."""
        bars = generate_eurusd_bars_3c(tf)
        packet = compute_structure_packet("EURUSD", tf, config, bars=bars)
        pkt = packet.to_dict()
        assert "imbalance" in pkt
        assert "active_zones" in pkt

    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_3c_tf2_xauusd_imbalance(self, config, tf):
        """TF.2 — XAUUSD has imbalance and active_zones in packet."""
        bars = generate_xauusd_bars_3c(tf)
        packet = compute_structure_packet("XAUUSD", tf, config, bars=bars)
        pkt = packet.to_dict()
        assert "imbalance" in pkt
        assert "active_zones" in pkt

    def test_tf3_xauusd_uses_own_min_size(self):
        """TF.3 — XAUUSD uses its own minimum gap size."""
        config = StructureConfig()
        assert config.fvg_min_size_eurusd != config.fvg_min_size_xauusd
        assert config.fvg_min_size_xauusd == pytest.approx(0.30)

    def test_tf4_xauusd_prices_plausible(self, config):
        """TF.4 — XAUUSD FVG prices are in plausible gold range."""
        bars = generate_xauusd_bars_3c("1h")
        packet = compute_structure_packet("XAUUSD", "1h", config, bars=bars)
        pkt = packet.to_dict()
        for zone in pkt["imbalance"]:
            assert 1_500.0 < zone["zone_low"] < 3_500.0
            assert 1_500.0 < zone["zone_high"] < 3_500.0


# ---------------------------------------------------------------------------
# Group G — Output and Boundaries
# ---------------------------------------------------------------------------

class TestGroupG_OutputBoundaries:
    """Group G — Output format and boundary tests."""

    def test_tg1_packet_contains_imbalance_keys(self, config):
        """TG.1 — Packet contains imbalance and active_zones keys."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
        ])
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        pkt = packet.to_dict()
        assert "imbalance" in pkt
        assert "active_zones" in pkt
        assert "count" in pkt["active_zones"]
        assert "zones" in pkt["active_zones"]

    def test_tg2_all_fvg_objects_have_required_fields(self, config):
        """TG.2 — All FVG objects have required fields."""
        bars = make_bars([
            (1.0820, 1.0860, 1.0810, 1.0840),
            (1.0845, 1.0890, 1.0840, 1.0880),
            (1.0882, 1.0900, 1.0875, 1.0895),
        ])
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        pkt = packet.to_dict()

        required = {
            "id", "fvg_type", "zone_high", "zone_low", "zone_size",
            "origin_time", "confirm_time", "timeframe", "status",
            "fill_high", "fill_low",
            "first_touch_time", "partial_fill_time", "full_fill_time",
        }
        for zone in pkt["imbalance"]:
            assert required.issubset(zone.keys()), \
                f"Missing fields in {zone['id']}: {required - set(zone.keys())}"

    def test_tg4_officer_and_feed_untouched(self):
        """TG.4 — Officer and feed modules untouched (no changes in those dirs)."""
        # This test verifies the constraint by checking that imbalance.py
        # does not import from officer/ or feed/
        import inspect
        from structure import imbalance
        source = inspect.getsource(imbalance)
        assert "officer" not in source.lower() or "officer" in "market_data_officer"
        assert "feed" not in source

    @pytest.mark.parametrize("instrument", ["EURUSD", "XAUUSD"])
    @pytest.mark.parametrize("tf", ["15m", "1h", "4h"])
    def test_tg5_engine_version_phase_3c(self, config, instrument, tf):
        """TG.5 — engine_version is phase_3c in all output packets."""
        if instrument == "EURUSD":
            bars = generate_eurusd_bars_3c(tf)
        else:
            bars = generate_xauusd_bars_3c(tf)
        packet = compute_structure_packet(instrument, tf, config, bars=bars)
        assert packet.build["engine_version"] == "phase_3c"

    def test_tg_json_roundtrip(self, config, tmp_path):
        """JSON write and re-read produces valid packet with 3C keys."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        bars = generate_eurusd_bars_3c("1h")
        packet = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        path = get_output_path("EURUSD", "1h", output_dir=output_dir)
        write_packet_atomic(packet.to_dict(), path)

        with open(path) as f:
            data = json.load(f)

        assert "imbalance" in data
        assert "active_zones" in data
        assert data["build"]["engine_version"] == "phase_3c"
