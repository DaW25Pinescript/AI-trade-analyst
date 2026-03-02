import pytest

from ai_analyst.graph.pipeline import build_analysis_graph


pytestmark = pytest.mark.asyncio


async def test_langgraph_pipeline_routes_direct_to_arbiter_without_overlay(
    monkeypatch,
    sample_ground_truth,
    sample_lens_config,
):
    calls: list[str] = []

    async def fake_macro_context_node(state):
        calls.append("macro_context")
        state["macro_context"] = None
        return state

    async def fake_base_node(state):
        calls.append("base")
        return state

    async def fake_auto_detect_node(state):
        calls.append("auto_detect")
        return state

    async def fake_lenses_node(state):
        calls.append("lenses")
        state["analyst_outputs"] = []
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
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_base_node", fake_base_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_auto_detect_node", fake_auto_detect_node)
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
            "overlay_delta_reports": [],
            "macro_context": None,
            "final_verdict": None,
            "error": None,
        }
    )

    assert calls == ["macro_context", "base", "auto_detect", "lenses", "arbiter", "pinekraft", "logging"]
    assert result["final_verdict"]["decision"] == "NO_TRADE"


async def test_langgraph_pipeline_runs_overlay_branch_when_overlay_present(
    monkeypatch,
    sample_ground_truth_with_overlay,
    sample_lens_config,
):
    calls: list[str] = []

    async def fake_macro_context_node(state):
        calls.append("macro_context")
        state["macro_context"] = None
        return state

    async def fake_base_node(state):
        calls.append("base")
        return state

    async def fake_auto_detect_node(state):
        calls.append("auto_detect")
        return state

    async def fake_lenses_node(state):
        calls.append("lenses")
        state["analyst_outputs"] = []
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
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_base_node", fake_base_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_auto_detect_node", fake_auto_detect_node)
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
            "overlay_delta_reports": [],
            "macro_context": None,
            "final_verdict": None,
            "error": None,
        }
    )

    assert calls == ["macro_context", "base", "auto_detect", "lenses", "overlay", "arbiter", "pinekraft", "logging"]


async def test_macro_context_none_does_not_block_pipeline(
    monkeypatch,
    sample_ground_truth,
    sample_lens_config,
):
    """Pipeline completes normally when macro_context is None throughout."""
    async def fake_macro_context_node(state):
        state["macro_context"] = None   # MRO unavailable
        return state

    async def fake_base_node(state):
        return state

    async def fake_auto_detect_node(state):
        return state

    async def fake_lenses_node(state):
        state["analyst_outputs"] = []
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
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_base_node", fake_base_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_auto_detect_node", fake_auto_detect_node)
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
            "overlay_delta_reports": [],
            "macro_context": None,
            "final_verdict": None,
            "error": None,
        }
    )

    assert result["final_verdict"]["decision"] == "NO_TRADE"
