"""Reflect endpoints router (PR-REFLECT-1)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from ai_analyst.api.models.ops import OpsError
from ai_analyst.api.services.reflect_aggregation import (
    ReflectScanError,
    get_pattern_summary,
    get_persona_performance,
)
from ai_analyst.api.services.reflect_bundle import RunBundleNotFound, get_run_bundle

logger = logging.getLogger(__name__)
router = APIRouter()


def _emit_obs_event(event: str, **fields: Any) -> None:
    fields["event"] = event
    if "ts" not in fields:
        fields["ts"] = datetime.now(timezone.utc).isoformat()
    try:
        logger.info(json.dumps(fields, default=str))
    except Exception:
        pass


def _ops_error(status_code: int, error: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=OpsError(error=error, message=message).model_dump(),
    )


def _validate_max_runs(max_runs: int) -> int:
    if max_runs < 10 or max_runs > 200:
        raise _ops_error(422, "INVALID_PARAMS", "max_runs must be between 10 and 200")
    return max_runs


@router.get("/reflect/persona-performance")
async def persona_performance(
    max_runs: int = Query(default=50),
    instrument: Optional[str] = Query(default=None),
    session: Optional[str] = Query(default=None),
):
    max_runs = _validate_max_runs(max_runs)
    try:
        response = get_persona_performance(
            max_runs=max_runs,
            instrument=instrument,
            session=session,
        )
        return JSONResponse(content=response.model_dump(by_alias=True))
    except ReflectScanError as exc:
        raise _ops_error(500, "REFLECT_SCAN_FAILED", str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise _ops_error(500, "REFLECT_SCAN_FAILED", f"Reflect scan error: {exc}")


@router.get("/reflect/pattern-summary")
async def pattern_summary(max_runs: int = Query(default=50)):
    max_runs = _validate_max_runs(max_runs)
    try:
        response = get_pattern_summary(max_runs=max_runs)
        return JSONResponse(content=response.model_dump(by_alias=True))
    except ReflectScanError as exc:
        raise _ops_error(500, "REFLECT_SCAN_FAILED", str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise _ops_error(500, "REFLECT_SCAN_FAILED", f"Reflect scan error: {exc}")


@router.get("/reflect/run/{run_id}")
async def reflect_run_bundle(run_id: str):
    try:
        response = get_run_bundle(run_id)
        return JSONResponse(content=response.model_dump(by_alias=True))
    except RunBundleNotFound as exc:
        raise _ops_error(404, "RUN_NOT_FOUND", str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise _ops_error(500, "REFLECT_SCAN_FAILED", f"Run bundle error: {exc}")
