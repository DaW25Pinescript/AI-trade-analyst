"""
LangGraph pipeline definition.

Graph flow (no overlay):
  validate_input → fan_out_analysts → run_arbiter → log_and_emit → END

Graph flow (with 15M overlay):
  validate_input → fan_out_analysts → fan_out_overlay_delta → run_arbiter → log_and_emit → END

The conditional branch is resolved after Phase 1 completes, based on whether
ground_truth.m15_overlay is populated in the immutable Ground Truth Packet.
"""
from langgraph.graph import StateGraph, END

from .state import GraphState
from .analyst_nodes import parallel_analyst_node, overlay_delta_node
from .arbiter_node import arbiter_node
from .logging_node import logging_node


async def validate_input_node(state: GraphState) -> GraphState:
    """
    Basic sanity checks on the Ground Truth Packet before the expensive fan-out.
    Raises ValueError if the packet is structurally incomplete.
    """
    gt = state.get("ground_truth")
    if gt is None:
        raise ValueError("GraphState is missing 'ground_truth'.")
    if not gt.instrument:
        raise ValueError("GroundTruthPacket.instrument must not be empty.")
    if not gt.timeframes:
        raise ValueError("GroundTruthPacket.timeframes must not be empty.")
    if not gt.charts:
        raise ValueError("GroundTruthPacket.charts must contain at least one clean price chart.")
    if len(gt.screenshot_metadata) != len(gt.charts):
        raise ValueError(
            "screenshot_metadata count must match charts count. "
            "Each clean chart requires typed evidence metadata."
        )
    if state.get("lens_config") is None:
        raise ValueError("GraphState is missing 'lens_config'.")
    return state


def _route_after_phase1(state: GraphState) -> str:
    """
    Conditional router: after Phase 1 clean analysis, decide whether to run
    the Phase 2 overlay delta node or proceed directly to the arbiter.
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

    graph.add_node("validate_input",       validate_input_node)
    graph.add_node("fan_out_analysts",     parallel_analyst_node)
    graph.add_node("fan_out_overlay_delta", overlay_delta_node)
    graph.add_node("run_arbiter",          arbiter_node)
    graph.add_node("log_and_emit",         logging_node)

    graph.set_entry_point("validate_input")
    graph.add_edge("validate_input", "fan_out_analysts")

    # Conditional edge: overlay delta only when m15_overlay is present
    graph.add_conditional_edges(
        "fan_out_analysts",
        _route_after_phase1,
        {
            "fan_out_overlay_delta": "fan_out_overlay_delta",
            "run_arbiter": "run_arbiter",
        },
    )

    graph.add_edge("fan_out_overlay_delta", "run_arbiter")
    graph.add_edge("run_arbiter",           "log_and_emit")
    graph.add_edge("log_and_emit",          END)

    return graph.compile()
