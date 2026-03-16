"""Market data OHLCV response models (PR-CHART-1).

Flat ResponseMeta & {} pattern — same as all prior endpoints.
Spec: docs/specs/PR_CHART_1_SPEC.md §6.2
"""

from __future__ import annotations

from pydantic import BaseModel

from ai_analyst.api.models.ops import ResponseMeta


class Candle(BaseModel):
    """Single OHLCV candle in lightweight-charts native format."""

    timestamp: int  # Unix epoch seconds
    open: float
    high: float
    low: float
    close: float
    volume: float


class OHLCVResponse(ResponseMeta):
    """GET /market-data/{instrument}/ohlcv response."""

    instrument: str
    timeframe: str
    candles: list[Candle]
    candle_count: int
