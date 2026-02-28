import pytest

from ai_analyst.graph.pipeline import build_analysis_graph


pytestmark = pytest.mark.asyncio


async def test_langgraph_pipeline_routes_direct_to_arbiter_without_overlay(
    monkeypatch,
    sample_ground_truth,
    sample_lens_config,
):
    calls: list[str] = []

    async def fake_parallel_node(state):
        calls.append("phase1")
        state["analyst_outputs"] = []
        return state

    async def fake_overlay_node(state):
        calls.append("overlay")
        return state

    async def fake_arbiter_node(state):
        calls.append("arbiter")
        state["final_verdict"] = {"decision": "NO_TRADE"}
        return state

    async def fake_logging_node(state):
        calls.append("logging")
        return state

    monkeypatch.setattr("ai_analyst.graph.pipeline.parallel_analyst_node", fake_parallel_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.overlay_delta_node", fake_overlay_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.arbiter_node", fake_arbiter_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.logging_node", fake_logging_node)

    graph = build_analysis_graph()
    result = await graph.ainvoke(
        {
            "ground_truth": sample_ground_truth,
            "lens_config": sample_lens_config,
            "analyst_outputs": [],
            "overlay_delta_reports": [],
            "final_verdict": None,
            "error": None,
        }
    )

    assert calls == ["phase1", "arbiter", "logging"]
    assert result["final_verdict"]["decision"] == "NO_TRADE"


async def test_langgraph_pipeline_runs_overlay_branch_when_overlay_present(
    monkeypatch,
    sample_ground_truth_with_overlay,
    sample_lens_config,
):
    calls: list[str] = []

    async def fake_parallel_node(state):
        calls.append("phase1")
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

    async def fake_logging_node(state):
        calls.append("logging")
        return state

    monkeypatch.setattr("ai_analyst.graph.pipeline.parallel_analyst_node", fake_parallel_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.overlay_delta_node", fake_overlay_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.arbiter_node", fake_arbiter_node)
    monkeypatch.setattr("ai_analyst.graph.pipeline.logging_node", fake_logging_node)

    graph = build_analysis_graph()
    await graph.ainvoke(
        {
            "ground_truth": sample_ground_truth_with_overlay,
            "lens_config": sample_lens_config,
            "analyst_outputs": [],
            "overlay_delta_reports": [],
            "final_verdict": None,
            "error": None,
        }
    )

    assert calls == ["phase1", "overlay", "arbiter", "logging"]
