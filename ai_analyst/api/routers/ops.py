"""Agent Operations router — read-only projection endpoints.

GET /ops/agent-roster          — Static architecture and roster truth (§4)
GET /ops/agent-health          — Current health snapshot (§5)
GET /runs/{run_id}/agent-trace — Run-level agent trace (§6, PR-OPS-4a)

Contract: docs/ui/AGENT_OPS_CONTRACT.md
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from ai_analyst.api.models.ops import OpsError
from ai_analyst.api.services.ops_roster import project_roster
from ai_analyst.api.services.ops_health import project_health
from ai_analyst.api.services.ops_trace import project_trace, TraceProjectionError

logger = logging.getLogger(__name__)

router = APIRouter()


def _emit_obs_event(event: str, **fields: Any) -> None:
    """Emit a structured JSON observability event (Obs P2)."""
    fields["event"] = event
    if "ts" not in fields:
        fields["ts"] = datetime.now(timezone.utc).isoformat()
    try:
        logger.info(json.dumps(fields, default=str))
    except Exception:
        pass


def _ops_error(status_code: int, error: str, message: str) -> HTTPException:
    """Build an HTTPException with OpsErrorEnvelope body (§2.3)."""
    return HTTPException(
        status_code=status_code,
        detail=OpsError(error=error, message=message).model_dump(),
    )


@router.get("/ops/agent-roster")
async def agent_roster():
    """Return the static agent roster hierarchy.

    Config-derived, not runtime-derived. Empty roster returns HTTP error.
    """
    _emit_obs_event("ops.roster.requested")
    try:
        response = project_roster()
    except RuntimeError as exc:
        _emit_obs_event("ops.roster.failed", error=str(exc))
        raise _ops_error(500, "ROSTER_UNAVAILABLE", str(exc))
    except Exception as exc:
        _emit_obs_event("ops.roster.failed", error=str(exc))
        raise _ops_error(
            503,
            "ROSTER_SERVICE_UNAVAILABLE",
            f"Roster service error: {exc}",
        )

    _emit_obs_event("ops.roster.served", data_state=response.data_state)
    return JSONResponse(
        content=response.model_dump(by_alias=True),
    )


@router.get("/ops/agent-health")
async def agent_health(request: Request):
    """Return the current health snapshot for all visible entities.

    Poll-based snapshot only — no SSE / WebSocket / live-push (§5.3).
    Empty entities array is valid on fresh start (§5.8).
    """
    _emit_obs_event("ops.health.requested")
    try:
        response = project_health(request.app.state)
    except Exception as exc:
        _emit_obs_event("ops.health.failed", error=str(exc))
        raise _ops_error(
            500,
            "HEALTH_PROJECTION_FAILED",
            f"Health projection error: {exc}",
        )

    _emit_obs_event(
        "ops.health.served",
        data_state=response.data_state,
        entity_count=len(response.entities),
    )
    return JSONResponse(
        content=response.model_dump(by_alias=True),
    )


@router.get("/runs/{run_id}/agent-trace")
async def agent_trace(run_id: str):
    """Return the run-level agent trace for a given run.

    Read-side projection from run_record.json + optional audit log (§6).
    """
    _emit_obs_event("ops.trace.requested", run_id=run_id)
    try:
        response = project_trace(run_id)
    except FileNotFoundError:
        _emit_obs_event("ops.trace.not_found", run_id=run_id)
        raise _ops_error(404, "RUN_NOT_FOUND", f"No run artifacts for run_id={run_id}")
    except TraceProjectionError as exc:
        _emit_obs_event("ops.trace.malformed", run_id=run_id, error=str(exc))
        raise _ops_error(422, "RUN_ARTIFACTS_MALFORMED", str(exc))
    except Exception as exc:
        _emit_obs_event("ops.trace.failed", run_id=run_id, error=str(exc))
        raise _ops_error(500, "TRACE_PROJECTION_FAILED", f"Trace projection error: {exc}")

    _emit_obs_event(
        "ops.trace.served",
        run_id=run_id,
        data_state=response.data_state,
        participant_count=len(response.participants),
    )
    return JSONResponse(
        content=response.model_dump(by_alias=True),
    )
