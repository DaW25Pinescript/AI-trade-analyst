"""
Phase 4 — Performance tests for the parallel pipeline and scheduler improvements.

Covers:
  - chart_setup_node returns only chart_analysis_runtime (partial state dict)
  - macro_context_node returns only macro_context (partial state dict)
  - MacroScheduler._refresh() uses ThreadPoolExecutor (parallel source fetches)
  - Pipeline parallel fan-out: both nodes run before chart_lenses
"""
from unittest.mock import patch, MagicMock





# ── chart_setup_node: partial state dict ─────────────────────────────────────

async def test_chart_setup_node_returns_only_chart_analysis_runtime(
    sample_ground_truth, sample_lens_config
):
    from ai_analyst.graph.chart_analysis_nodes import chart_setup_node
    state = {
        "ground_truth": sample_ground_truth,
        "lens_config": sample_lens_config,
        "chart_analysis_runtime": None,
    }
    result = await chart_setup_node(state)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"chart_analysis_runtime"}, (
        f"chart_setup_node must return only chart_analysis_runtime, got {set(result.keys())}"
    )


async def test_chart_setup_node_has_required_runtime_fields(
    sample_ground_truth, sample_lens_config
):
    from ai_analyst.graph.chart_analysis_nodes import chart_setup_node
    state = {"ground_truth": sample_ground_truth, "lens_config": sample_lens_config}
    result = await chart_setup_node(state)
    rt = result["chart_analysis_runtime"]
    assert rt["base_loaded"] is True
    assert rt["auto_detect_ran"] is True
    assert "selected_lenses" in rt


async def test_chart_setup_node_does_not_touch_macro_context(
    sample_ground_truth, sample_lens_config
):
    """chart_setup_node must not write macro_context — parallel merge safety."""
    from ai_analyst.graph.chart_analysis_nodes import chart_setup_node
    state = {"ground_truth": sample_ground_truth, "lens_config": sample_lens_config}
    result = await chart_setup_node(state)
    assert "macro_context" not in result


# ── macro_context_node: partial state dict ───────────────────────────────────

async def test_macro_context_node_returns_only_macro_context_key(
    sample_ground_truth, sample_lens_config
):
    from ai_analyst.graph import macro_context_node as module
    mock_scheduler = MagicMock()
    mock_scheduler.get_context.return_value = None
    state = {"ground_truth": sample_ground_truth, "lens_config": sample_lens_config, "macro_context": None}
    with patch.object(module, "_scheduler", mock_scheduler):
        result = await module.macro_context_node(state)
    assert set(result.keys()) == {"macro_context"}, (
        f"macro_context_node must return only macro_context, got {set(result.keys())}"
    )


async def test_macro_context_node_does_not_touch_chart_analysis_runtime(
    sample_ground_truth, sample_lens_config
):
    """macro_context_node must not write chart_analysis_runtime — parallel merge safety."""
    from ai_analyst.graph import macro_context_node as module
    mock_scheduler = MagicMock()
    mock_scheduler.get_context.return_value = None
    state = {"ground_truth": sample_ground_truth, "lens_config": sample_lens_config, "macro_context": None}
    with patch.object(module, "_scheduler", mock_scheduler):
        result = await module.macro_context_node(state)
    assert "chart_analysis_runtime" not in result


# ── MacroScheduler: parallel source fetches ──────────────────────────────────

def test_scheduler_refresh_uses_thread_pool_executor():
    import inspect
    from macro_risk_officer.ingestion.scheduler import MacroScheduler
    source = inspect.getsource(MacroScheduler._refresh)
    assert "ThreadPoolExecutor" in source, (
        "MacroScheduler._refresh must use ThreadPoolExecutor for parallel data-source fetches"
    )


def test_scheduler_refresh_uses_as_completed():
    import inspect
    from macro_risk_officer.ingestion.scheduler import MacroScheduler
    source = inspect.getsource(MacroScheduler._refresh)
    assert "as_completed" in source


