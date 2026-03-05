import pytest

from ai_analyst.graph.pipeline import build_analysis_graph


pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helper: check Phase 4 parallel-branch invariants.
#
# Phase 4 restructured the pipeline so that macro_context and chart_setup run
# in parallel after validate_input. The guaranteed invariants are:
#   1. Both "macro_context" and "chart_setup" appear before "lenses"
#   2. All nodes from "lenses" onward remain strictly sequential
#
# We no longer assert an exact prefix order because the relative position of
# "macro_context" vs "chart_setup" is non-deterministic (parallel).
# ---------------------------------------------------------------------------

def _assert_parallel_prefix_invariants(calls: list, post_lenses: list):
    """Check that parallel-branch ordering constraints are satisfied."""
    idx = calls.index
    # both pre-lenses nodes must appear before lenses
    for node in ("macro_context", "chart_setup"):
        assert idx(node) < idx("lenses"), f"Expected {node} before lenses in {calls}"
    # post-lenses sequence is deterministic
    lenses_pos = idx("lenses")
    assert calls[lenses_pos:] == post_lenses, (
        f"Expected sequential tail {post_lenses!r}, got {calls[lenses_pos:]!r}"
    )


async def test_langgraph_pipeline_routes_direct_to_arbiter_without_overlay(
    monkeypatch,
    sample_ground_truth,
    sample_lens_config,
):
    calls: list[str] = []

    async def fake_macro_context_node(state):
        calls.append("macro_context")
        return {"macro_context": None}

    async def fake_chart_setup_node(state):
        calls.append("chart_setup")
        return {"chart_analysis_runtime": {"base_loaded": True, "auto_detect_ran": True, "selected_lenses": []}}

    async def fake_lenses_node(state):
        calls.append("lenses")
        state["analyst_outputs"] = []
        state["analyst_configs_used"] = []
        return state

    async def fake_overlay_node(state):
        calls.append("overlay")
        return state

    async def fake_arbiter_node(state):
        calls.append("arbiter")
        state["final_verdict"] = {"decision": "NO_TRADE"}
        return state

    async def fake_pinekraft_node(state):
        calls.append("pinekraft")
        return state

    async def fake_logging_node(state):
        calls.append("logging")
        return state

    monkeypatch.setattr("ai_analyst.graph.pipeline.macro_context_node", fake_macro_context_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_setup_node", fake_chart_setup_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_lenses_node", fake_lenses_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.overlay_delta_node", fake_overlay_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.arbiter_node", fake_arbiter_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.pinekraft_bridge_node", fake_pinekraft_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.logging_node", fake_logging_node)

    graph = build_analysis_graph()
    result = await graph.ainvoke(
        {
            "ground_truth": sample_ground_truth,
            "lens_config": sample_lens_config,
            "analyst_outputs": [],
            "analyst_configs_used": [],
            "overlay_delta_reports": [],
            "macro_context": None,
            "final_verdict": None,
            "error": None,
        }
    )

    _assert_parallel_prefix_invariants(
        calls, post_lenses=["lenses", "arbiter", "pinekraft", "logging"]
    )
    assert result["final_verdict"]["decision"] == "NO_TRADE"


async def test_langgraph_pipeline_runs_overlay_branch_when_overlay_present(
    monkeypatch,
    sample_ground_truth_with_overlay,
    sample_lens_config,
):
    calls: list[str] = []

    async def fake_macro_context_node(state):
        calls.append("macro_context")
        return {"macro_context": None}

    async def fake_chart_setup_node(state):
        calls.append("chart_setup")
        return {"chart_analysis_runtime": {"base_loaded": True, "auto_detect_ran": True, "selected_lenses": []}}

    async def fake_lenses_node(state):
        calls.append("lenses")
        state["analyst_outputs"] = []
        state["analyst_configs_used"] = []
        return state

    async def fake_overlay_node(state):
        calls.append("overlay")
        state["overlay_delta_reports"] = [{"confirms": []}]
        return state

    async def fake_arbiter_node(state):
        calls.append("arbiter")
        state["final_verdict"] = {"decision": "NO_TRADE"}
        return state

    async def fake_pinekraft_node(state):
        calls.append("pinekraft")
        return state

    async def fake_logging_node(state):
        calls.append("logging")
        return state

    monkeypatch.setattr("ai_analyst.graph.pipeline.macro_context_node", fake_macro_context_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_setup_node", fake_chart_setup_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_lenses_node", fake_lenses_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.overlay_delta_node", fake_overlay_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.arbiter_node", fake_arbiter_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.pinekraft_bridge_node", fake_pinekraft_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.logging_node", fake_logging_node)

    graph = build_analysis_graph()
    await graph.ainvoke(
        {
            "ground_truth": sample_ground_truth_with_overlay,
            "lens_config": sample_lens_config,
            "analyst_outputs": [],
            "analyst_configs_used": [],
            "overlay_delta_reports": [],
            "macro_context": None,
            "final_verdict": None,
            "error": None,
        }
    )

    _assert_parallel_prefix_invariants(
        calls, post_lenses=["lenses", "overlay", "arbiter", "pinekraft", "logging"]
    )


async def test_macro_context_none_does_not_block_pipeline(
    monkeypatch,
    sample_ground_truth,
    sample_lens_config,
):
    """Pipeline completes normally when macro_context is None throughout."""
    async def fake_macro_context_node(state):
        return {"macro_context": None}   # MRO unavailable

    async def fake_chart_setup_node(state):
        return {"chart_analysis_runtime": {"base_loaded": True, "auto_detect_ran": True, "selected_lenses": []}}

    async def fake_lenses_node(state):
        state["analyst_outputs"] = []
        state["analyst_configs_used"] = []
        return state

    async def fake_arbiter_node(state):
        assert state.get("macro_context") is None  # arbiter must see None, not crash
        state["final_verdict"] = {"decision": "NO_TRADE"}
        return state

    async def fake_pinekraft_node(state):
        return state

    async def fake_logging_node(state):
        return state

    monkeypatch.setattr("ai_analyst.graph.pipeline.macro_context_node", fake_macro_context_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_setup_node", fake_chart_setup_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_lenses_node", fake_lenses_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.arbiter_node", fake_arbiter_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.pinekraft_bridge_node", fake_pinekraft_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.logging_node", fake_logging_node)

    graph = build_analysis_graph()
    result = await graph.ainvoke(
        {
            "ground_truth": sample_ground_truth,
            "lens_config": sample_lens_config,
            "analyst_outputs": [],
            "analyst_configs_used": [],
            "overlay_delta_reports": [],
            "macro_context": None,
            "final_verdict": None,
            "error": None,
        }
    )

    assert result["final_verdict"]["decision"] == "NO_TRADE"
