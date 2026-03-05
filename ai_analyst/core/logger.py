import json
from pathlib import Path
from datetime import datetime, timezone
from ..models.ground_truth import GroundTruthPacket
from ..models.analyst_output import AnalystOutput
from ..models.arbiter_output import FinalVerdict
from .correlation import get_correlation_id

LOG_DIR = Path(__file__).parent.parent / "logs" / "runs"
PROMPT_VERSION = "v1.2"


def log_run(
    ground_truth: GroundTruthPacket,
    analyst_outputs: list[AnalystOutput],
    final_verdict: FinalVerdict,
) -> Path:
    """
    Write a full audit log entry for a completed run.
    Returns the path of the log file written.
    Every run is logged — no exceptions (design rule #8).

    Phase 3: includes correlation_id for end-to-end traceability.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": get_correlation_id() or ground_truth.run_id,
        "run_id": ground_truth.run_id,
        "instrument": ground_truth.instrument,
        "session": ground_truth.session,
        "prompt_version": PROMPT_VERSION,
        "ground_truth": ground_truth.model_dump(exclude={"charts"}),  # exclude raw image data
        "analyst_outputs": [a.model_dump() for a in analyst_outputs],
        "final_verdict": final_verdict.model_dump(),
    }

    log_path = LOG_DIR / f"{ground_truth.run_id}.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, default=str) + "\n")

    return log_path
