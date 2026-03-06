"""State summary builder — derives compact market state from features and timeframe data.

The summary is derivative and non-authoritative. It summarises; it does not replace raw bars.
"""

from typing import Dict

import pandas as pd

from .contracts import CoreFeatures, StateSummary

# Momentum thresholds for state classification
MOMENTUM_EXPANDING_THRESHOLD = 0.001
MOMENTUM_CONTRACTING_THRESHOLD = -0.001


def derive_trend(df: pd.DataFrame) -> str:
    """Derive trend state from MA relationship on a given timeframe DataFrame.

    Args:
        df: OHLCV DataFrame with 'close' column.

    Returns:
        'bullish', 'bearish', or 'neutral'.
    """
    if len(df) < 200:
        return "neutral"
    close = df["close"].iloc[-1]
    ma50 = df["close"].rolling(50).mean().iloc[-1]
    ma200 = df["close"].rolling(200).mean().iloc[-1]
    if close > ma50 > ma200:
        return "bullish"
    if close < ma50 < ma200:
        return "bearish"
    return "neutral"


def derive_momentum_state(momentum: float) -> str:
    """Classify momentum as expanding, contracting, or flat.

    Args:
        momentum: Rate-of-change value from core features.

    Returns:
        'expanding', 'contracting', or 'flat'.
    """
    if momentum > MOMENTUM_EXPANDING_THRESHOLD:
        return "expanding"
    elif momentum < MOMENTUM_CONTRACTING_THRESHOLD:
        return "contracting"
    return "flat"


def build_state_summary(
    features: CoreFeatures,
    timeframes: Dict[str, pd.DataFrame],
    data_quality: str = "validated",
) -> StateSummary:
    """Build a compact state summary from features and timeframe DataFrames.

    Args:
        features: Computed CoreFeatures instance.
        timeframes: Dict mapping timeframe label to OHLCV DataFrame.
        data_quality: Overall data quality label.

    Returns:
        StateSummary dataclass with all fields populated.
    """
    trend_1h = derive_trend(timeframes["1h"]) if "1h" in timeframes else "neutral"
    trend_4h = derive_trend(timeframes["4h"]) if "4h" in timeframes else "neutral"
    trend_1d = derive_trend(timeframes["1d"]) if "1d" in timeframes else "neutral"

    return StateSummary(
        trend_1h=trend_1h,
        trend_4h=trend_4h,
        trend_1d=trend_1d,
        volatility_regime=features.volatility_regime,
        momentum_state=derive_momentum_state(features.momentum),
        session_context=features.session_context,
        data_quality=data_quality,
    )
