"""
LangGraph pipeline definition.

Graph flow (no overlay):
  validate_input → chart_base → chart_auto_detect → chart_lenses
  → run_arbiter → pinekraft_bridge (optional no-op) → log_and_emit → END

Graph flow (with 15M overlay):
  validate_input → chart_base → chart_auto_detect → chart_lenses
  → fan_out_overlay_delta → run_arbiter → pinekraft_bridge → log_and_emit → END

The conditional branch is resolved after the chart-lenses stage, based on whether
ground_truth.m15_overlay is populated in the immutable Ground Truth Packet.
"""
from langgraph.graph import StateGraph, END

from .state import GraphState
from .analyst_nodes import overlay_delta_node
from .chart_analysis_nodes import (
    chart_base_node,
    chart_auto_detect_node,
    chart_lenses_node,
    pinekraft_bridge_node,
)
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

    graph.add_node("validate_input",        validate_input_node)
    graph.add_node("chart_base",            chart_base_node)
    graph.add_node("chart_auto_detect",     chart_auto_detect_node)
    graph.add_node("chart_lenses",          chart_lenses_node)
    graph.add_node("fan_out_overlay_delta", overlay_delta_node)
    graph.add_node("run_arbiter",           arbiter_node)
    graph.add_node("pinekraft_bridge",      pinekraft_bridge_node)
    graph.add_node("log_and_emit",          logging_node)

    graph.set_entry_point("validate_input")
    graph.add_edge("validate_input", "chart_base")
    graph.add_edge("chart_base", "chart_auto_detect")
    graph.add_edge("chart_auto_detect", "chart_lenses")

    # Conditional edge: overlay delta only when m15_overlay is present
    graph.add_conditional_edges(
        "chart_lenses",
        _route_after_phase1,
        {
            "fan_out_overlay_delta": "fan_out_overlay_delta",
            "run_arbiter": "run_arbiter",
        },
    )

    graph.add_edge("fan_out_overlay_delta", "run_arbiter")
    graph.add_edge("run_arbiter", "pinekraft_bridge")
    graph.add_edge("pinekraft_bridge", "log_and_emit")
    graph.add_edge("log_and_emit", END)

    return graph.compile()
