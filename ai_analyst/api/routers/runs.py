"""Run Browser router — GET /runs/ endpoint (PR-RUN-1).

Top-level run-discovery surface. Serves a paginated, filterable index
of run summaries projected from run_record.json artifacts on disk.

Spec: docs/specs/PR_RUN_1_SPEC.md §6.1
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from ai_analyst.api.models.ops import OpsError
from ai_analyst.api.services.ops_run_browser import (
    RunScanError,
    project_run_browser,
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


@router.get("/runs/")
async def list_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    instrument: Optional[str] = Query(default=None),
    session: Optional[str] = Query(default=None),
):
    """Return paginated, filterable run browser index.

    Read-side projection — no writes, no mutations, no new storage.
    """
    _emit_obs_event(
        "runs.browser.requested",
        page=page,
        page_size=page_size,
        instrument=instrument,
        session=session,
    )

    try:
        response = project_run_browser(
            page=page,
            page_size=page_size,
            instrument=instrument,
            session=session,
        )
    except RunScanError as exc:
        _emit_obs_event("runs.browser.scan_failed", error=str(exc))
        raise _ops_error(500, "RUN_SCAN_FAILED", str(exc))
    except Exception as exc:
        _emit_obs_event("runs.browser.failed", error=str(exc))
        raise _ops_error(500, "RUN_SCAN_FAILED", f"Run browser error: {exc}")

    _emit_obs_event(
        "runs.browser.served",
        data_state=response.data_state,
        item_count=len(response.items),
        total=response.total,
    )
    return JSONResponse(
        content=response.model_dump(by_alias=True),
    )
