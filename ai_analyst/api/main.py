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
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

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


# ── Budget guards ────────────────────────────────────────────────────────────
# MAX_IMAGE_SIZE_MB: per-image upload ceiling (default 5 MB).
# MAX_COST_PER_RUN_USD: optional per-run cost ceiling (default disabled).
_MAX_IMAGE_BYTES: int = int(os.environ.get("MAX_IMAGE_SIZE_MB", "5")) * 1024 * 1024
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

# Allow the browser app to reach the API.
# Override ALLOWED_ORIGINS (comma-separated) for non-localhost deployments.
# Defaults to localhost:8080 / 127.0.0.1:8080 for local development.
_default_origins = ["http://localhost:8080", "http://127.0.0.1:8080"]
_env_origins = os.environ.get("ALLOWED_ORIGINS", "")
_allow_origins = [o.strip() for o in _env_origins.split(",") if o.strip()] or _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.3.0"}


# ── Phase 2a: Feeder bridge endpoints ────────────────────────────────────────
# POST /feeder/ingest   — accepts a feeder contract JSON, validates it,
#                         produces a MacroContext, and caches it in app.state
#                         so subsequent /analyse calls use live macro data.
# GET  /feeder/health   — returns the last ingestion metadata + staleness.

_FEEDER_STALE_SECONDS: int = int(os.environ.get("FEEDER_STALE_SECONDS", "3600"))


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
        logger.warning("[Feeder] Ingestion failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail="Feeder ingestion failed. Check server logs.")

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
):
    # ── Rate limit check (HIGH-7) ────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # ── Parse JSON fields ────────────────────────────────────────────────────
    try:
        tf_list: list[str] = json.loads(timeframes)
        no_trade_list: list[str] = json.loads(no_trade_windows)
        open_pos_list: list = json.loads(open_positions)
        overlay_claims_list: list[str] = json.loads(overlay_indicator_claims)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"JSON parse error in form field: {e}")

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
            raw_bytes = await upload.read()
            if len(raw_bytes) > _MAX_IMAGE_BYTES:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Chart {tf_label} exceeds the {_MAX_IMAGE_BYTES // (1024 * 1024)} MB "
                        "per-image size limit. Resize or compress the image before uploading."
                    ),
                )
            charts[tf_label] = base64.b64encode(raw_bytes).decode("utf-8")
            screenshot_metadata.append(
                ScreenshotMetadata(
                    timeframe=tf_label,
                    lens="NONE",
                    evidence_type="price_only",
                )
            )

    if not charts:
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
        raw_bytes = await chart_m15_overlay.read()
        if len(raw_bytes) > _MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Overlay image exceeds the {_MAX_IMAGE_BYTES // (1024 * 1024)} MB "
                    "per-image size limit. Resize or compress the image before uploading."
                ),
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
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Ground Truth Packet validation failed: {e}")

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
        "overlay_delta_reports": [],
        "macro_context": None,      # populated by macro_context_node
        "final_verdict": None,
        "error": None,
        "enable_deliberation": enable_deliberation,   # v2.1b
        "deliberation_outputs": [],                   # v2.1b
        # Phase 2a: inject live feeder context if available
        "_feeder_context": getattr(request.app.state, "feeder_context", None),
        "_feeder_ingested_at": getattr(request.app.state, "feeder_ingested_at", None),
        # Phase 3: timing fields (populated by validate_input_node)
        "_pipeline_start_ts": None,
        "_node_timings": None,
    }

    # Phase 3: set correlation context for structured logging
    ctx_token = correlation_ctx.set(ground_truth.run_id)
    try:
        final_state = await request.app.state.graph.ainvoke(initial_state)
    except RuntimeError as e:
        # Propagate pipeline failures (e.g. insufficient analysts) as 503
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal pipeline error. Check server logs.")
    finally:
        correlation_ctx.reset(ctx_token)

    verdict: FinalVerdict = final_state["final_verdict"]
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
    return JSONResponse(content=response.model_dump())


# ── v2.2 SSE streaming endpoint ───────────────────────────────────────────────

@app.post("/analyse/stream")
async def analyse_stream(
    request: Request,

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
    # ── Rate limit check ─────────────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # ── Parse JSON fields ────────────────────────────────────────────────────
    try:
        tf_list: list[str] = json.loads(timeframes)
        no_trade_list: list[str] = json.loads(no_trade_windows)
        open_pos_list: list = json.loads(open_positions)
        overlay_claims_list: list[str] = json.loads(overlay_indicator_claims)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"JSON parse error in form field: {e}")

    # ── Build clean chart base64 map ─────────────────────────────────────────
    clean_chart_uploads: dict[str, Optional[UploadFile]] = {
        "H4": chart_h4, "H1": chart_h1, "M15": chart_m15, "M5": chart_m5,
    }
    charts: dict[str, str] = {}
    screenshot_metadata: list[ScreenshotMetadata] = []

    for tf_label, upload in clean_chart_uploads.items():
        if upload is not None:
            raw_bytes = await upload.read()
            if len(raw_bytes) > _MAX_IMAGE_BYTES:
                raise HTTPException(
                    status_code=422,
                    detail=f"Chart {tf_label} exceeds the {_MAX_IMAGE_BYTES // (1024*1024)} MB size limit.",
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
        raw_bytes = await chart_m15_overlay.read()
        if len(raw_bytes) > _MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=422,
                detail=f"Overlay image exceeds the {_MAX_IMAGE_BYTES // (1024*1024)} MB size limit.",
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
        raise HTTPException(status_code=422, detail=f"Ground Truth Packet validation failed: {e}")

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
    }

    # Phase 3: set correlation context for structured logging
    correlation_ctx.set(ground_truth.run_id)

    # ── Register progress queue and stream ───────────────────────────────────
    run_id = ground_truth.run_id
    queue = progress_store.register(run_id)

    async def event_stream():
        pipeline_task = asyncio.create_task(
            request.app.state.graph.ainvoke(initial_state)
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
            yield f"data: {json.dumps({'type': 'verdict', 'verdict': verdict.model_dump()})}\n\n"

            # Budget guard (non-blocking warning only)
            if _MAX_COST_PER_RUN is not None:
                check_run_cost_ceiling(get_run_dir(run_id), _MAX_COST_PER_RUN)

        except RuntimeError as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
        except Exception:
            yield "data: {\"type\":\"error\",\"detail\":\"Internal pipeline error\"}\n\n"
        finally:
            progress_store.unregister(run_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Phase 3: Monitoring & Observability endpoints ─────────────────────────────

@app.get("/metrics")
async def get_metrics():
    """
    Phase 3 — Pipeline metrics endpoint.

    Returns aggregated metrics for all recorded pipeline runs including:
    cost, latency, analyst agreement, decision distribution, and recent runs.
    """
    from dataclasses import asdict
    snapshot = metrics_store.snapshot()
    return JSONResponse(content={
        "status": "ok",
        "server_started_at": metrics_store.started_at,
        "metrics": asdict(snapshot),
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
