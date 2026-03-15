"""
FastAPI entry point for the Multi-Model Trade Analysis System.

Usage:
    uvicorn ai_analyst.api.main:app --reload

POST /analyse
    - Accepts chart images as multipart file uploads
    - Accepts market parameters as form fields
    - Runs the full LangGraph pipeline (two-phase when 15M overlay is provided)
    - Returns AnalysisResponse: { verdict, ticket_draft, run_id, source_ticket_id }
    - enable_deliberation=true (v2.1b): optional second analyst round before arbiter

POST /analyse/stream  (v2.2)
    - Same parameters as POST /analyse
    - Returns Server-Sent Events (SSE) stream as analysts complete
    - Emits analyst_done events per analyst, then a final verdict event

GET /health
    - Liveness check
"""
import asyncio
import base64
import collections
import json
import logging
import os
import time
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from ai_analyst.api.auth import verify_api_key
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


def _dev_diagnostics_enabled() -> bool:
    return (
        os.getenv("AI_ANALYST_DEV_DIAGNOSTICS", "").lower() == "true"
        or os.getenv("DEBUG", "").lower() == "true"
    )


_DEV_DIAGNOSTICS_FALLBACK_PATH = Path(__file__).resolve().parent.parent / "output" / "runs" / "_dev_diagnostics.jsonl"


class DevDiagnosticsTrace:
    """Collect dev-only request lifecycle events and persist structured diagnostics."""

    def __init__(self, request_id: str, path: str, method: str):
        self.request_id = request_id
        self.path = path
        self.method = method
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.events: list[dict] = []

    def stage(self, stage_name: str, **payload) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "request_id": self.request_id,
            "stage": stage_name,
            "payload": payload,
        }
        self.events.append(entry)
        logger.info("[dev-stage] request_id=%s stage=%s payload=%s", self.request_id, stage_name, payload)

    def persist(self, *, run_id: Optional[str], final_status: str, error_detail: Optional[str] = None) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": self.request_id,
            "run_id": run_id,
            "request": {"path": self.path, "method": self.method},
            "started_at": self.started_at,
            "final_status": final_status,
            "error_detail": error_detail,
            "events": self.events,
        }
        if run_id:
            out_path = get_run_dir(run_id) / "dev_diagnostics.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
            return

        _DEV_DIAGNOSTICS_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _DEV_DIAGNOSTICS_FALLBACK_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")

# ── Secret masking for log messages (audit #3 — CWE-209) ─────────────────
import re as _re

_SECRET_PATTERNS = _re.compile(
    r"(sk-[A-Za-z0-9]{8,})"           # OpenAI / Anthropic style keys
    r"|(key-[A-Za-z0-9]{8,})"         # generic key- prefixed tokens
    r"|(xai-[A-Za-z0-9]{8,})"         # Grok/xAI keys
    r"|(AIza[A-Za-z0-9_-]{30,})"      # Google API keys
    r"|([A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})"  # JWT-like tokens
    , _re.ASCII,
)


def _mask_secrets(text: str) -> str:
    """Replace API-key-like patterns in text with <REDACTED>."""
    return _SECRET_PATTERNS.sub("<REDACTED>", text)


_IMAGE_MAGIC = {
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"\xff\xd8\xff": "JPEG",
}


def _validate_image_magic(data: bytes, label: str) -> None:
    """Verify the file starts with a known image magic number (audit #8 — CWE-434)."""
    for magic, fmt in _IMAGE_MAGIC.items():
        if data[:len(magic)] == magic:
            return
    raise HTTPException(
        status_code=422,
        detail=(
            f"{label} is not a valid PNG or JPEG image. "
            "Upload a chart screenshot in PNG or JPEG format."
        ),
    )


async def _read_upload_bounded(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    """Read an upload in chunks, raising 413 as soon as the limit is exceeded.

    This avoids loading an arbitrarily large file into memory before
    rejecting it — the server stops reading at max_bytes + 1.
    Validates the file is a PNG or JPEG image via magic-number check.
    """
    chunks: list[bytes] = []
    total = 0
    chunk_size = 64 * 1024  # 64 KB
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"{label} exceeds the {max_bytes // (1024 * 1024)} MB "
                    "per-image size limit. Resize or compress the image before uploading."
                ),
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if data:
        _validate_image_magic(data, label)
    return data

from ..models.ground_truth import (
    GroundTruthPacket,
    RiskConstraints,
    MarketContext,
    ScreenshotMetadata,
    ALLOWED_CLEAN_TIMEFRAMES,
    OVERLAY_TIMEFRAME,
    OVERLAY_LENS,
    MAX_SCREENSHOTS,
)
from ..models.lens_config import LensConfig
from ..models.arbiter_output import FinalVerdict
from ..graph.pipeline import build_analysis_graph
from ..graph.state import GraphState
from ..output.ticket_draft import build_ticket_draft
from ..core.run_paths import get_run_dir
from ..core.usage_meter import summarize_usage, check_run_cost_ceiling
from ..core import progress_store
from ..core.correlation import correlation_ctx, setup_structured_logging
from ..core.pipeline_metrics import metrics_store
from ..core.input_sanitiser import (
    sanitise_instrument,
    sanitise_session,
    sanitise_market_regime,
    sanitise_news_risk,
    sanitise_no_trade_windows,
    sanitise_open_positions,
)


class AnalysisResponse(BaseModel):
    """
    v2.0 response envelope for POST /analyse.

    Wraps the full FinalVerdict alongside a partial ticket_draft dict that
    the browser app can use to pre-populate its ticket form, plus
    traceability fields linking this analysis run to an originating ticket.
    """

    verdict: FinalVerdict
    ticket_draft: dict
    run_id: str
    source_ticket_id: Optional[str] = None
    usage_summary: dict


class RunUsageResponse(BaseModel):
    """Response envelope for GET /runs/{run_id}/usage."""

    run_id: str
    usage_summary: dict


def _empty_usage_summary() -> dict:
    return {
        "total_calls": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "calls_by_stage": {},
        "calls_by_node": {},
        "calls_by_model": {},
        "calls_by_provider": {},
        "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "calls_with_token_usage": 0,
        "calls_without_token_usage": 0,
        "total_cost_usd": 0.0,
    }


def _load_usage_summary(run_id: str) -> dict:
    try:
        return summarize_usage(get_run_dir(run_id))
    except Exception:
        return _empty_usage_summary()


def _format_form_value(raw_value: str, max_chars: int = 200) -> str:
    """Return a bounded repr for client-facing validation errors."""
    preview = raw_value if len(raw_value) <= max_chars else f"{raw_value[:max_chars]}..."
    return repr(preview)


def _parse_json_form_field(
    field_name: str,
    raw_value: str,
    *,
    expect_array: bool = False,
    array_example: Optional[str] = None,
    request_id: Optional[str] = None,
):
    """Parse a JSON-backed form field and surface field-specific 422 details."""
    if _dev_diagnostics_enabled():
        logger.info("[dev-parse] request_id=%s field=%s raw=%s", request_id or "n/a", field_name, repr(raw_value))

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        expected_shape = f"JSON array like {array_example}" if expect_array and array_example else "valid JSON"
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    f"JSON parse error in form field '{field_name}': expected {expected_shape}; "
                    f"received {_format_form_value(raw_value)}"
                ),
                "field": field_name,
                "raw_value": _format_form_value(raw_value),
                "expected_shape": expected_shape,
                "parse_error": str(exc),
                "request_id": request_id,
            },
        )

    if expect_array and not isinstance(parsed, list):
        expected_shape = f"JSON array like {array_example}" if array_example else "JSON array"
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Field '{field_name}' must be a JSON array; received {_format_form_value(raw_value)}",
                "field": field_name,
                "raw_value": _format_form_value(raw_value),
                "expected_shape": expected_shape,
                "parse_error": None,
                "request_id": request_id,
            },
        )

    return parsed


