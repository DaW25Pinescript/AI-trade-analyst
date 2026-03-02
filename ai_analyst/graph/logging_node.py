"""
Logging node: writes the full audit trail for every run.
Executes after the Arbiter — no run exits the graph without a log entry.

MRO-P3: also records the MacroContext + verdict to the OutcomeTracker
SQLite database so the `python -m macro_risk_officer audit` command can
report regime distribution and confidence statistics over time.
"""
import logging

from ..core.logger import log_run
from .state import GraphState

logger = logging.getLogger(__name__)


async def logging_node(state: GraphState) -> GraphState:
    """
    Persist the full run record. Returns state unchanged so the graph can reach END.
    """
    ground_truth = state["ground_truth"]
    analyst_outputs = state.get("analyst_outputs", [])
    final_verdict = state.get("final_verdict")

    if final_verdict is None:
        logger.warning("logging_node called with no final_verdict in state")
        return state

    log_path = log_run(ground_truth, analyst_outputs, final_verdict)
    logger.info("Run %s logged to %s", ground_truth.run_id, log_path)

    # MRO-P3: record MacroContext snapshot to OutcomeTracker (fail-silent)
    macro_context = state.get("macro_context")
    if macro_context is not None:
        try:
            from macro_risk_officer.history.tracker import OutcomeTracker
            tracker = OutcomeTracker()
            tracker.record(
                context=macro_context,
                run_id=ground_truth.run_id,
                instrument=ground_truth.instrument,
                verdict=final_verdict,
            )
            logger.debug("MRO outcome recorded for run %s", ground_truth.run_id)
        except Exception as exc:
            logger.warning("MRO outcome recording failed (%s) — audit log unaffected.", exc)

    return state
