"""
LangGraph pipeline definition.

Graph flow (no overlay, no deliberation):
  validate_input → {macro_context ∥ chart_setup} → chart_lenses
  → run_arbiter → pinekraft_bridge (optional no-op) → log_and_emit → END

Graph flow (with 15M overlay, no deliberation):
  validate_input → {macro_context ∥ chart_setup} → chart_lenses
  → fan_out_overlay_delta → run_arbiter → pinekraft_bridge → log_and_emit → END

Graph flow (deliberation enabled, no overlay):
  validate_input → {macro_context ∥ chart_setup} → chart_lenses
  → deliberation → run_arbiter → pinekraft_bridge → log_and_emit → END

Graph flow (deliberation + overlay):
  validate_input → {macro_context ∥ chart_setup} → chart_lenses
  → deliberation → fan_out_overlay_delta → run_arbiter → pinekraft_bridge → log_and_emit → END

Phase 4 (performance): macro_context and chart_setup run in parallel after validate_input.
  - macro_context_node: network I/O call (TTL-cached scheduler); returns {"macro_context": ...}
  - chart_setup_node: pure CPU (lens resolution); returns {"chart_analysis_runtime": ...}
  Both nodes write to DIFFERENT state keys so LangGraph's fan-in merge is conflict-free.
  chart_lenses_node runs only after BOTH parallel branches have completed (fan-in).

macro_context is advisory-only and fails silently (sets macro_context=None) so macro
data outages never block the pipeline.

The conditional branch after chart_lenses checks enable_deliberation first, then
ground_truth.m15_overlay. The branch after deliberation checks only m15_overlay.
"""
import logging
from time import perf_counter

from langgraph.graph import StateGraph, END

from .state import GraphState
from .analyst_nodes import overlay_delta_node, deliberation_node
from .chart_analysis_nodes import (
    chart_setup_node,
    chart_lenses_node,
    pinekraft_bridge_node,
)
from .arbiter_node import arbiter_node
from .logging_node import logging_node
from .macro_context_node import macro_context_node
from ..core.correlation import correlation_ctx

logger = logging.getLogger(__name__)


async def validate_input_node(state: GraphState) -> GraphState:
    """
    Basic sanity checks on the Ground Truth Packet before the expensive fan-out.
    Raises ValueError if the packet is structurally incomplete.

    Phase 3: Sets the correlation context (run_id) and starts pipeline timing.
    """
    import os as _os
    _triage_debug = _os.getenv("TRIAGE_DEBUG", "").lower() == "true"
    logger.info("[validate_input_node] entered — state keys present: %s", sorted(state.keys()))
    if _triage_debug:
        logger.info("[validate_input_node] TRIAGE_DEBUG detail — ground_truth=%s, lens_config=%s",
                    state.get("ground_truth") is not None, state.get("lens_config") is not None)

    gt = state.get("ground_truth")
    if gt is None:
        raise ValueError("GraphState is missing 'ground_truth'.")
    if not gt.instrument:
        raise ValueError("GroundTruthPacket.instrument must not be empty.")
    if not gt.timeframes:
        raise ValueError("GroundTruthPacket.timeframes must not be empty.")
    if not gt.charts and not getattr(gt, "triage_mode", False):
        raise ValueError("GroundTruthPacket.charts must contain at least one clean price chart.")
    if len(gt.screenshot_metadata) != len(gt.charts):
        raise ValueError(
            "screenshot_metadata count must match charts count. "
            "Each clean chart requires typed evidence metadata."
        )
    if state.get("lens_config") is None:
        raise ValueError("GraphState is missing 'lens_config'.")

    # Phase 3: set correlation context and start pipeline timer
    correlation_ctx.set(gt.run_id)
    state["_pipeline_start_ts"] = perf_counter()
    state["_node_timings"] = {}
    logger.info("[Pipeline] Run started: instrument=%s session=%s run_id=%s",
                gt.instrument, gt.session, gt.run_id)

    return state


def _route_after_phase1(state: GraphState) -> str:
    """
    Conditional router: after Phase 1 clean analysis, decide next node.

    Priority:
    1. If enable_deliberation is True → run deliberation round first.
    2. Else if 15M overlay provided → run overlay delta analysis.
    3. Else → proceed directly to arbiter.
    """
    if state.get("enable_deliberation"):
        return "deliberation"
    if state["ground_truth"].m15_overlay:
        return "fan_out_overlay_delta"
    return "run_arbiter"


def _route_after_deliberation(state: GraphState) -> str:
    """
    Conditional router: after deliberation, route to overlay delta or directly to arbiter.
    """
    if state["ground_truth"].m15_overlay:
        return "fan_out_overlay_delta"
    return "run_arbiter"


def build_analysis_graph() -> StateGraph:
    """
    Compile and return the stateful LangGraph analysis pipeline.
    Call .invoke() or .ainvoke() on the returned graph with an initial GraphState.
    """
    graph = StateGraph(GraphState)

    graph.add_node("validate_input",        validate_input_node)
    graph.add_node("macro_context",         macro_context_node)
    graph.add_node("chart_setup",           chart_setup_node)    # Phase 4: combined base+auto_detect
    graph.add_node("chart_lenses",          chart_lenses_node)
    graph.add_node("deliberation",          deliberation_node)   # v2.1b
    graph.add_node("fan_out_overlay_delta", overlay_delta_node)
    graph.add_node("run_arbiter",           arbiter_node)
    graph.add_node("pinekraft_bridge",      pinekraft_bridge_node)
    graph.add_node("log_and_emit",          logging_node)

    graph.set_entry_point("validate_input")

    # Phase 4: parallel fan-out — macro_context_node and chart_setup_node run concurrently.
    # Each writes to a DIFFERENT state key (macro_context vs chart_analysis_runtime) so
    # LangGraph's fan-in merge at chart_lenses is conflict-free.
    graph.add_edge("validate_input",  "macro_context")   # branch 1: MRO I/O fetch
    graph.add_edge("validate_input",  "chart_setup")     # branch 2: lens resolution
    graph.add_edge("macro_context",   "chart_lenses")    # branch 1 fan-in
    graph.add_edge("chart_setup",     "chart_lenses")    # branch 2 fan-in

    # After Phase 1: deliberation (v2.1b) > overlay delta > arbiter
    graph.add_conditional_edges(
        "chart_lenses",
        _route_after_phase1,
        {
            "deliberation":          "deliberation",
            "fan_out_overlay_delta": "fan_out_overlay_delta",
            "run_arbiter":           "run_arbiter",
        },
    )

    # After deliberation: overlay delta (if provided) or directly to arbiter
    graph.add_conditional_edges(
        "deliberation",
        _route_after_deliberation,
        {
            "fan_out_overlay_delta": "fan_out_overlay_delta",
            "run_arbiter":           "run_arbiter",
        },
    )

    graph.add_edge("fan_out_overlay_delta", "run_arbiter")
    graph.add_edge("run_arbiter", "pinekraft_bridge")
    graph.add_edge("pinekraft_bridge", "log_and_emit")
    graph.add_edge("log_and_emit", END)

    return graph.compile()