def _parse_string_array_form_field(
    field_name: str,
    raw_value: str,
    *,
    array_example: Optional[str] = None,
    request_id: Optional[str] = None,
    allow_empty: bool = True,
) -> list[str]:
    """Parse string-array form fields from JSON array syntax or CSV fallback."""
    trimmed = raw_value.strip()
    mode = "json_array" if trimmed.startswith("[") else "csv_fallback"

    if _dev_diagnostics_enabled():
        logger.info(
            "[dev-parse] request_id=%s field=%s raw=%s mode=%s",
            request_id or "n/a",
            field_name,
            repr(raw_value),
            mode,
        )

    if mode == "json_array":
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            expected_shape = f"JSON array like {array_example}" if array_example else "JSON array"
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        f"JSON parse error in form field '{field_name}': expected {expected_shape}; "
                        f"received {_format_form_value(raw_value)}"
                    ),
                    "field": field_name,
                    "raw_value": _format_form_value(raw_value),
                    "expected_shape": expected_shape,
                    "parse_error": str(exc),
                    "request_id": request_id,
                },
            )
        if not isinstance(parsed, list):
            expected_shape = f"JSON array like {array_example}" if array_example else "JSON array"
            raise HTTPException(
                status_code=422,
                detail={
                    "message": f"Field '{field_name}' must be a JSON array; received {_format_form_value(raw_value)}",
                    "field": field_name,
                    "raw_value": _format_form_value(raw_value),
                    "expected_shape": expected_shape,
                    "parse_error": None,
                    "request_id": request_id,
                },
            )
        values = parsed
    else:
        values = [item.strip() for item in raw_value.split(",") if item.strip()]

    if not all(isinstance(item, str) and item.strip() for item in values):
        expected_shape = "array of non-empty strings"
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    f"Field '{field_name}' must be {expected_shape}; "
                    f"received {_format_form_value(raw_value)}"
                ),
                "field": field_name,
                "raw_value": _format_form_value(raw_value),
                "expected_shape": expected_shape,
                "parse_error": f"invalid item types from mode {mode}",
                "request_id": request_id,
            },
        )

    normalized = [item.strip() for item in values]
    if not allow_empty and not normalized:
        expected_shape = "non-empty array of strings"
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    f"Field '{field_name}' must be {expected_shape}; "
                    f"received {_format_form_value(raw_value)}"
                ),
                "field": field_name,
                "raw_value": _format_form_value(raw_value),
                "expected_shape": expected_shape,
                "parse_error": f"empty array from mode {mode}",
                "request_id": request_id,
            },
        )

    if _dev_diagnostics_enabled() and mode == "csv_fallback":
        logger.info(
            "[dev-parse] request_id=%s field=%s raw=%s mode=%s parsed=%s",
            request_id or "n/a",
            field_name,
            repr(raw_value),
            mode,
            normalized,
        )

    return normalized


# ── Budget guards ────────────────────────────────────────────────────────────
# MAX_IMAGE_SIZE_MB: per-image upload ceiling (default 5 MB).
# MAX_COST_PER_RUN_USD: optional per-run cost ceiling (default disabled).
_MAX_IMAGE_BYTES: int = int(os.environ.get("MAX_IMAGE_SIZE_MB", "5")) * 1024 * 1024
GRAPH_TIMEOUT_SECONDS: float = float(os.environ.get("GRAPH_TIMEOUT_SECONDS", "120"))
_MAX_COST_PER_RUN: float | None = (
    float(os.environ["MAX_COST_PER_RUN_USD"])
    if os.environ.get("MAX_COST_PER_RUN_USD")
    else None
)

# ── Rate limiter (HIGH-7) ────────────────────────────────────────────────────
# Simple in-process sliding-window rate limiter. Default: 10 requests per 60 s
# per client IP. Override with RATE_LIMIT_REQUESTS and RATE_LIMIT_WINDOW_S env vars.
_RATE_LIMIT_REQUESTS: int = int(os.environ.get("RATE_LIMIT_REQUESTS", "10"))
_RATE_LIMIT_WINDOW_S: int = int(os.environ.get("RATE_LIMIT_WINDOW_S", "60"))
_rate_windows: dict[str, collections.deque] = {}
_rate_lock = threading.Lock()


def _check_rate_limit(client_ip: str) -> None:
    """
    Sliding-window rate limiter. Raises HTTPException(429) when the client
    has exceeded RATE_LIMIT_REQUESTS requests within the last RATE_LIMIT_WINDOW_S
    seconds. Thread-safe via a shared lock.
    """
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_S
    with _rate_lock:
        window = _rate_windows.setdefault(client_ip, collections.deque())
        # Evict timestamps older than the sliding window
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= _RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: {_RATE_LIMIT_REQUESTS} requests "
                    f"per {_RATE_LIMIT_WINDOW_S}s. Retry after the window expires."
                ),
            )
        window.append(now)


# ── Application lifespan (HIGH-8) ────────────────────────────────────────────
# Build the LangGraph pipeline during startup rather than at module import time.
# This is safe across uvicorn worker restarts and avoids holding references to
# async event loops or per-process MRO cache at import time.


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 3: structured logging with correlation IDs
    setup_structured_logging()
    app.state.graph = build_analysis_graph()
    # Phase 2a: shared feeder state — latest ingested feeder payload + MacroContext
    app.state.feeder_context = None          # Optional[MacroContext]
    app.state.feeder_payload_meta = None     # dict with generated_at, source_health, etc.
    app.state.feeder_ingested_at = None      # datetime when last payload was ingested
    yield
    # Teardown (if needed in future) goes here


app = FastAPI(
    title="AI Trade Analyst — Multi-Model Pipeline",
    version="2.3.0",
    description=(
        "Deterministic, auditable multi-AI trade analysis. "
        "Multiple independent analyst models feed a single Arbiter verdict. "
        "Supports lens-aware screenshot handling: 3 clean price charts + "
        "optional 15M ICT overlay with isolated two-phase analysis. "
        "v2.0: POST /analyse returns an AnalysisResponse envelope including "
        "a ticket_draft block for direct browser app import. "
        "v2.1b: enable_deliberation=true triggers an optional second analyst round "
        "where peers review each other's blinded Round 1 outputs before the arbiter. "
        "v2.2: POST /analyse/stream returns SSE events as each analyst completes. "
        "v2.3: GET /metrics + /dashboard for operator monitoring and observability."
    ),
    lifespan=lifespan,
)

# ── CORS configuration (audit #4 — HTTPS enforcement) ────────────────────
# Override ALLOWED_ORIGINS (comma-separated) for non-localhost deployments.
# Defaults to localhost:8080 / 127.0.0.1:8080 for local development.
_default_origins = ["http://localhost:8080", "http://127.0.0.1:8080"]
_env_origins = os.environ.get("ALLOWED_ORIGINS", "")
_allow_origins = [o.strip() for o in _env_origins.split(",") if o.strip()] or _default_origins

_is_production = os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod")

if not _env_origins:
    logger.warning(
        "ALLOWED_ORIGINS not set — using localhost defaults. "
        "Set ALLOWED_ORIGINS in .env for production deployments."
    )

if _is_production:
    _insecure = [o for o in _allow_origins if o.startswith("http://")]
    if _insecure:
        logger.error(
            "SECURITY: ALLOWED_ORIGINS contains http:// origins in production: %s. "
            "Only https:// origins are permitted. Removing insecure origins.",
            _insecure,
        )
        _allow_origins = [o for o in _allow_origins if not o.startswith("http://")]
        if not _allow_origins:
            logger.error(
                "SECURITY: No valid https:// origins remain. "
                "API will reject all cross-origin requests."
            )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)


