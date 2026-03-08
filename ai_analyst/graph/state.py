from typing import TypedDict, Optional
from ..models.ground_truth import GroundTruthPacket
from ..models.lens_config import LensConfig
from ..models.analyst_output import AnalystOutput, OverlayDeltaReport
from ..models.arbiter_output import FinalVerdict

# Runtime import — LangGraph resolves TypedDict annotations via get_type_hints()
# at StateGraph construction time, so MacroContext must be importable at runtime.
from macro_risk_officer.core.models import MacroContext


class GraphState(TypedDict):
    ground_truth: GroundTruthPacket
    lens_config: LensConfig
    analyst_outputs: list[AnalystOutput]           # Phase 1 — clean price analysis outputs
    analyst_configs_used: list[dict]               # Phase 1 — configs that produced valid outputs (parallel to analyst_outputs)
    overlay_delta_reports: list[OverlayDeltaReport]  # Phase 2 — 15M overlay delta reports (empty if no overlay)
    chart_analysis_runtime: Optional[dict]
    macro_context: Optional[MacroContext]           # MRO Phase 2 — injected before chart analysis, advisory only
    final_verdict: Optional[FinalVerdict]
    error: Optional[str]
    # v2.1b — Multi-Round Deliberation
    enable_deliberation: bool                       # when True, run a second analyst round before arbiter
    deliberation_outputs: list[AnalystOutput]       # Round 2 peer-informed analyst outputs
    # Smoke mode — single-analyst, quorum bypass
    smoke_mode: bool                                # when True, run only first analyst and skip quorum
    # Phase 3 — Monitoring & Observability
    _pipeline_start_ts: Optional[float]             # perf_counter() at pipeline entry (for total latency)
    _node_timings: Optional[dict]                   # node_name → elapsed_ms
