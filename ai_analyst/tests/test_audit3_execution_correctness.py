"""
test_audit3_execution_correctness.py — Audit 3: LLM Execution Correctness

Tests that lock the pipeline sequencing and mode behavior:
1. Deliberation routing: enable_deliberation=True → deliberation node runs
2. Deliberation + overlay: both deliberation and overlay run in correct order
3. Mode routing determinism: same inputs → same node sequence
4. Parallel branch invariants: macro_context and chart_setup both precede lenses
"""
import pytest

from ai_analyst.graph.pipeline import (
    build_analysis_graph,
    _route_after_phase1,
    _route_after_deliberation,
)
from ai_analyst.models.ground_truth import (
    GroundTruthPacket,
    MarketContext,
    RiskConstraints,
    ScreenshotMetadata,
)


pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_state(ground_truth, lens_config, enable_deliberation=False):
    """Build a minimal valid GraphState dict."""
    return {
        "ground_truth": ground_truth,
        "lens_config": lens_config,
        "analyst_outputs": [],
        "analyst_configs_used": [],
        "overlay_delta_reports": [],
        "macro_context": None,
        "final_verdict": None,
        "error": None,
        "enable_deliberation": enable_deliberation,
        "deliberation_outputs": [],
        "_feeder_context": None,
        "_feeder_ingested_at": None,
        "_pipeline_start_ts": None,
        "_node_timings": None,
    }


def _make_fakes(calls: list):
    """Return a dict of fake node functions that record call order."""

    async def fake_macro_context_node(state):
        calls.append("macro_context")
        return {"macro_context": None}

    async def fake_chart_setup_node(state):
        calls.append("chart_setup")
        return {
            "chart_analysis_runtime": {
                "base_loaded": True,
                "auto_detect_ran": True,
                "selected_lenses": [],
            }
        }

    async def fake_lenses_node(state):
        calls.append("lenses")
        state["analyst_outputs"] = []
        state["analyst_configs_used"] = []
        return state

    async def fake_deliberation_node(state):
        calls.append("deliberation")
        state["deliberation_outputs"] = []
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

    return {
        "ai_analyst.graph.pipeline.macro_context_node": fake_macro_context_node,
        "ai_analyst.graph.pipeline.chart_setup_node": fake_chart_setup_node,
        "ai_analyst.graph.pipeline.chart_lenses_node": fake_lenses_node,
        "ai_analyst.graph.pipeline.deliberation_node": fake_deliberation_node,
        "ai_analyst.graph.pipeline.overlay_delta_node": fake_overlay_node,
        "ai_analyst.graph.pipeline.arbiter_node": fake_arbiter_node,
        "ai_analyst.graph.pipeline.pinekraft_bridge_node": fake_pinekraft_node,
        "ai_analyst.graph.pipeline.logging_node": fake_logging_node,
    }


# ── 1. Routing function unit tests (pure, no graph needed) ──────────────────


def test_route_after_phase1_deliberation_priority(sample_ground_truth):
    """enable_deliberation=True takes priority over overlay."""
    state = _make_state(sample_ground_truth, None, enable_deliberation=True)
    assert _route_after_phase1(state) == "deliberation"


def test_route_after_phase1_overlay_without_deliberation(
    sample_ground_truth_with_overlay,
):
    """Overlay present but no deliberation → overlay delta."""
    state = _make_state(sample_ground_truth_with_overlay, None, enable_deliberation=False)
    assert _route_after_phase1(state) == "fan_out_overlay_delta"


def test_route_after_phase1_direct_to_arbiter(sample_ground_truth):
    """No deliberation, no overlay → straight to arbiter."""
    state = _make_state(sample_ground_truth, None, enable_deliberation=False)
    assert _route_after_phase1(state) == "run_arbiter"


def test_route_after_deliberation_with_overlay(sample_ground_truth_with_overlay):
    """After deliberation, overlay present → overlay delta."""
    state = _make_state(sample_ground_truth_with_overlay, None)
    assert _route_after_deliberation(state) == "fan_out_overlay_delta"


def test_route_after_deliberation_without_overlay(sample_ground_truth):
    """After deliberation, no overlay → arbiter."""
    state = _make_state(sample_ground_truth, None)
    assert _route_after_deliberation(state) == "run_arbiter"


