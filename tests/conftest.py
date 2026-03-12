"""Shared fixtures for Phase 3E analyst tests.

Builds synthetic MarketPacketV2 instances with controlled structure blocks
for deterministic testing of the pre-filter and analyst pipeline.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest


# Re-export _generate_ohlcv for backward compatibility with tests/test_officer_v2.py
def _generate_ohlcv(
    periods: int,
    freq: str,
    base_price: float = 1.0850,
    volatility: float = 0.0005,
    end_near_now: bool = True,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    rng = np.random.RandomState(42)
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    index = pd.date_range(end=now_utc, periods=periods, freq=freq, tz="UTC")
    returns = rng.normal(0, volatility, periods)
    close = base_price + np.cumsum(returns)
    high = close + rng.uniform(0, volatility * 2, periods)
    low = close - rng.uniform(0, volatility * 2, periods)
    open_ = close + rng.normal(0, volatility * 0.5, periods)
    volume = rng.uniform(100, 5000, periods)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )
    df.index.name = "timestamp_utc"
    return df

from market_data_officer.officer.contracts import (
    ActiveFVGZone,
    CoreFeatures,
    FeatureBlock,
    LiquidityNearest,
    LiquidityTimeframeSummary,
    MarketPacketV2,
    QualityBlock,
    StateSummary,
    StructureBlock,
    StructureRecentEvent,
    StructureRegime,
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _make_core(
    atr_14: float = 0.00080,
    ma_50: float = 1.08500,
    ma_200: float = 1.08300,
    swing_high: float = 1.08800,
    swing_low: float = 1.08200,
) -> CoreFeatures:
    return CoreFeatures(
        atr_14=atr_14,
        volatility_regime="normal",
        momentum=0.5,
        ma_50=ma_50,
        ma_200=ma_200,
        swing_high=swing_high,
        swing_low=swing_low,
        rolling_range=0.00600,
        session_context="london",
    )


def _make_summary() -> StateSummary:
    return StateSummary(
        trend_1h="bullish",
        trend_4h="bullish",
        trend_1d="neutral",
        volatility_regime="normal",
        momentum_state="positive",
        session_context="london",
        data_quality="validated",
    )


def _make_quality() -> QualityBlock:
    return QualityBlock(
        manifest_valid=True,
        all_timeframes_present=True,
        staleness_minutes=5,
        stale=False,
        partial=False,
    )


def make_packet(
    instrument: str = "EURUSD",
    structure: StructureBlock | None = None,
    core: CoreFeatures | None = None,
    timeframes: dict | None = None,
) -> MarketPacketV2:
    """Build a synthetic MarketPacketV2 for testing."""
    if structure is None:
        structure = StructureBlock.unavailable()
    return MarketPacketV2(
        instrument=instrument,
        as_of_utc=_now_utc(),
        source={"vendor": "dukascopy", "canonical_tf": "1m", "quality": "validated"},
        timeframes=timeframes or {},
        features=FeatureBlock(core=core or _make_core()),
        state_summary=_make_summary(),
        quality=_make_quality(),
        structure=structure,
    )


# ---- Structure block builders ----


def make_bullish_4h_structure() -> StructureBlock:
    """Bullish 4h regime with aligned BOS, some LTF conflict."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bullish",
            last_bos_direction="bullish",
            last_mss_direction="bearish",
            trend_state="trending",
            structure_quality="clean",
            source_timeframe="4h",
        ),
        recent_events=[
            StructureRecentEvent(type="bos_bull", time=_now_utc(), timeframe="1h", reference_price=1.08650),
            StructureRecentEvent(type="mss_bear", time=_now_utc(), timeframe="15m", reference_price=1.08580),
        ],
        liquidity={
            "1h": LiquidityTimeframeSummary(
                active_count=3,
                nearest_above=LiquidityNearest(type="prior_day_high", price=1.08720, scope="external_liquidity", status="active"),
                nearest_below=LiquidityNearest(type="equal_lows", price=1.08410, scope="internal_liquidity", status="active"),
            ),
        },
        active_fvg_zones=[
            ActiveFVGZone(
                id="fvg_001", fvg_type="bullish_fvg",
                zone_high=1.08620, zone_low=1.08475, zone_size=0.00145,
                status="open", timeframe="1h", origin_time=_now_utc(),
            ),
        ],
    )


