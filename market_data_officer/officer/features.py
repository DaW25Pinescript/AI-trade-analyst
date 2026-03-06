"""Core feature computation from loaded timeframe DataFrames.

All features are computed from already-loaded DataFrames — no file I/O,
no HTTP calls, no feed pipeline interaction. Features must be deterministic.
"""

from datetime import datetime, timezone

import pandas as pd

from .contracts import CoreFeatures

# Swing detection lookback (bars on each side of pivot)
SWING_LOOKBACK = 5

# Rolling range window
ROLLING_RANGE_WINDOW = 20

# ATR period
ATR_PERIOD = 14

# Momentum (ROC) period
MOMENTUM_PERIOD = 14

# Volatility regime thresholds (percentiles of rolling ATR)
VOLATILITY_LOW_PERCENTILE = 25
VOLATILITY_HIGH_PERCENTILE = 75
VOLATILITY_ROLLING_WINDOW = 50

# Session windows (UTC hours)
SESSION_WINDOWS = {
    "asian": (0, 8),
    "london": (8, 13),
    "overlap": (13, 17),
    "new_york": (17, 21),
}


def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    """Compute Average True Range over the given period.

    Args:
        df: OHLCV DataFrame with 'high', 'low', 'close' columns.
        period: ATR lookback period.

    Returns:
        ATR value as float. Returns 0.0 if insufficient data.
    """
    if len(df) < period + 1:
        return 0.0

    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(period).mean().iloc[-1]
    return float(atr)


def compute_volatility_regime(
    df: pd.DataFrame,
    period: int = ATR_PERIOD,
    rolling_window: int = VOLATILITY_ROLLING_WINDOW,
) -> str:
    """Classify volatility regime based on ATR vs rolling ATR baseline.

    Args:
        df: OHLCV DataFrame.
        period: ATR period.
        rolling_window: Window for rolling ATR percentile comparison.

    Returns:
        'low', 'normal', or 'expanding'.
    """
    if len(df) < period + rolling_window:
        return "normal"

    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    rolling_atr = true_range.rolling(period).mean()

    current_atr = rolling_atr.iloc[-1]
    atr_history = rolling_atr.dropna().tail(rolling_window)

    low_threshold = atr_history.quantile(VOLATILITY_LOW_PERCENTILE / 100)
    high_threshold = atr_history.quantile(VOLATILITY_HIGH_PERCENTILE / 100)

    if current_atr < low_threshold:
        return "low"
    elif current_atr > high_threshold:
        return "expanding"
    return "normal"


def compute_momentum(df: pd.DataFrame, period: int = MOMENTUM_PERIOD) -> float:
    """Compute rate-of-change of close over the given period.

    Args:
        df: OHLCV DataFrame with 'close' column.
        period: ROC lookback period.

    Returns:
        Momentum (ROC) value as float. Returns 0.0 if insufficient data.
    """
    if len(df) < period + 1:
        return 0.0
    close = df["close"]
    roc = (close.iloc[-1] - close.iloc[-1 - period]) / close.iloc[-1 - period]
    return float(roc)


def compute_swing_high(df: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> float:
    """Find the most recent swing high (pivot high) on the given bars.

    A swing high is a bar whose high is greater than the highs of
    `lookback` bars on each side.

    Args:
        df: OHLCV DataFrame with 'high' column.
        lookback: Number of bars on each side to confirm pivot.

    Returns:
        Most recent swing high price. Returns 0.0 if none found.
    """
    if len(df) < 2 * lookback + 1:
        return 0.0

    highs = df["high"].values
    for i in range(len(highs) - 1 - lookback, lookback - 1, -1):
        is_pivot = True
        for j in range(1, lookback + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_pivot = False
                break
        if is_pivot:
            return float(highs[i])
    return 0.0


def compute_swing_low(df: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> float:
    """Find the most recent swing low (pivot low) on the given bars.

    A swing low is a bar whose low is less than the lows of
    `lookback` bars on each side.

    Args:
        df: OHLCV DataFrame with 'low' column.
        lookback: Number of bars on each side to confirm pivot.

    Returns:
        Most recent swing low price. Returns 0.0 if none found.
    """
    if len(df) < 2 * lookback + 1:
        return 0.0

    lows = df["low"].values
    for i in range(len(lows) - 1 - lookback, lookback - 1, -1):
        is_pivot = True
        for j in range(1, lookback + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_pivot = False
                break
        if is_pivot:
            return float(lows[i])
    return 0.0


def compute_rolling_range(
    df: pd.DataFrame, window: int = ROLLING_RANGE_WINDOW
) -> float:
    """Compute the high-low range over the last N bars.

    Args:
        df: OHLCV DataFrame with 'high' and 'low' columns.
        window: Number of bars to include.

    Returns:
        Range (max high - min low) over the window. Returns 0.0 if insufficient data.
    """
    if len(df) < window:
        tail = df
    else:
        tail = df.tail(window)

    if tail.empty:
        return 0.0
    return float(tail["high"].max() - tail["low"].min())


def derive_session(as_of_utc: datetime) -> str:
    """Derive trading session context from UTC hour.

    Args:
        as_of_utc: UTC-aware datetime.

    Returns:
        Session label: 'asian', 'london', 'overlap', or 'new_york'.
    """
    hour = as_of_utc.hour
    for session, (start, end) in SESSION_WINDOWS.items():
        if start <= hour < end:
            return session
    return "asian"  # Outside all windows defaults to asian


def compute_core_features(
    df_1h: pd.DataFrame,
    as_of_utc: datetime | None = None,
) -> CoreFeatures:
    """Compute the full core feature set from 1h bars.

    Args:
        df_1h: 1-hour OHLCV DataFrame.
        as_of_utc: Packet timestamp for session derivation. Defaults to now.

    Returns:
        CoreFeatures dataclass with all fields populated.
    """
    if as_of_utc is None:
        as_of_utc = datetime.now(timezone.utc)

    atr_14 = compute_atr(df_1h, ATR_PERIOD)
    volatility_regime = compute_volatility_regime(df_1h)
    momentum = compute_momentum(df_1h, MOMENTUM_PERIOD)

    # Moving averages — graceful on insufficient data
    ma_50 = 0.0
    ma_200 = 0.0
    if len(df_1h) >= 50:
        ma_50 = float(df_1h["close"].rolling(50).mean().iloc[-1])
    if len(df_1h) >= 200:
        ma_200 = float(df_1h["close"].rolling(200).mean().iloc[-1])

    swing_high = compute_swing_high(df_1h)
    swing_low = compute_swing_low(df_1h)
    rolling_range = compute_rolling_range(df_1h)
    session_context = derive_session(as_of_utc)

    return CoreFeatures(
        atr_14=atr_14,
        volatility_regime=volatility_regime,
        momentum=momentum,
        ma_50=ma_50,
        ma_200=ma_200,
        swing_high=swing_high,
        swing_low=swing_low,
        rolling_range=rolling_range,
        session_context=session_context,
    )
