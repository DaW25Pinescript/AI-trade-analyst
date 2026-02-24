from typing import TypedDict, Optional
from ..models.ground_truth import GroundTruthPacket
from ..models.lens_config import LensConfig
from ..models.analyst_output import AnalystOutput
from ..models.arbiter_output import FinalVerdict


class GraphState(TypedDict):
    ground_truth: GroundTruthPacket
    lens_config: LensConfig
    analyst_outputs: list[AnalystOutput]
    final_verdict: Optional[FinalVerdict]
    error: Optional[str]