def test_scheduler_all_three_sources_submitted():
    import inspect
    from macro_risk_officer.ingestion.scheduler import MacroScheduler
    source = inspect.getsource(MacroScheduler._refresh)
    for client in ("FinnhubClient", "FredClient", "GdeltClient"):
        assert client in source, f"Expected {client} in _refresh source"


def test_scheduler_all_sources_failing_returns_none():
    """If all data sources fail, get_context() returns None (never raises)."""
    from macro_risk_officer.ingestion.scheduler import MacroScheduler

    def always_raise(*a, **kw):
        raise RuntimeError("simulated outage")

    scheduler = MacroScheduler(ttl_seconds=0, enable_fetch_log=False)

    with patch("macro_risk_officer.ingestion.scheduler.FinnhubClient") as fh, \
         patch("macro_risk_officer.ingestion.scheduler.FredClient") as fr, \
         patch("macro_risk_officer.ingestion.scheduler.GdeltClient") as gd:
        fh.return_value.fetch_calendar.side_effect = always_raise
        fr.return_value.to_macro_events.side_effect = always_raise
        gd.return_value.fetch_geopolitical_events.side_effect = always_raise

        ctx = scheduler.get_context("XAUUSD")

    assert ctx is None, "All sources failing must return None gracefully"


# ── Pipeline topology ─────────────────────────────────────────────────────────

def test_pipeline_has_chart_setup_node_not_chart_base():
    from ai_analyst.graph.pipeline import build_analysis_graph
    graph = build_analysis_graph()
    assert "macro_context" in graph.nodes
    assert "chart_setup"   in graph.nodes
    assert "chart_lenses"  in graph.nodes
    assert "chart_base"        not in graph.nodes, "chart_base replaced by chart_setup"
    assert "chart_auto_detect" not in graph.nodes, "chart_auto_detect merged into chart_setup"


async def test_parallel_branches_both_complete_before_chart_lenses(
    monkeypatch, sample_ground_truth, sample_lens_config
):
    """Both macro_context and chart_setup must complete before chart_lenses runs."""
    from ai_analyst.graph.pipeline import build_analysis_graph

    completed = []

    async def fake_macro(state):
        completed.append("macro_context")
        return {"macro_context": None}

    async def fake_setup(state):
        completed.append("chart_setup")
        return {"chart_analysis_runtime": {"base_loaded": True, "auto_detect_ran": True, "selected_lenses": []}}

    async def fake_lenses(state):
        assert "macro_context" in completed, "macro_context must run before chart_lenses"
        assert "chart_setup"   in completed, "chart_setup must run before chart_lenses"
        state["analyst_outputs"] = []
        state["analyst_configs_used"] = []
        return state

    async def fake_arbiter(state):
        state["final_verdict"] = {"decision": "NO_TRADE"}
        return state

    async def noop(state): return state

    monkeypatch.setattr("ai_analyst.graph.pipeline.macro_context_node", fake_macro)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_setup_node",   fake_setup)
    monkeypatch.setattr("ai_analyst.graph.pipeline.chart_lenses_node",  fake_lenses)
    monkeypatch.setattr("ai_analyst.graph.pipeline.arbiter_node",       fake_arbiter)
    monkeypatch.setattr("ai_analyst.graph.pipeline.pinekraft_bridge_node", noop)
    monkeypatch.setattr("ai_analyst.graph.pipeline.logging_node",          noop)

    graph = build_analysis_graph()
    result = await graph.ainvoke({
        "ground_truth": sample_ground_truth,
        "lens_config": sample_lens_config,
        "analyst_outputs": [],
        "analyst_configs_used": [],
        "overlay_delta_reports": [],
        "macro_context": None,
        "final_verdict": None,
        "error": None,
    })

    assert result["final_verdict"]["decision"] == "NO_TRADE"
    assert set(completed) == {"macro_context", "chart_setup"}
