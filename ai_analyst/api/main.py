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
import json
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
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
)

# Allow the browser app (localhost:8080) to reach the API (localhost:8000).
# Restricted to localhost origins only — tighten for production deployments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_graph = build_analysis_graph()


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/analyse", response_model=AnalysisResponse)
async def analyse(
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
        "final_verdict": None,
        "error": None,
    }

    try:
        final_state = await _graph.ainvoke(initial_state)
    except RuntimeError as e:
        # Propagate pipeline failures (e.g. insufficient analysts) as 503
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    verdict: FinalVerdict = final_state["final_verdict"]
    ticket_draft = build_ticket_draft(verdict, ground_truth)

    response = AnalysisResponse(
        verdict=verdict,
        ticket_draft=ticket_draft,
        run_id=ground_truth.run_id,
        source_ticket_id=ground_truth.source_ticket_id,
    )
    return JSONResponse(content=response.model_dump())
