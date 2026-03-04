"""
FastAPI entry point for the Multi-Model Trade Analysis System.

Usage:
    uvicorn ai_analyst.api.main:app --reload

POST /analyse
    - Accepts chart images as multipart file uploads
    - Accepts market parameters as form fields
    - Runs the full LangGraph pipeline (two-phase when 15M overlay is provided)
    - Returns AnalysisResponse: { verdict, ticket_draft, run_id, source_ticket_id }

GET /health
    - Liveness check
"""
import base64
import collections
import json
import os
import time
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
    app.state.graph = build_analysis_graph()
    yield
    # Teardown (if needed in future) goes here


app = FastAPI(
    title="AI Trade Analyst — Multi-Model Pipeline",
    version="2.0.0",
    description=(
        "Deterministic, auditable multi-AI trade analysis. "
        "Multiple independent analyst models feed a single Arbiter verdict. "
        "Supports lens-aware screenshot handling: 3 clean price charts + "
        "optional 15M ICT overlay with isolated two-phase analysis. "
        "v2.0: POST /analyse returns an AnalysisResponse envelope including "
        "a ticket_draft block for direct browser app import."
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
    return {"status": "ok", "version": "2.0.0"}


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
    }

    try:
        final_state = await request.app.state.graph.ainvoke(initial_state)
    except RuntimeError as e:
        # Propagate pipeline failures (e.g. insufficient analysts) as 503
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal pipeline error. Check server logs.")

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