# ── 2. Execution truth table: mode ↔ node sequence ──────────────────────────


async def test_mode_no_delib_no_overlay_sequence(
    monkeypatch, sample_ground_truth, sample_lens_config
):
    """Truth table row: delib=False, overlay=None → straight to arbiter."""
    calls = []
    for attr, fn in _make_fakes(calls).items():
        monkeypatch.setattr(attr, fn)

    graph = build_analysis_graph()
    state = _make_state(sample_ground_truth, sample_lens_config)
    await graph.ainvoke(state)

    # Verify macro_context and chart_setup both before lenses
    assert calls.index("macro_context") < calls.index("lenses")
    assert calls.index("chart_setup") < calls.index("lenses")
    # Verify deliberation and overlay did NOT run
    assert "deliberation" not in calls
    assert "overlay" not in calls
    # Verify sequential tail
    lenses_idx = calls.index("lenses")
    assert calls[lenses_idx:] == ["lenses", "arbiter", "pinekraft", "logging"]


async def test_mode_delib_enabled_no_overlay_sequence(
    monkeypatch, sample_ground_truth, sample_lens_config
):
    """Truth table row: delib=True, overlay=None → deliberation before arbiter."""
    calls = []
    for attr, fn in _make_fakes(calls).items():
        monkeypatch.setattr(attr, fn)

    graph = build_analysis_graph()
    state = _make_state(sample_ground_truth, sample_lens_config, enable_deliberation=True)
    await graph.ainvoke(state)

    assert "deliberation" in calls
    assert "overlay" not in calls
    lenses_idx = calls.index("lenses")
    assert calls[lenses_idx:] == [
        "lenses", "deliberation", "arbiter", "pinekraft", "logging"
    ]


async def test_mode_overlay_without_delib_sequence(
    monkeypatch, sample_ground_truth_with_overlay, sample_lens_config
):
    """Truth table row: delib=False, overlay=present → overlay before arbiter."""
    calls = []
    for attr, fn in _make_fakes(calls).items():
        monkeypatch.setattr(attr, fn)

    graph = build_analysis_graph()
    state = _make_state(sample_ground_truth_with_overlay, sample_lens_config)
    await graph.ainvoke(state)

    assert "deliberation" not in calls
    assert "overlay" in calls
    lenses_idx = calls.index("lenses")
    assert calls[lenses_idx:] == [
        "lenses", "overlay", "arbiter", "pinekraft", "logging"
    ]


async def test_mode_delib_plus_overlay_sequence(
    monkeypatch, sample_ground_truth_with_overlay, sample_lens_config
):
    """Truth table row: delib=True, overlay=present → deliberation → overlay → arbiter."""
    calls = []
    for attr, fn in _make_fakes(calls).items():
        monkeypatch.setattr(attr, fn)

    graph = build_analysis_graph()
    state = _make_state(
        sample_ground_truth_with_overlay, sample_lens_config, enable_deliberation=True
    )
    await graph.ainvoke(state)

    assert "deliberation" in calls
    assert "overlay" in calls
    lenses_idx = calls.index("lenses")
    assert calls[lenses_idx:] == [
        "lenses", "deliberation", "overlay", "arbiter", "pinekraft", "logging"
    ]


# ── 3. Determinism: same input → same route ─────────────────────────────────


async def test_determinism_same_input_same_sequence(
    monkeypatch, sample_ground_truth, sample_lens_config
):
    """Two invocations with identical input produce identical node sequences."""
    calls1, calls2 = [], []

    for attr, fn in _make_fakes(calls1).items():
        monkeypatch.setattr(attr, fn)
    graph = build_analysis_graph()
    await graph.ainvoke(_make_state(sample_ground_truth, sample_lens_config))

    for attr, fn in _make_fakes(calls2).items():
        monkeypatch.setattr(attr, fn)
    graph = build_analysis_graph()
    await graph.ainvoke(_make_state(sample_ground_truth, sample_lens_config))

    # Remove parallel nodes for deterministic comparison
    def sequential(c):
        return [n for n in c if n not in ("macro_context", "chart_setup")]

    assert sequential(calls1) == sequential(calls2)
