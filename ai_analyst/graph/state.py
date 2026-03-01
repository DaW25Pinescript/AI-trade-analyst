from typing import TypedDict, Optional
from ..models.ground_truth import GroundTruthPacket
from ..models.lens_config import LensConfig
from ..models.analyst_output import AnalystOutput, OverlayDeltaReport
from ..models.arbiter_output import FinalVerdict


class GraphState(TypedDict):
    ground_truth: GroundTruthPacket
    lens_config: LensConfig
    analyst_outputs: list[AnalystOutput]           # Phase 1 — clean price analysis outputs
    overlay_delta_reports: list[OverlayDeltaReport]  # Phase 2 — 15M overlay delta reports (empty if no overlay)
    chart_analysis_runtime: Optional[dict]
    final_verdict: Optional[FinalVerdict]
    error: Optional[str]