def make_bearish_4h_structure() -> StructureBlock:
    """Bearish 4h regime with aligned BOS."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bearish",
            last_bos_direction="bearish",
            last_mss_direction=None,
            trend_state="trending",
            structure_quality="clean",
            source_timeframe="4h",
        ),
        recent_events=[
            StructureRecentEvent(type="bos_bear", time=_now_utc(), timeframe="1h", reference_price=1.08200),
        ],
        liquidity={
            "1h": LiquidityTimeframeSummary(
                active_count=2,
                nearest_above=LiquidityNearest(type="prior_day_high", price=1.08700, scope="external_liquidity", status="active"),
                nearest_below=LiquidityNearest(type="prior_day_low", price=1.08100, scope="external_liquidity", status="active"),
            ),
        },
        active_fvg_zones=[
            ActiveFVGZone(
                id="fvg_002", fvg_type="bearish_fvg",
                zone_high=1.08700, zone_low=1.08600, zone_size=0.00100,
                status="open", timeframe="1h", origin_time=_now_utc(),
            ),
        ],
    )


def make_neutral_regime_structure() -> StructureBlock:
    """Neutral 4h regime — no directional bias."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="neutral",
            last_bos_direction=None,
            last_mss_direction=None,
            trend_state="ranging",
            structure_quality="choppy",
            source_timeframe="4h",
        ),
        recent_events=[],
        liquidity={},
        active_fvg_zones=[],
    )


def make_conflicting_regime_structure() -> StructureBlock:
    """4h bullish but 1h bearish MSS — conflicting regimes."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bullish",
            last_bos_direction="bullish",
            last_mss_direction="bearish",
            trend_state="trending",
            structure_quality="choppy",
            source_timeframe="4h",
        ),
        recent_events=[
            StructureRecentEvent(type="bos_bull", time=_now_utc(), timeframe="4h", reference_price=1.08700),
            StructureRecentEvent(type="mss_bear", time=_now_utc(), timeframe="1h", reference_price=1.08400),
        ],
        liquidity={},
        active_fvg_zones=[],
    )


def make_aligned_bos_mss_structure() -> StructureBlock:
    """Both last BOS and MSS are bullish — aligned."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bullish",
            last_bos_direction="bullish",
            last_mss_direction="bullish",
            trend_state="trending",
            structure_quality="clean",
            source_timeframe="4h",
        ),
        recent_events=[
            StructureRecentEvent(type="bos_bull", time=_now_utc(), timeframe="1h", reference_price=1.08650),
            StructureRecentEvent(type="mss_bull", time=_now_utc(), timeframe="15m", reference_price=1.08600),
        ],
        liquidity={
            "1h": LiquidityTimeframeSummary(
                active_count=2,
                nearest_above=LiquidityNearest(type="prior_day_high", price=1.08900, scope="external_liquidity", status="active"),
                nearest_below=LiquidityNearest(type="equal_lows", price=1.08200, scope="internal_liquidity", status="active"),
            ),
        },
        active_fvg_zones=[],
    )


def make_discount_fvg_structure(current_price: float = 1.08400) -> StructureBlock:
    """Active bullish FVG above current price (discount)."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bullish",
            last_bos_direction="bullish",
            last_mss_direction=None,
            trend_state="trending",
            structure_quality="clean",
            source_timeframe="4h",
        ),
        recent_events=[
            StructureRecentEvent(type="bos_bull", time=_now_utc(), timeframe="1h", reference_price=1.08650),
        ],
        liquidity={},
        active_fvg_zones=[
            ActiveFVGZone(
                id="fvg_discount", fvg_type="bullish_fvg",
                zone_high=1.08620, zone_low=1.08475, zone_size=0.00145,
                status="open", timeframe="1h", origin_time=_now_utc(),
            ),
        ],
    )


def make_inside_fvg_structure() -> StructureBlock:
    """Price inside an active FVG zone."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bullish",
            last_bos_direction="bullish",
            last_mss_direction=None,
            trend_state="trending",
            structure_quality="clean",
            source_timeframe="4h",
        ),
        recent_events=[],
        liquidity={},
        active_fvg_zones=[
            ActiveFVGZone(
                id="fvg_inside", fvg_type="bullish_fvg",
                zone_high=1.08620, zone_low=1.08475, zone_size=0.00145,
                status="open", timeframe="1h", origin_time=_now_utc(),
            ),
        ],
    )


