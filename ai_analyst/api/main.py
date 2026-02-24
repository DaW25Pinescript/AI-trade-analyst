"""
FastAPI entry point for the Multi-Model Trade Analysis System.

Usage:
    uvicorn ai_analyst.api.main:app --reload

POST /analyse
    - Accepts chart images as multipart file uploads
    - Accepts market parameters as form fields
    - Runs the full LangGraph pipeline
    - Returns the FinalVerdict as JSON

GET /health
    - Liveness check
"""
import base64
import json
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..models.ground_truth import GroundTruthPacket, RiskConstraints, MarketContext
from ..models.lens_config import LensConfig
from ..models.arbiter_output import FinalVerdict
from ..graph.pipeline import build_analysis_graph
from ..graph.state import GraphState

app = FastAPI(
    title="AI Trade Analyst — Multi-Model Pipeline",
    version="1.1.0",
    description=(
        "Deterministic, auditable multi-AI trade analysis. "
        "Multiple independent analyst models feed a single Arbiter verdict."
    ),
)

_graph = build_analysis_graph()


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.1.0"}


@app.post("/analyse", response_model=FinalVerdict)
async def analyse(
    # Market identity
    instrument: str = Form(..., description="e.g. XAUUSD"),
    session: str = Form(..., description="e.g. NY, London, Asia"),
    timeframes: str = Form(..., description="JSON array, e.g. [\"D1\",\"H4\",\"H1\",\"M15\"]"),

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

    # Chart images — keyed by timeframe label
    chart_d1: Optional[UploadFile] = File(None),
    chart_h4: Optional[UploadFile] = File(None),
    chart_h1: Optional[UploadFile] = File(None),
    chart_m15: Optional[UploadFile] = File(None),
    chart_m5: Optional[UploadFile] = File(None),
):
    # Parse JSON fields
    try:
        tf_list: list[str] = json.loads(timeframes)
        no_trade_list: list[str] = json.loads(no_trade_windows)
        open_pos_list: list = json.loads(open_positions)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"JSON parse error in form field: {e}")

    # Build chart base64 map from uploaded files
    chart_uploads = {
        "D1": chart_d1,
        "H4": chart_h4,
        "H1": chart_h1,
        "M15": chart_m15,
        "M5": chart_m5,
    }
    charts: dict[str, str] = {}
    for label, upload in chart_uploads.items():
        if upload is not None:
            raw_bytes = await upload.read()
            charts[label] = base64.b64encode(raw_bytes).decode("utf-8")

    if not charts:
        raise HTTPException(status_code=422, detail="At least one chart image must be provided.")

    # Assemble Ground Truth Packet (immutable after creation)
    ground_truth = GroundTruthPacket(
        instrument=instrument,
        session=session,
        timeframes=tf_list,
        charts=charts,
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
    return JSONResponse(content=verdict.model_dump())
