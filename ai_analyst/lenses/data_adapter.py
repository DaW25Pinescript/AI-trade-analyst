"""OHLCV data adapter — converts OHLCVResponse to lens input format.

Pure function. No validation. Empty candles → empty arrays.
Lenses own their own failure paths.
"""

import numpy as np

from ai_analyst.api.models.market_data import OHLCVResponse


def ohlcv_response_to_lens_input(response: OHLCVResponse) -> dict[str, np.ndarray]:
    """Convert OHLCVResponse to the dict[str, np.ndarray] shape lenses expect.

    Returns dict with 6 keys: timestamp, open, high, low, close, volume.
    Each value is a 1-D numpy float64 array (timestamps are float64 epoch seconds).
    """
    candles = response.candles
    if not candles:
        return {
            "timestamp": np.array([], dtype=np.float64),
            "open": np.array([], dtype=np.float64),
            "high": np.array([], dtype=np.float64),
            "low": np.array([], dtype=np.float64),
            "close": np.array([], dtype=np.float64),
            "volume": np.array([], dtype=np.float64),
        }

    return {
        "timestamp": np.array([c.timestamp for c in candles], dtype=np.float64),
        "open": np.array([c.open for c in candles], dtype=np.float64),
        "high": np.array([c.high for c in candles], dtype=np.float64),
        "low": np.array([c.low for c in candles], dtype=np.float64),
        "close": np.array([c.close for c in candles], dtype=np.float64),
        "volume": np.array([c.volume for c in candles], dtype=np.float64),
    }