def make_no_fvg_structure() -> StructureBlock:
    """Structure available but no active FVG zones."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bullish",
            last_bos_direction="bullish",
            last_mss_direction=None,
            trend_state="trending",
            structure_quality="clean",
            source_timeframe="4h",
        ),
        recent_events=[],
        liquidity={},
        active_fvg_zones=[],
    )


def make_bullish_reclaim_structure() -> StructureBlock:
    """Recent swept low-side level with reclaim (bullish signal)."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bullish",
            last_bos_direction="bullish",
            last_mss_direction=None,
            trend_state="trending",
            structure_quality="clean",
            source_timeframe="4h",
        ),
        recent_events=[],
        liquidity={
            "1h": LiquidityTimeframeSummary(
                active_count=2,
                nearest_above=LiquidityNearest(type="prior_day_high", price=1.08720, scope="external_liquidity", status="active"),
                nearest_below=LiquidityNearest(type="equal_lows", price=1.08410, scope="internal_liquidity", status="swept"),
            ),
        },
        active_fvg_zones=[],
    )


def make_liquidity_close_above_structure(atr_14: float = 0.00080) -> StructureBlock:
    """External liquidity level just above current price (within 0.5 ATR)."""
    # Price ~1.08500, PDH at 1.08530 → distance 0.00030 < 0.5 * 0.00080 = 0.00040
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bullish",
            last_bos_direction="bullish",
            last_mss_direction=None,
            trend_state="trending",
            structure_quality="clean",
            source_timeframe="4h",
        ),
        recent_events=[],
        liquidity={
            "1h": LiquidityTimeframeSummary(
                active_count=2,
                nearest_above=LiquidityNearest(type="prior_day_high", price=1.08530, scope="external_liquidity", status="active"),
                nearest_below=LiquidityNearest(type="equal_lows", price=1.08200, scope="internal_liquidity", status="active"),
            ),
        },
        active_fvg_zones=[],
    )


def make_ltf_mss_conflict_structure() -> StructureBlock:
    """HTF bullish, 15m bearish MSS — caution flag expected."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bullish",
            last_bos_direction="bullish",
            last_mss_direction="bearish",
            trend_state="trending",
            structure_quality="clean",
            source_timeframe="4h",
        ),
        recent_events=[
            StructureRecentEvent(type="bos_bull", time=_now_utc(), timeframe="1h", reference_price=1.08650),
            StructureRecentEvent(type="mss_bear", time=_now_utc(), timeframe="15m", reference_price=1.08580),
        ],
        liquidity={},
        active_fvg_zones=[],
    )


def make_clean_bullish_structure() -> StructureBlock:
    """Clean bullish structure with no conflicts."""
    return StructureBlock(
        available=True,
        source_engine_version="3D.1",
        as_of=_now_utc(),
        regime=StructureRegime(
            bias="bullish",
            last_bos_direction="bullish",
            last_mss_direction=None,
            trend_state="trending",
            structure_quality="clean",
            source_timeframe="4h",
        ),
        recent_events=[
            StructureRecentEvent(type="bos_bull", time=_now_utc(), timeframe="1h", reference_price=1.08650),
        ],
        liquidity={
            "1h": LiquidityTimeframeSummary(
                active_count=2,
                nearest_above=LiquidityNearest(type="prior_day_high", price=1.09000, scope="external_liquidity", status="active"),
                nearest_below=LiquidityNearest(type="equal_lows", price=1.08000, scope="internal_liquidity", status="active"),
            ),
        },
        active_fvg_zones=[],
    )
