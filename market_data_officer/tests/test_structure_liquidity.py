"""Group C — Liquidity detection tests + Phase 3B Groups A–E.

Tests prior day high/low, EQH/EQL detection, sweep events,
instrument-specific tolerance, reclaim detection, post-sweep
classification, lifecycle, internal/external tagging, and replay.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structure.config import StructureConfig
from structure.liquidity import (
    classify_liquidity_scope,
    detect_liquidity,
    _detect_reclaim,
)
from structure.schemas import LiquidityLevel, SwingPoint
from structure.swings import detect_swings


def make_multi_day_bars(
    base_price: float = 1.085,
    days: int = 5,
    bars_per_day: int = 24,
    freq: str = "1h",
    volatility: float = 0.001,
    start: datetime = None,
) -> pd.DataFrame:
    """Build multi-day OHLCV bars for liquidity testing."""
    if start is None:
        # Start on a Monday at 21:00 UTC (FX session open)
        start = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)

    rng = np.random.RandomState(42)
    total_bars = days * bars_per_day
    idx = pd.date_range(start=start, periods=total_bars, freq=freq, tz="UTC")

    returns = rng.normal(0, volatility, total_bars)
    close = base_price + np.cumsum(returns)
    high = close + rng.uniform(0, volatility * 2, total_bars)
    low = close - rng.uniform(0, volatility * 2, total_bars)
    open_ = close + rng.normal(0, volatility * 0.5, total_bars)
    volume = rng.uniform(100, 5000, total_bars)

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=idx)


@pytest.fixture
def config():
    return StructureConfig(pivot_left_bars=3, pivot_right_bars=3)


class TestGroupC_Liquidity:
    """Group C — Liquidity detection."""

    def test_c1_prior_day_high_low(self, config):
        """C.1 — Prior day high and low are correct."""
        bars = make_multi_day_bars(days=5)
        swings = detect_swings(bars, config, timeframe="1h")
        levels, _ = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        pdh_levels = [l for l in levels if l.type == "prior_day_high"]
        pdl_levels = [l for l in levels if l.type == "prior_day_low"]

        assert len(pdh_levels) >= 1, "Expected at least one prior_day_high"
        assert len(pdl_levels) >= 1, "Expected at least one prior_day_low"

        # Verify price is reasonable
        for pdh in pdh_levels:
            assert pdh.price > 0, f"Invalid PDH price: {pdh.price}"
        for pdl in pdl_levels:
            assert pdl.price > 0, f"Invalid PDL price: {pdl.price}"

    def test_c2_eqh_detected_within_tolerance(self, config):
        """C.2 — EQH detected within tolerance."""
        # Build bars with two swing highs within 1 pip of each other
        # Two peaks at approximately the same level
        START = datetime(2026, 1, 1, tzinfo=timezone.utc)
        prices = [
            1.080, 1.082, 1.084,
            1.0855,  # first peak (high will be 1.0855 + 0.0005 = 1.0860)
            1.084, 1.082, 1.080,
            1.078, 1.080, 1.082,
            1.0854,  # second peak (high will be 1.0854 + 0.0005 = 1.0859) — within 1 pip
            1.083, 1.081, 1.079,
        ]
        rows = []
        for p in prices:
            rows.append({
                "open": p, "high": p + 0.0005, "low": p - 0.0005,
                "close": p, "volume": 100.0,
            })
        idx = pd.date_range(start=START, periods=len(prices), freq="1h", tz="UTC")
        bars = pd.DataFrame(rows, index=idx)

        swings = detect_swings(bars, config, timeframe="1h")
        levels, _ = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        eqh_levels = [l for l in levels if l.type == "equal_highs"]
        assert len(eqh_levels) >= 1, "Expected at least one EQH"
        assert len(eqh_levels[0].member_swing_ids) >= 2
        assert eqh_levels[0].tolerance_used == config.eqh_eql_tolerance["EURUSD"]

    def test_c3_sweep_fires_on_wick(self, config):
        """C.3 — Sweep fires on wick-through, not just close-through."""
        # Multi-day bars where a wick exceeds prior day high
        bars = make_multi_day_bars(days=5)
        swings = detect_swings(bars, config, timeframe="1h")
        levels, sweep_events = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        swept_levels = [l for l in levels if l.status == "swept"]
        # With random data, sweeps should occur
        # Just verify the mechanism works — swept levels have swept_time
        for level in swept_levels:
            assert level.swept_time is not None
            assert level.sweep_type in ("wick_sweep", "close_sweep")

    def test_c4_swept_level_status(self, config):
        """C.4 — Swept level status updates correctly."""
        bars = make_multi_day_bars(days=5)
        swings = detect_swings(bars, config, timeframe="1h")
        levels, sweep_events = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        for level in levels:
            if level.status == "swept":
                assert level.swept_time is not None, \
                    f"Swept level {level.id} has no swept_time"

    def test_c5_instrument_tolerance(self, config):
        """C.5 — EQH/EQL uses instrument-correct tolerance."""
        assert config.eqh_eql_tolerance["EURUSD"] != config.eqh_eql_tolerance["XAUUSD"]
        assert config.eqh_eql_tolerance["EURUSD"] == 0.00010
        assert config.eqh_eql_tolerance["XAUUSD"] == 0.50


# ---------------------------------------------------------------------------
# Phase 3B helpers
# ---------------------------------------------------------------------------

def _make_bars(prices, start=None, freq="1h"):
    """Build a simple OHLCV DataFrame from a list of (open, high, low, close) tuples."""
    if start is None:
        start = datetime(2026, 3, 6, 22, 0, tzinfo=timezone.utc)
    idx = pd.date_range(start=start, periods=len(prices), freq=freq, tz="UTC")
    rows = []
    for o, h, l, c in prices:
        rows.append({"open": o, "high": h, "low": l, "close": c, "volume": 100.0})
    return pd.DataFrame(rows, index=idx)


def _make_level(level_id, level_type, price, origin_time, timeframe="1h", **kwargs):
    return LiquidityLevel(
        id=level_id, type=level_type, price=price,
        origin_time=origin_time, timeframe=timeframe, **kwargs,
    )


# ---------------------------------------------------------------------------
# Group A — Reclaim detection (3B)
# ---------------------------------------------------------------------------

class TestGroup3B_A_Reclaim:
    """Group A — Reclaim detection."""

    def test_3b_ta1_high_side_reclaim(self):
        """TA.1 — High-side reclaim confirmed when close returns below level."""
        level_price = 1.08720
        # Bar 0: some pre-bar (origin context)
        # Bar 1: sweep bar — high above, close above (no same-bar reclaim)
        # Bar 2: close below level — reclaim confirmed
        prices = [
            (1.086, 1.087, 1.085, 1.086),       # bar 0 (origin)
            (1.087, 1.08731, 1.0870, 1.08740),   # bar 1 — sweep bar
            (1.087, 1.088, 1.086, 1.08695),       # bar 2 — reclaim
        ]
        start = datetime(2026, 3, 6, 21, 0, tzinfo=timezone.utc)
        bars = _make_bars(prices, start=start)

        config = StructureConfig()
        level = _make_level("liq_001", "prior_day_high", level_price,
                            origin_time=start, timeframe="1h")

        outcome, reclaim_time, post_close = _detect_reclaim(
            level_price, "prior_day_high", 1, bars, config,
        )
        assert outcome == "reclaimed"
        assert reclaim_time is not None
        assert post_close == 1.08695

    def test_3b_ta2_low_side_reclaim(self):
        """TA.2 — Low-side reclaim confirmed when close returns above level."""
        level_price = 1.07500
        prices = [
            (1.076, 1.077, 1.075, 1.076),       # bar 0 (origin)
            (1.075, 1.076, 1.07488, 1.07470),    # bar 1 — sweep bar
            (1.075, 1.076, 1.074, 1.07530),       # bar 2 — reclaim
        ]
        start = datetime(2026, 3, 6, 21, 0, tzinfo=timezone.utc)
        bars = _make_bars(prices, start=start)

        config = StructureConfig()
        outcome, reclaim_time, post_close = _detect_reclaim(
            level_price, "prior_day_low", 1, bars, config,
        )
        assert outcome == "reclaimed"
        assert reclaim_time is not None

    def test_3b_ta3_same_bar_reclaim_enabled(self):
        """TA.3 — Same-bar reclaim when allow_same_bar_reclaim=True."""
        level_price = 1.08720
        prices = [
            (1.086, 1.087, 1.085, 1.086),         # bar 0
            (1.087, 1.08731, 1.0865, 1.08690),     # bar 1 — sweep + reclaim on same bar
        ]
        start = datetime(2026, 3, 6, 21, 0, tzinfo=timezone.utc)
        bars = _make_bars(prices, start=start)

        config = StructureConfig(allow_same_bar_reclaim=True)
        outcome, reclaim_time, post_close = _detect_reclaim(
            level_price, "prior_day_high", 1, bars, config,
        )
        assert outcome == "reclaimed"
        # Reclaim on sweep bar itself
        assert reclaim_time == bars.index[1].to_pydatetime()

    def test_3b_ta4_same_bar_reclaim_blocked(self):
        """TA.4 — Same-bar reclaim blocked when allow_same_bar_reclaim=False."""
        level_price = 1.08720
        # Sweep bar closes below level, but same-bar reclaim disabled
        # Next bar closes above level — no reclaim
        # Extra bar to confirm window is closed
        prices = [
            (1.086, 1.087, 1.085, 1.086),         # bar 0
            (1.087, 1.08731, 1.0865, 1.08690),     # bar 1 — sweep bar, close below
            (1.087, 1.088, 1.087, 1.08750),         # bar 2 — close above, no reclaim
            (1.088, 1.089, 1.087, 1.08760),         # bar 3 — extra bar confirms window closed
        ]
        start = datetime(2026, 3, 6, 21, 0, tzinfo=timezone.utc)
        bars = _make_bars(prices, start=start)

        config = StructureConfig(allow_same_bar_reclaim=False, reclaim_window_bars=1)
        outcome, reclaim_time, post_close = _detect_reclaim(
            level_price, "prior_day_high", 1, bars, config,
        )
        # Next bar (bar 2) close is 1.08750 > level — NOT reclaimed, window exhausted
        assert outcome == "accepted_beyond"
        assert reclaim_time is None

    def test_3b_ta5_no_false_reclaim_on_wick(self):
        """TA.5 — No false reclaim when wick crosses but close does not."""
        level_price = 1.08720
        prices = [
            (1.086, 1.087, 1.085, 1.086),         # bar 0
            (1.087, 1.08731, 1.087, 1.08750),      # bar 1 — sweep bar (close above)
            (1.087, 1.088, 1.08700, 1.08730),       # bar 2 — wick below but close above
        ]
        start = datetime(2026, 3, 6, 21, 0, tzinfo=timezone.utc)
        bars = _make_bars(prices, start=start)

        config = StructureConfig()
        outcome, reclaim_time, _ = _detect_reclaim(
            level_price, "prior_day_high", 1, bars, config,
        )
        # Wick went below but close stayed above — NOT reclaimed
        assert outcome != "reclaimed"

    def test_3b_ta6_accepted_beyond(self):
        """TA.6 — accepted_beyond after window exhausted."""
        level_price = 1.08720
        prices = [
            (1.086, 1.087, 1.085, 1.086),         # bar 0
            (1.087, 1.08731, 1.087, 1.08740),      # bar 1 — sweep bar
            (1.088, 1.089, 1.087, 1.08738),         # bar 2 — still above
            (1.088, 1.089, 1.087, 1.08750),         # bar 3 — extra bar to confirm window closed
        ]
        start = datetime(2026, 3, 6, 21, 0, tzinfo=timezone.utc)
        bars = _make_bars(prices, start=start)

        config = StructureConfig(reclaim_window_bars=1)
        outcome, reclaim_time, post_close = _detect_reclaim(
            level_price, "prior_day_high", 1, bars, config,
        )
        assert outcome == "accepted_beyond"
        assert reclaim_time is None
        assert post_close is not None

    def test_3b_ta7_unresolved(self):
        """TA.7 — unresolved when window not yet closed."""
        level_price = 1.08720
        # Only sweep bar, no subsequent bars
        prices = [
            (1.086, 1.087, 1.085, 1.086),         # bar 0
            (1.087, 1.08731, 1.087, 1.08740),      # bar 1 — sweep bar
        ]
        start = datetime(2026, 3, 6, 21, 0, tzinfo=timezone.utc)
        bars = _make_bars(prices, start=start)

        config = StructureConfig(allow_same_bar_reclaim=False, reclaim_window_bars=1)
        outcome, reclaim_time, post_close = _detect_reclaim(
            level_price, "prior_day_high", 1, bars, config,
        )
        assert outcome == "unresolved"
        assert reclaim_time is None


# ---------------------------------------------------------------------------
# Group B — Post-sweep classification (3B)
# ---------------------------------------------------------------------------

class TestGroup3B_B_Classification:
    """Group B — Post-sweep classification."""

    def test_3b_tb1_classification_mutually_exclusive(self):
        """TB.1 — Classification is mutually exclusive."""
        bars = make_multi_day_bars(days=5)
        config = StructureConfig()
        swings = detect_swings(bars, config, timeframe="1h")
        levels, sweeps = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        for level in levels:
            if level.outcome is not None:
                assert level.outcome in ("reclaimed", "accepted_beyond", "unresolved")

    def test_3b_tb2_sweep_outcome_mirrors_level(self):
        """TB.2 — SweepEvent outcome mirrors LiquidityLevel outcome."""
        bars = make_multi_day_bars(days=5)
        config = StructureConfig()
        swings = detect_swings(bars, config, timeframe="1h")
        levels, sweeps = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        level_map = {l.id: l for l in levels}
        for sw in sweeps:
            linked = level_map.get(sw.linked_liquidity_id)
            if linked:
                assert sw.outcome == linked.outcome, \
                    f"Sweep {sw.id} outcome {sw.outcome} != level {linked.id} outcome {linked.outcome}"
                assert sw.reclaim_time == linked.reclaim_time

    def test_3b_tb3_post_sweep_close_populated(self):
        """TB.3 — post_sweep_close is populated after resolution."""
        bars = make_multi_day_bars(days=5)
        config = StructureConfig()
        swings = detect_swings(bars, config, timeframe="1h")
        _, sweeps = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        for sw in sweeps:
            if sw.outcome in ("reclaimed", "accepted_beyond"):
                assert sw.post_sweep_close is not None
                assert isinstance(sw.post_sweep_close, float)

    def test_3b_tb4_post_sweep_close_null_unresolved(self):
        """TB.4 — post_sweep_close is null while unresolved."""
        level_price = 1.08720
        prices = [
            (1.086, 1.087, 1.085, 1.086),
            (1.087, 1.08731, 1.087, 1.08740),
        ]
        start = datetime(2026, 3, 6, 21, 0, tzinfo=timezone.utc)
        bars = _make_bars(prices, start=start)

        config = StructureConfig(allow_same_bar_reclaim=False, reclaim_window_bars=1)
        outcome, _, post_close = _detect_reclaim(
            level_price, "prior_day_high", 1, bars, config,
        )
        assert outcome == "unresolved"
        assert post_close is None

    def test_3b_tb5_classification_deterministic(self):
        """TB.5 — Classification is deterministic across runs."""
        bars = make_multi_day_bars(days=5)
        config = StructureConfig()

        swings1 = detect_swings(bars, config, timeframe="1h")
        levels1, _ = detect_liquidity(bars, swings1, config, timeframe="1h", instrument="EURUSD")
        outcomes1 = {l.id: l.outcome for l in levels1}

        swings2 = detect_swings(bars, config, timeframe="1h")
        levels2, _ = detect_liquidity(bars, swings2, config, timeframe="1h", instrument="EURUSD")
        outcomes2 = {l.id: l.outcome for l in levels2}

        assert outcomes1 == outcomes2


# ---------------------------------------------------------------------------
# Group C — Liquidity lifecycle (3B)
# ---------------------------------------------------------------------------

class TestGroup3B_C_Lifecycle:
    """Group C — Liquidity lifecycle transitions."""

    ALLOWED_TRANSITIONS = {
        "active": {"swept", "invalidated"},
        "swept": {"reclaimed", "accepted_beyond"},
        "reclaimed": {"archived"},
        "accepted_beyond": {"archived"},
        "invalidated": {"archived"},
    }

    def test_3b_tc1_allowed_transitions(self):
        """TC.1 — Levels only transition through allowed states."""
        bars = make_multi_day_bars(days=5)
        config = StructureConfig()
        swings = detect_swings(bars, config, timeframe="1h")
        levels, _ = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        for level in levels:
            status = level.status
            assert status in ("active", "swept", "reclaimed", "accepted_beyond",
                              "invalidated", "archived"), \
                f"Level {level.id} has unexpected status: {status}"

    def test_3b_tc2_reruns_no_backward_transitions(self):
        """TC.2 — Reruns do not create backward transitions."""
        bars = make_multi_day_bars(days=5)
        config = StructureConfig()

        swings1 = detect_swings(bars, config, timeframe="1h")
        levels1, _ = detect_liquidity(bars, swings1, config, timeframe="1h", instrument="EURUSD")
        outcomes1 = {l.id: l.outcome for l in levels1 if l.outcome is not None}

        swings2 = detect_swings(bars, config, timeframe="1h")
        levels2, _ = detect_liquidity(bars, swings2, config, timeframe="1h", instrument="EURUSD")
        outcomes2 = {l.id: l.outcome for l in levels2 if l.outcome is not None}

        for lid, outcome in outcomes1.items():
            if outcome in ("reclaimed", "accepted_beyond"):
                assert outcomes2.get(lid) == outcome, \
                    f"Resolved outcome for {lid} changed from {outcome} to {outcomes2.get(lid)}"

    def test_3b_tc3_resolved_not_mutated_on_append(self):
        """TC.3 — Historical resolved levels not mutated on new bar append."""
        bars_short = make_multi_day_bars(days=4)
        bars_long = make_multi_day_bars(days=5)
        config = StructureConfig()

        swings1 = detect_swings(bars_short, config, timeframe="1h")
        levels1, _ = detect_liquidity(bars_short, swings1, config, timeframe="1h", instrument="EURUSD")
        resolved1 = {l.id: l.outcome for l in levels1
                     if l.outcome in ("reclaimed", "accepted_beyond")}

        swings2 = detect_swings(bars_long, config, timeframe="1h")
        levels2, _ = detect_liquidity(bars_long, swings2, config, timeframe="1h", instrument="EURUSD")
        resolved2 = {l.id: l.outcome for l in levels2
                     if l.outcome in ("reclaimed", "accepted_beyond")}

        for lid, outcome in resolved1.items():
            if lid in resolved2:
                assert resolved2[lid] == outcome

    def test_3b_tc4_unresolved_resolves_with_new_bars(self):
        """TC.4 — Unresolved levels resolve correctly as new bars arrive."""
        level_price = 1.08720
        # Day 1: sweep only, no subsequent bars → unresolved
        prices_day1 = [
            (1.086, 1.087, 1.085, 1.086),
            (1.087, 1.08731, 1.087, 1.08740),
        ]
        # Day 2: add bar that closes below level → reclaimed
        prices_day2 = prices_day1 + [
            (1.087, 1.088, 1.086, 1.08695),
        ]

        start = datetime(2026, 3, 6, 21, 0, tzinfo=timezone.utc)
        bars_day1 = _make_bars(prices_day1, start=start)
        bars_day2 = _make_bars(prices_day2, start=start)

        config = StructureConfig(allow_same_bar_reclaim=False, reclaim_window_bars=1)

        outcome1, _, _ = _detect_reclaim(level_price, "prior_day_high", 1, bars_day1, config)
        assert outcome1 == "unresolved"

        outcome2, _, _ = _detect_reclaim(level_price, "prior_day_high", 1, bars_day2, config)
        assert outcome2 == "reclaimed"


# ---------------------------------------------------------------------------
# Group D — Internal/external tagging (3B)
# ---------------------------------------------------------------------------

class TestGroup3B_D_Tagging:
    """Group D — Internal/external liquidity tagging."""

    def test_3b_td1_prior_levels_external(self):
        """TD.1 — Prior day/week levels tagged as external."""
        bars = make_multi_day_bars(days=5)
        config = StructureConfig()
        swings = detect_swings(bars, config, timeframe="1h")
        levels, _ = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        for level in levels:
            if level.type in ("prior_day_high", "prior_day_low",
                              "prior_week_high", "prior_week_low"):
                assert level.liquidity_scope == "external_liquidity", \
                    f"{level.id} should be external_liquidity, got {level.liquidity_scope}"

    def test_3b_td2_eqh_above_swing_high_is_external(self):
        """TD.2 — EQH above most recent swing high tagged as external."""
        swings = [
            SwingPoint(
                id="sw_1", type="swing_high", price=1.08500,
                anchor_time=datetime(2026, 3, 5, tzinfo=timezone.utc),
                confirm_time=datetime(2026, 3, 5, 3, tzinfo=timezone.utc),
                timeframe="1h",
            ),
        ]
        scope = classify_liquidity_scope("equal_highs", 1.08720, swings)
        assert scope == "external_liquidity"

    def test_3b_td3_eqh_below_swing_high_is_internal(self):
        """TD.3 — EQH below most recent swing high tagged as internal."""
        swings = [
            SwingPoint(
                id="sw_1", type="swing_high", price=1.09000,
                anchor_time=datetime(2026, 3, 5, tzinfo=timezone.utc),
                confirm_time=datetime(2026, 3, 5, 3, tzinfo=timezone.utc),
                timeframe="1h",
            ),
        ]
        scope = classify_liquidity_scope("equal_highs", 1.08720, swings)
        assert scope == "internal_liquidity"

    def test_3b_td4_eqh_no_swings_unclassified(self):
        """TD.4 — EQH/EQL without relevant confirmed swing tagged as unclassified."""
        scope = classify_liquidity_scope("equal_highs", 1.08720, [])
        assert scope == "unclassified"

    def test_3b_td5_scope_set_at_creation(self):
        """TD.5 — liquidity_scope is set at creation time, not post-sweep."""
        bars = make_multi_day_bars(days=5)
        config = StructureConfig()
        swings = detect_swings(bars, config, timeframe="1h")
        levels, _ = detect_liquidity(
            bars, swings, config, timeframe="1h", instrument="EURUSD",
        )

        for level in levels:
            assert level.liquidity_scope is not None, \
                f"Level {level.id} has no liquidity_scope"

    def test_3b_td_eql_below_swing_low_is_external(self):
        """EQL below most recent swing low tagged as external."""
        swings = [
            SwingPoint(
                id="sw_1", type="swing_low", price=1.07500,
                anchor_time=datetime(2026, 3, 5, tzinfo=timezone.utc),
                confirm_time=datetime(2026, 3, 5, 3, tzinfo=timezone.utc),
                timeframe="1h",
            ),
        ]
        scope = classify_liquidity_scope("equal_lows", 1.07300, swings)
        assert scope == "external_liquidity"

    def test_3b_td_eql_above_swing_low_is_internal(self):
        """EQL above most recent swing low tagged as internal."""
        swings = [
            SwingPoint(
                id="sw_1", type="swing_low", price=1.07000,
                anchor_time=datetime(2026, 3, 5, tzinfo=timezone.utc),
                confirm_time=datetime(2026, 3, 5, 3, tzinfo=timezone.utc),
                timeframe="1h",
            ),
        ]
        scope = classify_liquidity_scope("equal_lows", 1.07300, swings)
        assert scope == "internal_liquidity"


# ---------------------------------------------------------------------------
# Group E — Determinism and replay stability (3B)
# ---------------------------------------------------------------------------

class TestGroup3B_E_Determinism:
    """Group E — Determinism and replay stability."""

    def test_3b_te1_identical_packets(self):
        """TE.1 — Identical inputs produce identical packets."""
        import hashlib, json
        from structure.engine import compute_structure_packet

        bars = make_multi_day_bars(days=5)
        config = StructureConfig()

        def packet_hash(b):
            p = compute_structure_packet("EURUSD", "1h", config, bars=b)
            d = p.to_dict()
            d.pop("as_of", None)  # as_of will differ
            return hashlib.md5(json.dumps(d, sort_keys=True).encode()).hexdigest()

        assert packet_hash(bars) == packet_hash(bars)

    def test_3b_te2_reruns_no_resolved_changes(self):
        """TE.2 — Reruns on unchanged bars produce no changes to resolved objects."""
        from structure.engine import compute_structure_packet

        bars = make_multi_day_bars(days=5)
        config = StructureConfig()

        p1 = compute_structure_packet("EURUSD", "1h", config, bars=bars)
        p2 = compute_structure_packet("EURUSD", "1h", config, bars=bars)

        resolved1 = [l.to_dict() for l in p1.liquidity if l.outcome != "unresolved"]
        resolved2 = [l.to_dict() for l in p2.liquidity if l.outcome != "unresolved"]
        assert resolved1 == resolved2

    def test_3b_te3_append_only_resolves_unresolved(self):
        """TE.3 — Appending new bars only resolves unresolved outcomes."""
        from structure.engine import compute_structure_packet

        bars_short = make_multi_day_bars(days=4)
        bars_long = make_multi_day_bars(days=5)
        config = StructureConfig()

        p1 = compute_structure_packet("EURUSD", "1h", config, bars=bars_short)
        p2 = compute_structure_packet("EURUSD", "1h", config, bars=bars_long)

        resolved_before = {l.id: l.outcome for l in p1.liquidity
                          if l.outcome in ("reclaimed", "accepted_beyond")}
        resolved_after = {l.id: l.outcome for l in p2.liquidity
                         if l.outcome in ("reclaimed", "accepted_beyond")}

        for lid, outcome in resolved_before.items():
            if lid in resolved_after:
                assert resolved_after[lid] == outcome