# ── Security headers middleware (audit #12 — CWE-693) ─────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if _is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── Global request body-size limit ────────────────────────────────────────────
# Caps total request body (including multipart uploads) at MAX_REQUEST_BODY_MB.
# Per-image limits (_MAX_IMAGE_BYTES) are tighter but only apply after parsing.
MAX_REQUEST_BODY_BYTES: int = int(os.environ.get("MAX_REQUEST_BODY_MB", "10")) * 1024 * 1024


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds the configured cap."""

    async def dispatch(self, request: StarletteRequest, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large."},
            )
        return await call_next(request)


app.add_middleware(BodySizeLimitMiddleware)

# ── Journey router (V1.1) ────────────────────────────────────────────────────
from .routers.journey import router as journey_router

app.include_router(journey_router)

# ── Agent Operations router (PR-OPS-2) ──────────────────────────────────────
from .routers.ops import router as ops_router

app.include_router(ops_router)

# ── Run Browser router (PR-RUN-1) ────────────────────────────────────────
from .routers.runs import router as runs_router

app.include_router(runs_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.3.0"}


# ── Phase 2a: Feeder bridge endpoints ────────────────────────────────────────
# POST /feeder/ingest   — accepts a feeder contract JSON, validates it,
#                         produces a MacroContext, and caches it in app.state
#                         so subsequent /analyse calls use live macro data.
# GET  /feeder/health   — returns the last ingestion metadata + staleness.

_FEEDER_STALE_SECONDS: int = int(os.environ.get("FEEDER_STALE_SECONDS", "3600"))


class FeederIngestPayload(BaseModel):
    contract_version: str
    generated_at: str
    instrument_context: str = "XAUUSD"
    sources_queried: list[str] = Field(default_factory=list)
    status: str
    warnings: list = Field(default_factory=list)
    events: list
    source_health: dict = Field(default_factory=dict)


@app.post("/feeder/ingest")
async def feeder_ingest(request: Request):
    """
    Accept a feeder contract JSON payload, validate, and produce a MacroContext.

    The resulting MacroContext is cached in app.state so that subsequent
    /analyse calls can use the live feeder context instead of falling back
    to the TTL-cached MacroScheduler.

    Returns the MacroContext as JSON for immediate verification.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Request body must be valid JSON.")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Feeder payload must be a JSON object.")

    try:
        validated_payload = FeederIngestPayload.model_validate(payload)
    except ValidationError as ve:
        logger.warning(
            json.dumps({
                "event": "feeder.ingest.validation_failed",
                "top_level_category": "request_validation_failure",
                "event_code": "feeder_payload_schema_invalid",
                "error": str(ve)[:500],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        )
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid feeder payload schema.",
                "code": "FEEDER_PAYLOAD_INVALID",
            },
        )

    payload = validated_payload.model_dump()
    instrument = payload.get("instrument_context", "XAUUSD")

    try:
        from macro_risk_officer.ingestion.feeder_ingest import (
            ingest_feeder_payload,
            events_from_feeder,
        )

        context = await asyncio.to_thread(
            ingest_feeder_payload, payload, instrument
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Feeder validation error: {exc}")
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="macro_risk_officer package not available — feeder ingestion disabled.",
        )
    except Exception as exc:
        logger.warning("[Feeder] Ingestion failed: %s: %s", type(exc).__name__, _mask_secrets(str(exc)))
        raise HTTPException(status_code=500, detail="Feeder ingestion failed. Check server logs.")

    # Obs P2: detect staleness-to-fresh recovery
    prev_ingested_at = getattr(request.app.state, "feeder_ingested_at", None)
    was_stale = False
    if prev_ingested_at is not None:
        was_stale = (datetime.now(timezone.utc) - prev_ingested_at).total_seconds() > _FEEDER_STALE_SECONDS
    elif prev_ingested_at is None:
        was_stale = True  # first ingest = recovery from "no data"
    if was_stale:
        logger.info(
            json.dumps({
                "event": "feeder.staleness.recovered",
                "top_level_category": "recovery_after_prior_failure",
                "event_code": "feeder_staleness_recovered",
                "previous_ingested_at": prev_ingested_at.isoformat() if prev_ingested_at else None,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        )

    # Cache in app.state for macro_context_node to pick up
    request.app.state.feeder_context = context
    request.app.state.feeder_payload_meta = {
        "contract_version": payload.get("contract_version"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "warnings": payload.get("warnings", []),
        "source_health": payload.get("source_health", {}),
        "event_count": len(payload.get("events", [])),
        "instrument_context": instrument,
    }
    request.app.state.feeder_ingested_at = datetime.now(timezone.utc)

    logger.info(
        "[Feeder] Ingested: regime=%s vol_bias=%s confidence=%.0f%% events=%d",
        context.regime,
        context.vol_bias,
        context.confidence * 100,
        len(payload.get("events", [])),
    )

    return JSONResponse(content={
        "status": "ok",
        "macro_context": context.model_dump(),
        "ingested_at": request.app.state.feeder_ingested_at.isoformat(),
    })


@app.get("/feeder/health")
async def feeder_health(request: Request):
    """
    Return the current feeder ingestion state.

    Reports whether a feeder payload has been ingested, when it was last
    ingested, whether it is stale, and the source health from the last payload.
    """
    ingested_at = getattr(request.app.state, "feeder_ingested_at", None)
    meta = getattr(request.app.state, "feeder_payload_meta", None)
    context = getattr(request.app.state, "feeder_context", None)

    if ingested_at is None or meta is None:
        return JSONResponse(content={
            "status": "no_data",
            "message": "No feeder payload has been ingested yet.",
            "stale": True,
            "age_seconds": None,
            "source_health": {},
        })

    now = datetime.now(timezone.utc)
    age_seconds = (now - ingested_at).total_seconds()
    stale = age_seconds > _FEEDER_STALE_SECONDS

    return JSONResponse(content={
        "status": "stale" if stale else "fresh",
        "ingested_at": ingested_at.isoformat(),
        "age_seconds": round(age_seconds, 1),
        "stale": stale,
        "stale_threshold_seconds": _FEEDER_STALE_SECONDS,
        "source_health": meta.get("source_health", {}),
        "event_count": meta.get("event_count", 0),
        "contract_version": meta.get("contract_version"),
        "generated_at": meta.get("generated_at"),
        "regime": context.regime if context else None,
        "vol_bias": context.vol_bias if context else None,
        "confidence": context.confidence if context else None,
    })


@app.get("/runs/{run_id}/usage", response_model=RunUsageResponse)
async def get_run_usage(run_id: str):
    response = RunUsageResponse(run_id=run_id, usage_summary=_load_usage_summary(run_id))
    return JSONResponse(content=response.model_dump())


@app.post("/analyse", response_model=AnalysisResponse)
async def analyse(
    request: Request,
    _api_key: str = Depends(verify_api_key),

    # Market identity
    instrument: str = Form(..., description="e.g. XAUUSD"),
    session: str = Form(..., description="e.g. NY, London, Asia"),
    timeframes: str = Form(..., description="JSON array, e.g. [\"H4\",\"M15\",\"M5\"]"),

    # Account / risk
    account_balance: float = Form(...),
    min_rr: float = Form(2.0),
    max_risk_per_trade: float = Form(0.5),
    max_daily_risk: float = Form(2.0),
    no_trade_windows: str = Form('["FOMC","NFP"]', description="JSON array of window names"),

    # Market context
    market_regime: str = Form("unknown", description="trending | ranging | unknown"),
    news_risk: str = Form("none_noted"),
    open_positions: str = Form("[]", description="JSON array of open position descriptions"),

    # Lens config (defaults to ICT + Market Structure only)
    lens_ict_icc: bool = Form(True),
    lens_market_structure: bool = Form(True),
    lens_orderflow: bool = Form(False),
    lens_trendlines: bool = Form(False),
    lens_classical: bool = Form(False),
    lens_harmonic: bool = Form(False),
    lens_smt: bool = Form(False),
    lens_volume_profile: bool = Form(False),

    # ─── Clean price chart images (architecture: 3 slots, all price_only) ───
    # At least one is required. For best results provide all three.
    chart_h4: Optional[UploadFile] = File(None, description="4H clean price chart"),
    chart_h1: Optional[UploadFile] = File(None, description="1H clean price chart"),
    chart_m15: Optional[UploadFile] = File(None, description="15M clean price chart (mandatory for overlay)"),
    chart_m5: Optional[UploadFile] = File(None, description="5M clean price chart"),

    # ─── 15M ICT overlay (optional, bound to M15 only) ──────────────────────
    # When provided triggers two-phase analysis: clean baseline then delta.
    chart_m15_overlay: Optional[UploadFile] = File(
        None,
        description="15M ICT indicator overlay screenshot (optional). "
                    "Triggers isolated overlay delta analysis phase.",
    ),
    # ─── v2.0 traceability ───────────────────────────────────────────────────
    source_ticket_id: Optional[str] = Form(
        None,
        description="v2.0: Originating app ticket ID for traceability. "
                    "When supplied, echoed in the response and embedded in ticket_draft.",
    ),
    overlay_indicator_source: str = Form(
        "TradingView",
        description="Platform/script providing the ICT overlay (e.g. TradingView)",
    ),
    overlay_settings_locked: bool = Form(
        True,
        description="Confirms indicator settings are locked and consistent across sessions.",
    ),
    overlay_indicator_claims: str = Form(
        '["FVG","OrderBlock","SessionLiquidity"]',
        description="JSON array of construct types the overlay claims to identify.",
    ),
    # ─── v2.1b deliberation ──────────────────────────────────────────────────
    enable_deliberation: bool = Form(
        False,
        description=(
            "v2.1b: When true, runs an optional second analyst round (deliberation) "
            "before the arbiter. Each analyst reviews anonymized peer Round 1 outputs "
            "and may revise or reaffirm its analysis. Arbiter weights Round 2 at 1.5x Round 1."
        ),
    ),
    # ─── triage mode (chartless) ────────────────────────────────────────────
    triage_mode: bool = Form(
        False,
        description=(
            "When true, skips the chart-upload requirement and runs the pipeline "
            "without visual evidence. Used by POST /triage for headless batch runs."
        ),
    ),
    # ─── smoke mode (single-analyst, no quorum) ─────────────────────────────
    smoke_mode: bool = Form(
        False,
        description=(
            "When true, runs only the first analyst and bypasses quorum enforcement. "
            "Used by POST /triage/smoke for diagnostic probes."
        ),
    ),
):
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Run-ID") or str(uuid.uuid4())
    dev_trace = DevDiagnosticsTrace(request_id=request_id, path=request.url.path, method=request.method) if _dev_diagnostics_enabled() else None

    # ── Triage-path entry log ──────────────────────────────────────────────
    logger.info("[analyse] request_id=%s POST /analyse received — instrument=%s triage_mode=%s smoke_mode=%s ts=%s",
                request_id, instrument, triage_mode, smoke_mode, datetime.now(timezone.utc).isoformat())
    if dev_trace:
        dev_trace.stage("request_received", instrument=instrument, triage_mode=triage_mode, smoke_mode=smoke_mode)
        dev_trace.stage("auth_passed", endpoint="/analyse")

    # ── Rate limit check (HIGH-7) ────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # ── Parse JSON fields ────────────────────────────────────────────────────
    if dev_trace:
        dev_trace.stage("request_parsing_start")
    try:
        tf_list: list[str] = _parse_string_array_form_field(
            "timeframes", timeframes, array_example='["H4","M15","M5"]', request_id=request_id
        )
        no_trade_list: list[str] = _parse_string_array_form_field(
            "no_trade_windows", no_trade_windows, array_example='["NFP"]', request_id=request_id
        )
        open_pos_list: list[str] = _parse_string_array_form_field("open_positions", open_positions, request_id=request_id)
        overlay_claims_list: list[str] = _parse_string_array_form_field(
            "overlay_indicator_claims", overlay_indicator_claims, request_id=request_id
        )
        if dev_trace:
            dev_trace.stage("request_parsing_success")
    except HTTPException as exc:
        if dev_trace:
            dev_trace.stage("request_parsing_failure", error=exc.detail)
            dev_trace.persist(run_id=None, final_status="failed", error_detail=str(exc.detail))
        raise

    # ── Sanitise user inputs before they reach LLM prompts (audit #2) ─────
    try:
        instrument = sanitise_instrument(instrument)
        session = sanitise_session(session)
        market_regime = sanitise_market_regime(market_regime)
        news_risk = sanitise_news_risk(news_risk)
        no_trade_list = sanitise_no_trade_windows(no_trade_list)
        open_pos_list = sanitise_open_positions(open_pos_list)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Input validation error: {e}")

    # ── Build clean chart base64 map ─────────────────────────────────────────
    clean_chart_uploads: dict[str, Optional[UploadFile]] = {
        "H4": chart_h4,
        "H1": chart_h1,
        "M15": chart_m15,
        "M5":  chart_m5,
    }
    charts: dict[str, str] = {}
    screenshot_metadata: list[ScreenshotMetadata] = []

    for tf_label, upload in clean_chart_uploads.items():
        if upload is not None:
            raw_bytes = await _read_upload_bounded(
                upload, _MAX_IMAGE_BYTES, f"Chart {tf_label}"
            )
            charts[tf_label] = base64.b64encode(raw_bytes).decode("utf-8")
            screenshot_metadata.append(
                ScreenshotMetadata(
                    timeframe=tf_label,
                    lens="NONE",
                    evidence_type="price_only",
                )
            )

    if not charts and not triage_mode:
        raise HTTPException(
            status_code=422,
            detail=(
                "At least one clean price chart must be provided. "
                "Submit chart_h4, chart_h1, chart_m15, or chart_m5."
            ),
        )

    # ── Build overlay base64 and metadata ───────────────────────────────────
    m15_overlay_b64: Optional[str] = None
    m15_overlay_meta: Optional[ScreenshotMetadata] = None

    if chart_m15_overlay is not None:
        # Validate overlay claims list is not empty
        if not overlay_claims_list:
            raise HTTPException(
                status_code=422,
                detail="overlay_indicator_claims must not be empty when overlay is provided.",
            )
        raw_bytes = await _read_upload_bounded(
            chart_m15_overlay, _MAX_IMAGE_BYTES, "Overlay image"
        )
        m15_overlay_b64 = base64.b64encode(raw_bytes).decode("utf-8")
        m15_overlay_meta = ScreenshotMetadata(
            timeframe=OVERLAY_TIMEFRAME,
            lens=OVERLAY_LENS,
            evidence_type="indicator_overlay",
            indicator_claims=overlay_claims_list,
            indicator_source=overlay_indicator_source,
            settings_locked=overlay_settings_locked,
        )

    # ── Enforce 4-screenshot hard cap ───────────────────────────────────────
    total_screenshots = len(charts) + (1 if m15_overlay_b64 else 0)
    if total_screenshots > MAX_SCREENSHOTS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Maximum {MAX_SCREENSHOTS} screenshots per run "
                f"(3 clean + 1 overlay). Got {total_screenshots}."
            ),
        )

    # ── Assemble Ground Truth Packet (immutable after creation) ─────────────
    try:
        ground_truth = GroundTruthPacket(
            source_ticket_id=source_ticket_id or None,
            instrument=instrument,
            session=session,
            timeframes=tf_list,
            charts=charts,
            screenshot_metadata=screenshot_metadata,
            m15_overlay=m15_overlay_b64,
            m15_overlay_metadata=m15_overlay_meta,
            risk_constraints=RiskConstraints(
                min_rr=min_rr,
                max_risk_per_trade=max_risk_per_trade,
                max_daily_risk=max_daily_risk,
                no_trade_windows=no_trade_list,
            ),
            context=MarketContext(
                market_regime=market_regime,
                news_risk=news_risk,
                account_balance=account_balance,
                open_positions=open_pos_list,
            ),
            triage_mode=triage_mode,
        )
    except ValueError as e:
        if dev_trace:
            dev_trace.stage("request_parsing_failure", error=str(e))
            dev_trace.persist(run_id=None, final_status="failed", error_detail=f"Ground Truth Packet validation failed: {e}")
        raise HTTPException(status_code=422, detail={"message": f"Ground Truth Packet validation failed: {e}", "request_id": request_id})

    if dev_trace:
        dev_trace.stage("request_id_assigned", run_id=ground_truth.run_id)
        dev_trace.stage("graph_build_start")

    lens_config = LensConfig(
        ICT_ICC=lens_ict_icc,
        MarketStructure=lens_market_structure,
        OrderflowLite=lens_orderflow,
        Trendlines=lens_trendlines,
        ClassicalIndicators=lens_classical,
        Harmonic=lens_harmonic,
        SMT_Divergence=lens_smt,
        VolumeProfile=lens_volume_profile,
    )

    # Effective smoke mode: request param OR env var
    _smoke_mode = smoke_mode or os.getenv("TRIAGE_SMOKE_MODE", "").lower() == "true"
    logger.info("[analyse] smoke_mode: request_param=%s env_var=%s effective=%s",
                smoke_mode, os.getenv("TRIAGE_SMOKE_MODE", ""),  _smoke_mode)

    initial_state: GraphState = {
        "ground_truth": ground_truth,
        "lens_config": lens_config,
        "analyst_outputs": [],
        "analyst_configs_used": [],                    # populated by chart_lenses_node
        "overlay_delta_reports": [],
        "macro_context": None,      # populated by macro_context_node
        "final_verdict": None,
        "error": None,
        "enable_deliberation": enable_deliberation,   # v2.1b
        "deliberation_outputs": [],                   # v2.1b
        "smoke_mode": _smoke_mode,                    # single-analyst, quorum bypass
        # Phase 2a: inject live feeder context if available
        "_feeder_context": getattr(request.app.state, "feeder_context", None),
        "_feeder_ingested_at": getattr(request.app.state, "feeder_ingested_at", None),
        # Phase 3: timing fields (populated by validate_input_node)
        "_pipeline_start_ts": None,
        "_node_timings": None,
        # Debug — temporary analyst output persistence investigation
        "_debug_after_parallel": None,
        # Observability Phase 1 — run visibility accumulators
        "_stage_trace": [],
        "_analyst_results": [],
        "_arbiter_meta": None,
    }

    # Phase 3: set correlation context for structured logging
    ctx_token = correlation_ctx.set(ground_truth.run_id)
    try:
        if dev_trace:
            dev_trace.stage("graph_build_success")
            dev_trace.stage("analyst_fanout_start")
        final_state = await asyncio.wait_for(
            request.app.state.graph.ainvoke(initial_state),
            timeout=GRAPH_TIMEOUT_SECONDS,
        )
        if dev_trace:
            dev_trace.stage("analyst_fanout_complete", analyst_count=len(final_state.get("analyst_outputs", [])))
            dev_trace.stage("arbiter_success", has_verdict=bool(final_state.get("final_verdict")))
    except asyncio.TimeoutError:
        logger.error("Graph execution timed out after %.0fs for run_id=%s",
                      GRAPH_TIMEOUT_SECONDS, ground_truth.run_id)
        if dev_trace:
            dev_trace.stage("graph_build_failure", error="timeout")
            dev_trace.persist(run_id=ground_truth.run_id, final_status="failed", error_detail="Analysis timed out")
        raise HTTPException(status_code=504, detail={"message": "Analysis timed out. Please try again later.", "request_id": request_id, "run_id": ground_truth.run_id})
    except RuntimeError as e:
        if _smoke_mode:
            return JSONResponse(content={
                "smoke_error": _mask_secrets(str(e)),
                "run_id": ground_truth.run_id,
                "debug_analyst_counts": {
                    "after_parallel_analyst_node": 0,
                    "at_chart_lenses_entry": 0,
                    "at_arbiter_entry": 0,
                    "note": "pipeline raised RuntimeError before completion",
                },
            })
        # Propagate pipeline failures (e.g. insufficient analysts) as 503
        logger.error("Pipeline RuntimeError: %s", _mask_secrets(str(e)))
        if dev_trace:
            dev_trace.stage("graph_build_failure", error=_mask_secrets(str(e)))
            dev_trace.persist(run_id=ground_truth.run_id, final_status="failed", error_detail=_mask_secrets(str(e)))
        raise HTTPException(status_code=503, detail={"message": "Analysis failed. Check server logs.", "request_id": request_id, "run_id": ground_truth.run_id})
    except Exception as exc:
        if _smoke_mode:
            return JSONResponse(content={
                "smoke_error": {"error_type": type(exc).__name__, "message": _mask_secrets(str(exc))[:500]},
                "run_id": ground_truth.run_id,
                "debug_analyst_counts": {
                    "after_parallel_analyst_node": 0,
                    "at_chart_lenses_entry": 0,
                    "at_arbiter_entry": 0,
                    "note": f"pipeline raised {type(exc).__name__} before completion",
                },
            })
        logger.error("Pipeline error: %s: %s", type(exc).__name__, _mask_secrets(str(exc)))
        if dev_trace:
            dev_trace.stage("graph_build_failure", error=f"{type(exc).__name__}: {_mask_secrets(str(exc))}")
            dev_trace.persist(run_id=ground_truth.run_id, final_status="failed", error_detail=f"{type(exc).__name__}: {_mask_secrets(str(exc))}")
        raise HTTPException(status_code=500, detail={"message": "Internal pipeline error. Check server logs.", "request_id": request_id, "run_id": ground_truth.run_id})
    finally:
        correlation_ctx.reset(ctx_token)

    # Build debug_analyst_counts from final pipeline state
    _debug_counts = {
        "after_parallel_analyst_node": final_state.get("_debug_after_parallel", -1),
        "at_chart_lenses_entry": final_state.get("_debug_after_parallel", -1),  # same node
        "at_arbiter_entry": len(final_state.get("analyst_outputs", [])),
    }

    # Smoke mode: if _smoke_error was captured, return it instead of crashing
    if _smoke_mode and final_state.get("_smoke_error"):
        return JSONResponse(content={
            "smoke_error": final_state["_smoke_error"],
            "run_id": ground_truth.run_id,
            "debug_analyst_counts": _debug_counts,
        })

    verdict: FinalVerdict = final_state["final_verdict"]
    if dev_trace:
        dev_trace.stage("artifact_write_start", run_id=ground_truth.run_id)
    ticket_draft = build_ticket_draft(verdict, ground_truth)
    usage_summary = _load_usage_summary(ground_truth.run_id)

    # Budget guard: warn if per-run cost ceiling is configured and exceeded.
    if _MAX_COST_PER_RUN is not None:
        check_run_cost_ceiling(get_run_dir(ground_truth.run_id), _MAX_COST_PER_RUN)

    response = AnalysisResponse(
        verdict=verdict,
        ticket_draft=ticket_draft,
        run_id=ground_truth.run_id,
        source_ticket_id=ground_truth.source_ticket_id,
        usage_summary=usage_summary,
    )
    resp_data = response.model_dump()
    # Smoke mode: inject debug_analyst_counts into successful response too
    if _smoke_mode:
        resp_data["debug_analyst_counts"] = _debug_counts
    if dev_trace:
        dev_trace.stage("artifact_write_success", run_id=ground_truth.run_id)
        dev_trace.stage("request_complete", status="success")
        dev_trace.persist(run_id=ground_truth.run_id, final_status="success")
    return JSONResponse(content=resp_data)


# ── v2.2 SSE streaming endpoint ───────────────────────────────────────────────

@app.post("/analyse/stream")
async def analyse_stream(
    request: Request,
    _api_key: str = Depends(verify_api_key),

    # Market identity
    instrument: str = Form(..., description="e.g. XAUUSD"),
    session: str = Form(..., description="e.g. NY, London, Asia"),
    timeframes: str = Form(..., description="JSON array, e.g. [\"H4\",\"M15\",\"M5\"]"),

    # Account / risk
    account_balance: float = Form(...),
    min_rr: float = Form(2.0),
    max_risk_per_trade: float = Form(0.5),
    max_daily_risk: float = Form(2.0),
    no_trade_windows: str = Form('["FOMC","NFP"]', description="JSON array of window names"),

    # Market context
    market_regime: str = Form("unknown", description="trending | ranging | unknown"),
    news_risk: str = Form("none_noted"),
    open_positions: str = Form("[]", description="JSON array of open position descriptions"),

    # Lens config
    lens_ict_icc: bool = Form(True),
    lens_market_structure: bool = Form(True),
    lens_orderflow: bool = Form(False),
    lens_trendlines: bool = Form(False),
    lens_classical: bool = Form(False),
    lens_harmonic: bool = Form(False),
    lens_smt: bool = Form(False),
    lens_volume_profile: bool = Form(False),

    # Chart images
    chart_h4: Optional[UploadFile] = File(None),
    chart_h1: Optional[UploadFile] = File(None),
    chart_m15: Optional[UploadFile] = File(None),
    chart_m5: Optional[UploadFile] = File(None),
    chart_m15_overlay: Optional[UploadFile] = File(None),

    # v2.0 traceability
    source_ticket_id: Optional[str] = Form(None),
    overlay_indicator_source: str = Form("TradingView"),
    overlay_settings_locked: bool = Form(True),
    overlay_indicator_claims: str = Form('["FVG","OrderBlock","SessionLiquidity"]'),

    # v2.1b deliberation
    enable_deliberation: bool = Form(
        False,
        description="v2.1b: Run optional second analyst round before arbiter.",
    ),
):
    """
    v2.2 — Streaming analysis via Server-Sent Events (SSE).

    Emits a JSON event for each analyst as it completes (stage: phase1, phase2_overlay,
    or deliberation), then a final "verdict" event with the full FinalVerdict payload.

    Event format: data: <JSON>\\n\\n

    Event types:
      {"type": "analyst_done", "stage": "phase1", "persona": "...", "action": "...", "confidence": 0.0}
      {"type": "analyst_done", "stage": "deliberation", "persona": "...", ...}
      {"type": "analyst_done", "stage": "phase2_overlay", "persona": "...", "contradictions": 0}
      {"type": "heartbeat"}
      {"type": "verdict", "verdict": { ... FinalVerdict ... }}
      {"type": "error", "detail": "..."}
    """
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Run-ID") or str(uuid.uuid4())
    dev_trace = DevDiagnosticsTrace(request_id=request_id, path=request.url.path, method=request.method) if _dev_diagnostics_enabled() else None
    if dev_trace:
        dev_trace.stage("request_received", stream=True, instrument=instrument)
        dev_trace.stage("auth_passed", endpoint="/analyse/stream")

    # ── Rate limit check ─────────────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # ── Parse JSON fields ────────────────────────────────────────────────────
    if dev_trace:
        dev_trace.stage("request_parsing_start")
    tf_list: list[str] = _parse_string_array_form_field(
        "timeframes", timeframes, array_example='["H4","M15","M5"]', request_id=request_id
    )
    no_trade_list: list[str] = _parse_string_array_form_field(
        "no_trade_windows", no_trade_windows, array_example='["NFP"]', request_id=request_id
    )
    open_pos_list: list[str] = _parse_string_array_form_field("open_positions", open_positions, request_id=request_id)
    overlay_claims_list: list[str] = _parse_string_array_form_field(
        "overlay_indicator_claims", overlay_indicator_claims, request_id=request_id
    )
    if dev_trace:
        dev_trace.stage("request_parsing_success")

    # ── Sanitise user inputs before they reach LLM prompts (audit #2) ─────
    try:
        instrument = sanitise_instrument(instrument)
        session = sanitise_session(session)
        market_regime = sanitise_market_regime(market_regime)
        news_risk = sanitise_news_risk(news_risk)
        no_trade_list = sanitise_no_trade_windows(no_trade_list)
        open_pos_list = sanitise_open_positions(open_pos_list)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Input validation error: {e}")

    # ── Build clean chart base64 map ─────────────────────────────────────────
    clean_chart_uploads: dict[str, Optional[UploadFile]] = {
        "H4": chart_h4, "H1": chart_h1, "M15": chart_m15, "M5": chart_m5,
    }
    charts: dict[str, str] = {}
    screenshot_metadata: list[ScreenshotMetadata] = []

    for tf_label, upload in clean_chart_uploads.items():
        if upload is not None:
            raw_bytes = await _read_upload_bounded(
                upload, _MAX_IMAGE_BYTES, f"Chart {tf_label}"
            )
            charts[tf_label] = base64.b64encode(raw_bytes).decode("utf-8")
            screenshot_metadata.append(
                ScreenshotMetadata(timeframe=tf_label, lens="NONE", evidence_type="price_only")
            )

    if not charts:
        raise HTTPException(status_code=422, detail="At least one clean price chart must be provided.")

    # ── Build overlay base64 ─────────────────────────────────────────────────
    m15_overlay_b64: Optional[str] = None
    m15_overlay_meta: Optional[ScreenshotMetadata] = None

    if chart_m15_overlay is not None:
        if not overlay_claims_list:
            raise HTTPException(
                status_code=422,
                detail="overlay_indicator_claims must not be empty when overlay is provided.",
            )
        raw_bytes = await _read_upload_bounded(
            chart_m15_overlay, _MAX_IMAGE_BYTES, "Overlay image"
        )
        m15_overlay_b64 = base64.b64encode(raw_bytes).decode("utf-8")
        m15_overlay_meta = ScreenshotMetadata(
            timeframe=OVERLAY_TIMEFRAME,
            lens=OVERLAY_LENS,
            evidence_type="indicator_overlay",
            indicator_claims=overlay_claims_list,
            indicator_source=overlay_indicator_source,
            settings_locked=overlay_settings_locked,
        )

    total_screenshots = len(charts) + (1 if m15_overlay_b64 else 0)
    if total_screenshots > MAX_SCREENSHOTS:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {MAX_SCREENSHOTS} screenshots per run. Got {total_screenshots}.",
        )

    # ── Assemble Ground Truth Packet ─────────────────────────────────────────
    try:
        ground_truth = GroundTruthPacket(
            source_ticket_id=source_ticket_id or None,
            instrument=instrument,
            session=session,
            timeframes=tf_list,
            charts=charts,
            screenshot_metadata=screenshot_metadata,
            m15_overlay=m15_overlay_b64,
            m15_overlay_metadata=m15_overlay_meta,
            risk_constraints=RiskConstraints(
                min_rr=min_rr,
                max_risk_per_trade=max_risk_per_trade,
                max_daily_risk=max_daily_risk,
                no_trade_windows=no_trade_list,
            ),
            context=MarketContext(
                market_regime=market_regime,
                news_risk=news_risk,
                account_balance=account_balance,
                open_positions=open_pos_list,
            ),
        )
    except ValueError as e:
        if dev_trace:
            dev_trace.stage("request_parsing_failure", error=str(e))
            dev_trace.persist(run_id=None, final_status="failed", error_detail=f"Ground Truth Packet validation failed: {e}")
        raise HTTPException(status_code=422, detail={"message": f"Ground Truth Packet validation failed: {e}", "request_id": request_id})

    lens_config = LensConfig(
        ICT_ICC=lens_ict_icc,
        MarketStructure=lens_market_structure,
        OrderflowLite=lens_orderflow,
        Trendlines=lens_trendlines,
        ClassicalIndicators=lens_classical,
        Harmonic=lens_harmonic,
        SMT_Divergence=lens_smt,
        VolumeProfile=lens_volume_profile,
    )

    initial_state: GraphState = {
        "ground_truth": ground_truth,
        "lens_config": lens_config,
        "analyst_outputs": [],
        "analyst_configs_used": [],
        "overlay_delta_reports": [],
        "macro_context": None,
        "final_verdict": None,
        "error": None,
        "enable_deliberation": enable_deliberation,
        "deliberation_outputs": [],
        # Phase 2a: inject live feeder context if available
        "_feeder_context": getattr(request.app.state, "feeder_context", None),
        "_feeder_ingested_at": getattr(request.app.state, "feeder_ingested_at", None),
        # Phase 3: timing fields (populated by validate_input_node)
        "_pipeline_start_ts": None,
        "_node_timings": None,
        # Debug — temporary analyst output persistence investigation
        "_debug_after_parallel": None,
        # Observability Phase 1 — run visibility accumulators
        "_stage_trace": [],
        "_analyst_results": [],
        "_arbiter_meta": None,
    }

    # Phase 3: set correlation context for structured logging
    correlation_ctx.set(ground_truth.run_id)
    if dev_trace:
        dev_trace.stage("request_id_assigned", run_id=ground_truth.run_id)
        dev_trace.stage("graph_build_start")

    # ── Register progress queue and stream ───────────────────────────────────
    run_id = ground_truth.run_id
    queue = progress_store.register(run_id)

    async def event_stream():
        pipeline_task = asyncio.create_task(
            asyncio.wait_for(
                request.app.state.graph.ainvoke(initial_state),
                timeout=GRAPH_TIMEOUT_SECONDS,
            )
        )
        try:
            while True:
                # Drain available events; yield heartbeats while pipeline is running
                done = pipeline_task.done()
                try:
                    event = queue.get_nowait()
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.QueueEmpty:
                    if done:
                        break
                    # Yield a heartbeat to keep the connection alive
                    yield "data: {\"type\":\"heartbeat\"}\n\n"
                    await asyncio.sleep(0.2)

            # Pipeline complete — emit final verdict
            final_state = await pipeline_task
            verdict: FinalVerdict = final_state["final_verdict"]
            if dev_trace:
                dev_trace.stage("graph_build_success")
                dev_trace.stage("request_complete", status="success")
                dev_trace.persist(run_id=run_id, final_status="success")
            yield f"data: {json.dumps({'type': 'verdict', 'verdict': verdict.model_dump()})}\n\n"

            # Budget guard (non-blocking warning only)
            if _MAX_COST_PER_RUN is not None:
                check_run_cost_ceiling(get_run_dir(run_id), _MAX_COST_PER_RUN)

        except asyncio.TimeoutError:
            logger.error("Stream graph execution timed out after %.0fs for run_id=%s",
                          GRAPH_TIMEOUT_SECONDS, run_id)
            if dev_trace:
                dev_trace.stage("graph_build_failure", error="timeout")
                dev_trace.persist(run_id=run_id, final_status="failed", error_detail="Analysis timed out")
            yield f"data: {json.dumps({'type': 'error', 'detail': 'Analysis timed out. Please try again later.', 'request_id': request_id, 'run_id': run_id})}\n\n"
        except RuntimeError as exc:
            logger.error("Stream pipeline RuntimeError: %s", _mask_secrets(str(exc)))
            if dev_trace:
                dev_trace.stage("graph_build_failure", error=_mask_secrets(str(exc)))
                dev_trace.persist(run_id=run_id, final_status="failed", error_detail=_mask_secrets(str(exc)))
            yield f"data: {json.dumps({'type': 'error', 'detail': 'Analysis failed. Check server logs.', 'request_id': request_id, 'run_id': run_id})}\n\n"
        except Exception as exc:
            logger.error("Stream pipeline error: %s: %s", type(exc).__name__, _mask_secrets(str(exc)))
            yield "data: {\"type\":\"error\",\"detail\":\"Internal pipeline error\"}\n\n"
        finally:
            progress_store.unregister(run_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Phase 3: Monitoring & Observability endpoints ─────────────────────────────

@app.get("/metrics")
async def get_metrics(request: Request):
    """
    Phase 3 — Pipeline metrics endpoint.

    Returns aggregated metrics for all recorded pipeline runs including:
    cost, latency, analyst agreement, decision distribution, and recent runs.

    Obs P2: additively includes feeder_status for cross-lane visibility.
    """
    from dataclasses import asdict
    snapshot = metrics_store.snapshot()

    # Obs P2: additive feeder status
    feeder_ingested_at = getattr(request.app.state, "feeder_ingested_at", None)
    feeder_meta = getattr(request.app.state, "feeder_payload_meta", None)
    feeder_status: dict = {"status": "no_data", "age_seconds": None, "stale": True}
    if feeder_ingested_at is not None:
        age = (datetime.now(timezone.utc) - feeder_ingested_at).total_seconds()
        stale = age > _FEEDER_STALE_SECONDS
        feeder_status = {
            "status": "stale" if stale else "fresh",
            "age_seconds": round(age, 1),
            "stale": stale,
            "event_count": feeder_meta.get("event_count", 0) if feeder_meta else 0,
        }

    return JSONResponse(content={
        "status": "ok",
        "server_started_at": metrics_store.started_at,
        "metrics": asdict(snapshot),
        "feeder_status": feeder_status,
    })


@app.get("/dashboard")
async def operator_dashboard(request: Request):
    """
    Phase 3 — Operator health dashboard.

    Returns a self-contained HTML page showing pipeline health, cost tracking,
    and recent run summaries. Auto-refreshes every 30 seconds.
    """
    from dataclasses import asdict
    snapshot = metrics_store.snapshot()
    feeder_ingested_at = getattr(request.app.state, "feeder_ingested_at", None)
    feeder_meta = getattr(request.app.state, "feeder_payload_meta", None)
    feeder_context = getattr(request.app.state, "feeder_context", None)

    feeder_stale = True
    feeder_age = None
    if feeder_ingested_at is not None:
        age = (datetime.now(timezone.utc) - feeder_ingested_at).total_seconds()
        feeder_age = round(age, 1)
        feeder_stale = age > _FEEDER_STALE_SECONDS

    # Build recent runs table rows
    recent_rows = ""
    for run in reversed(snapshot.recent_runs):
        recent_rows += (
            f"<tr>"
            f"<td>{_esc(run.get('run_id', '')[:12])}...</td>"
            f"<td>{_esc(run.get('instrument', ''))}</td>"
            f"<td>{_esc(run.get('session', ''))}</td>"
            f"<td>{_esc(run.get('decision', ''))}</td>"
            f"<td>{run.get('analyst_agreement_pct', 0)}%</td>"
            f"<td>{run.get('overall_confidence', 0):.2f}</td>"
            f"<td>${run.get('llm_cost_usd', 0):.4f}</td>"
            f"<td>{run.get('total_latency_ms', 0):,}ms</td>"
            f"<td>{_esc(run.get('timestamp', '')[:19])}</td>"
            f"</tr>"
        )

    # Decision distribution
    decision_bars = ""
    total_runs = snapshot.total_runs or 1
    for dec, count in sorted(snapshot.decision_distribution.items(), key=lambda x: -x[1]):
        pct = round(count / total_runs * 100, 1)
        color = {"ENTER_LONG": "#22c55e", "ENTER_SHORT": "#ef4444", "NO_TRADE": "#6b7280"}.get(dec, "#3b82f6")
        decision_bars += (
            f'<div style="margin:4px 0">'
            f'<span style="display:inline-block;width:180px">{_esc(dec)}</span>'
            f'<span style="display:inline-block;width:40px;text-align:right">{count}</span>'
            f'<span style="display:inline-block;background:{color};height:16px;width:{pct*2}px;'
            f'margin-left:8px;border-radius:2px"></span>'
            f'<span style="margin-left:6px;color:#9ca3af">{pct}%</span>'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>AI Trade Analyst — Operator Dashboard</title>
<style>
  body {{ font-family: 'IBM Plex Mono', monospace; background: #0f172a; color: #e2e8f0; margin: 0; padding: 20px; }}
  h1 {{ color: #38bdf8; font-size: 1.4rem; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 16px; border: 1px solid #334155; }}
  .card .label {{ color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card .value {{ color: #f1f5f9; font-size: 1.5rem; font-weight: 700; margin-top: 4px; }}
  .card .sub {{ color: #64748b; font-size: 0.75rem; margin-top: 4px; }}
  .section {{ margin-bottom: 24px; }}
  .section h2 {{ color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
  th {{ text-align: left; color: #64748b; padding: 8px 12px; border-bottom: 1px solid #334155; font-weight: 500; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
  tr:hover {{ background: #1e293b; }}
  .status-ok {{ color: #22c55e; }} .status-warn {{ color: #f59e0b; }} .status-err {{ color: #ef4444; }}
  .feeder-bar {{ display: flex; gap: 16px; align-items: center; }}
</style>
</head>
<body>
<h1>AI Trade Analyst — Operator Dashboard</h1>
<div class="subtitle">Phase 3 Monitoring &amp; Observability | Server started {_esc(metrics_store.started_at[:19])} | Auto-refresh 30s</div>

<div class="grid">
  <div class="card">
    <div class="label">Total Runs</div>
    <div class="value">{snapshot.total_runs}</div>
    <div class="sub">{snapshot.runs_last_hour} last hour | {snapshot.runs_last_24h} last 24h</div>
  </div>
  <div class="card">
    <div class="label">Total LLM Cost</div>
    <div class="value">${snapshot.total_cost_usd:.4f}</div>
    <div class="sub">Avg ${snapshot.avg_cost_per_run_usd:.4f}/run</div>
  </div>
  <div class="card">
    <div class="label">Avg Latency</div>
    <div class="value">{snapshot.avg_latency_ms:,.0f}ms</div>
    <div class="sub">End-to-end pipeline</div>
  </div>
  <div class="card">
    <div class="label">Avg Agreement</div>
    <div class="value">{snapshot.avg_analyst_agreement_pct:.0f}%</div>
    <div class="sub">Analyst consensus</div>
  </div>
  <div class="card">
    <div class="label">Error Rate</div>
    <div class="value {'status-ok' if snapshot.error_rate < 0.05 else 'status-warn' if snapshot.error_rate < 0.2 else 'status-err'}">{snapshot.error_rate:.1%}</div>
    <div class="sub">LLM call failures</div>
  </div>
  <div class="card">
    <div class="label">Feeder Status</div>
    <div class="value {'status-ok' if not feeder_stale and feeder_age is not None else 'status-warn' if feeder_age is not None else 'status-err'}">{'Fresh' if not feeder_stale and feeder_age is not None else 'Stale' if feeder_age is not None else 'No Data'}</div>
    <div class="sub">{'Age: ' + str(feeder_age) + 's' if feeder_age is not None else 'No feeder payload ingested'}</div>
  </div>
</div>

<div class="section">
  <h2>Decision Distribution</h2>
  <div class="card">{decision_bars if decision_bars else '<span style="color:#64748b">No runs recorded yet.</span>'}</div>
</div>

<div class="section">
  <h2>Recent Runs (Last 10)</h2>
  <div style="overflow-x:auto">
  <table>
    <thead>
      <tr><th>Run ID</th><th>Instrument</th><th>Session</th><th>Decision</th><th>Agreement</th><th>Confidence</th><th>Cost</th><th>Latency</th><th>Time</th></tr>
    </thead>
    <tbody>{recent_rows if recent_rows else '<tr><td colspan="9" style="color:#64748b">No runs recorded yet.</td></tr>'}</tbody>
  </table>
  </div>
</div>

<div class="section">
  <h2>API Health</h2>
  <div class="card">
    <div class="feeder-bar">
      <span class="status-ok">Pipeline: OK</span>
      <span>| Version: 2.3.0</span>
      <span>| Last run: {_esc(snapshot.last_run_at[:19]) if snapshot.last_run_at else 'N/A'}</span>
    </div>
  </div>
</div>

</body>
</html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


def _esc(s: str) -> str:
    """Minimal HTML escaping for dashboard values."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ── Phase 5: Analytics CSV export endpoint ─────────────────────────────────

@app.get("/analytics/csv")
async def analytics_csv_export():
    """
    Phase 5 — Export all pipeline runs with verdicts and usage as a CSV download.

    Produces a CSV file containing one row per run with verdict details, usage
    metrics, and AAR data (if linked). Compatible with spreadsheet tools and
    external analytics platforms.
    """
    import csv as csv_mod
    import io

    from ..core.run_state_manager import list_all_runs

    runs = list_all_runs()

    fieldnames = [
        "run_id", "instrument", "session", "mode", "status", "created_at",
        "decision", "final_bias", "overall_confidence", "analyst_agreement_pct",
        "risk_override_applied", "setup_types", "avg_rr_estimate",
        "no_trade_conditions", "total_cost_usd", "total_llm_calls",
        "prompt_tokens", "completion_tokens",
        "aar_outcome", "aar_verdict", "aar_r_achieved", "aar_exit_reason",
        "aar_psychological_tag",
    ]

    output = io.StringIO()
    writer = csv_mod.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    from ..core.run_state_manager import OUTPUT_BASE

    AAR_BASE = OUTPUT_BASE.parent / "aars"

    for run_state in runs:
        run_dir = OUTPUT_BASE / run_state.run_id

        verdict_data: dict = {}
        verdict_path = run_dir / "final_verdict.json"
        if verdict_path.exists():
            try:
                verdict_data = json.loads(verdict_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        usage: dict = {}
        try:
            usage = summarize_usage(run_dir)
        except Exception:
            pass

        aar_data: dict = {}
        aar_path = AAR_BASE / run_state.run_id / "aar.json"
        if aar_path.exists():
            try:
                aar_data = json.loads(aar_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        setups = verdict_data.get("approved_setups", [])
        setup_types = "; ".join(s.get("type", "") for s in setups) if setups else ""
        avg_rr = ""
        if setups:
            rrs = [s.get("rr_estimate", 0) for s in setups if s.get("rr_estimate")]
            avg_rr = f"{sum(rrs) / len(rrs):.2f}" if rrs else ""

        writer.writerow({
            "run_id": run_state.run_id,
            "instrument": run_state.instrument,
            "session": run_state.session,
            "mode": run_state.mode,
            "status": run_state.status.value if hasattr(run_state.status, "value") else str(run_state.status),
            "created_at": run_state.created_at.isoformat(),
            "decision": verdict_data.get("decision", ""),
            "final_bias": verdict_data.get("final_bias", ""),
            "overall_confidence": verdict_data.get("overall_confidence", ""),
            "analyst_agreement_pct": verdict_data.get("analyst_agreement_pct", ""),
            "risk_override_applied": verdict_data.get("risk_override_applied", ""),
            "setup_types": setup_types,
            "avg_rr_estimate": avg_rr,
            "no_trade_conditions": "; ".join(verdict_data.get("no_trade_conditions", [])),
            "total_cost_usd": usage.get("total_cost_usd", 0.0),
            "total_llm_calls": usage.get("total_calls", 0),
            "prompt_tokens": usage.get("tokens", {}).get("prompt_tokens", 0),
            "completion_tokens": usage.get("tokens", {}).get("completion_tokens", 0),
            "aar_outcome": aar_data.get("outcomeEnum", ""),
            "aar_verdict": aar_data.get("verdictEnum", ""),
            "aar_r_achieved": aar_data.get("rAchieved", ""),
            "aar_exit_reason": aar_data.get("exitReasonEnum", ""),
            "aar_psychological_tag": aar_data.get("psychologicalTag", ""),
        })

    csv_content = output.getvalue()
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=analytics_export.csv"},
    )


# ── Phase 8a: Advanced Analytics Dashboard ─────────────────────────────────

@app.get("/analytics/dashboard")
async def analytics_dashboard():
    """
    Phase 8a — Advanced Analytics Dashboard.

    Returns a self-contained HTML page with Chart.js visualizations:
    regime accuracy, confidence calibration, persona heatmap, outcome trends,
    decision distribution, and instrument breakdown.
    """
    from ..core.analytics_dashboard import build_analytics_data, render_analytics_dashboard
    from fastapi.responses import HTMLResponse

    data = build_analytics_data()
    html = render_analytics_dashboard(data)
    return HTMLResponse(content=html)


# ── Phase 8b: Backtesting endpoint ─────────────────────────────────────────

@app.get("/backtest")
async def backtest_endpoint(
    instrument: Optional[str] = None,
    regime: Optional[str] = None,
    min_confidence: float = 0.0,
):
    """
    Phase 8b — Run a strategy backtest over historical outcomes.

    Query parameters:
        instrument: Filter by instrument (e.g. XAUUSD)
        regime: Filter by macro regime (e.g. risk_on, risk_off, neutral)
        min_confidence: Minimum arbiter confidence threshold (0.0-1.0)

    Returns JSON with strategy-level metrics (Sharpe, drawdown, win rate, etc.)
    """
    from ..core.backtester import run_backtest, BacktestConfig

    config = BacktestConfig(
        instrument_filter=instrument,
        regime_filter=regime,
        min_confidence=min_confidence,
    )
    report = run_backtest(config)
    return JSONResponse(content={"status": "ok", "backtest": report.to_dict()})


# ── Phase 8c: E2E validation endpoint ──────────────────────────────────────

@app.get("/e2e")
async def e2e_validation():
    """
    Phase 8c — Run end-to-end integration validation checks.

    Returns a structured report of all validation results.
    """
    from ..core.e2e_validator import run_e2e_validation
    from dataclasses import asdict

    report = run_e2e_validation()
    return JSONResponse(content={
        "status": "ok" if report.all_passed else "degraded",
        "total_checks": report.total_checks,
        "passed": report.passed,
        "failed": report.failed,
        "duration_ms": report.duration_ms,
        "checks": [asdict(c) for c in report.checks],
    })


# ── Phase 8d: Plugin registry endpoint ─────────────────────────────────────

@app.get("/plugins")
async def plugins_endpoint():
    """
    Phase 8d — List all registered plugins (personas, data sources, hooks).
    """
    from ..core.plugin_registry import registry
    from dataclasses import asdict

    registry.discover_builtins()
    registry.discover_plugins()

    return JSONResponse(content={
        "status": "ok",
        "total_plugins": registry.total_plugins,
        "personas": [
            {"name": p.name, "version": p.version, "description": p.description,
             "specialization": p.specialization, "enabled": p.enabled}
            for p in registry.list_personas()
        ],
        "data_sources": [
            {"name": s.name, "version": s.version, "description": s.description,
             "source_type": s.source_type, "enabled": s.enabled}
            for s in registry.list_data_sources()
        ],
        "hooks": [
            {"name": h.name, "version": h.version, "description": h.description,
             "events": [e.value for e in h.events], "enabled": h.enabled}
            for h in registry.list_hooks()
        ],
    })
