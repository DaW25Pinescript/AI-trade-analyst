"""
Logging node: writes the full audit trail for every run.
Executes after the Arbiter — no run exits the graph without a log entry.
"""
from ..core.logger import log_run
from .state import GraphState


async def logging_node(state: GraphState) -> GraphState:
    """
    Persist the full run record. Returns state unchanged so the graph can reach END.
    """
    ground_truth = state["ground_truth"]
    analyst_outputs = state.get("analyst_outputs", [])
    final_verdict = state.get("final_verdict")

    if final_verdict is None:
        # Should not happen — arbiter_node always sets this or raises
        print("[WARN] logging_node called with no final_verdict in state")
        return state

    log_path = log_run(ground_truth, analyst_outputs, final_verdict)
    print(f"[INFO] Run {ground_truth.run_id} logged to {log_path}")
    return state
