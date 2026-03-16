"""Market Data router — GET /market-data/{instrument}/ohlcv (PR-CHART-1).

Read-side market data surface. Serves stored OHLCV candle data from
MDO's hot package layer. No writes, no fetches, no scheduler.

Spec: docs/specs/PR_CHART_1_SPEC.md §6.2, §6.6
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Path, Query
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from ai_analyst.api.models.ops import OpsError
from ai_analyst.api.services.market_data_read import (
    InstrumentNotFound,
    MarketDataReadError,
    TimeframeNotFound,
    read_ohlcv,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _emit_obs_event(event: str, **fields: Any) -> None:
    """Emit a structured JSON observability event."""
    fields["event"] = event
    if "ts" not in fields:
        fields["ts"] = datetime.now(timezone.utc).isoformat()
    try:
        logger.info(json.dumps(fields, default=str))
    except Exception:
        pass


def _ops_error(status_code: int, error: str, message: str) -> HTTPException:
    """Build an HTTPException with OpsErrorEnvelope body."""
    return HTTPException(
        status_code=status_code,
        detail=OpsError(error=error, message=message).model_dump(),
    )


@router.get("/market-data/{instrument}/ohlcv")
async def get_ohlcv(
    instrument: str = Path(..., description="Instrument symbol (e.g. XAUUSD)"),
    timeframe: str = Query(default="4h", description="Candle timeframe"),
    limit: int = Query(default=100, description="Number of candles (1–500)"),
):
    """Return stored OHLCV candles for the given instrument and timeframe.

    Read-side projection — no writes, no fetches, no scheduler trigger.
    """
    # Validate limit
    if limit < 1 or limit > 500:
        raise _ops_error(
            422,
            "INVALID_PARAMS",
            f"limit must be between 1 and 500, got {limit}",
        )

    _emit_obs_event(
        "market_data.ohlcv.requested",
        instrument=instrument,
        timeframe=timeframe,
        limit=limit,
    )

    try:
        response = read_ohlcv(
            instrument=instrument,
            timeframe=timeframe,
            limit=limit,
        )
    except InstrumentNotFound:
        _emit_obs_event(
            "market_data.ohlcv.not_found",
            instrument=instrument,
            reason="instrument_not_found",
        )
        raise _ops_error(404, "INSTRUMENT_NOT_FOUND", f"Unknown instrument: {instrument}")
    except TimeframeNotFound:
        _emit_obs_event(
            "market_data.ohlcv.not_found",
            instrument=instrument,
            timeframe=timeframe,
            reason="timeframe_not_found",
        )
        raise _ops_error(
            404,
            "TIMEFRAME_NOT_FOUND",
            f"No data for {instrument} at timeframe {timeframe}",
        )
    except MarketDataReadError as exc:
        _emit_obs_event(
            "market_data.ohlcv.read_failed",
            instrument=instrument,
            timeframe=timeframe,
            error=str(exc),
        )
        raise _ops_error(500, "MARKET_DATA_READ_FAILED", str(exc))

    _emit_obs_event(
        "market_data.ohlcv.served",
        instrument=instrument,
        timeframe=timeframe,
        data_state=response.data_state,
        candle_count=response.candle_count,
    )

    return JSONResponse(content=response.model_dump(by_alias=True))
