"""
MEDIUM-3: End-to-end pipeline integration test.

Unlike the topology tests in test_langgraph_async_integration.py (which
monkeypatch every node), this test runs the REAL node logic with only the
LLM API call (acompletion_metered) mocked. This exercises:

  validate_input → macro_context → chart_setup → chart_lenses
  → arbiter → pinekraft_bridge → logging → END

…with Pydantic schema validation, prompt building, and arbiter logic
all running for real.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from ai_analyst.graph.pipeline import build_analysis_graph
from ai_analyst.graph.state import GraphState
from ai_analyst.models.arbiter_output import FinalVerdict

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers: canned LLM responses that satisfy Pydantic schemas
# ---------------------------------------------------------------------------

_ANALYST_RESPONSE = json.dumps(
    {
        "htf_bias": "bullish",
        "structure_state": "continuation",
        "key_levels": {
            "premium": ["2040.00"],
            "discount": ["2020.00"],
        },
        "setup_valid": True,
        "setup_type": "BOS retest",
        "entry_model": "M15 FVG fill",
        "invalidation": "Below 2015.00",
        "disqualifiers": [],
        "sweep_status": "BSL swept",
        "fvg_zones": ["2025-2030"],
        "displacement_quality": "strong",
        "confidence": 0.78,
        "rr_estimate": 3.2,
        "notes": "Clean bullish continuation after BOS on H4.",
        "recommended_action": "LONG",
    }
)

_ARBITER_RESPONSE = json.dumps(
    {
        "final_bias": "bullish",
        "decision": "ENTER_LONG",
        "approved_setups": [
            {
                "type": "BOS retest",
                "entry_zone": "2025-2030 FVG",
                "stop": "2015.00",
                "targets": ["2040.00", "2050.00"],
                "rr_estimate": 3.2,
                "confidence": 0.75,
                "indicator_dependent": False,
            }
        ],
        "no_trade_conditions": [],
        "overall_confidence": 0.75,
        "analyst_agreement_pct": 100,
        "risk_override_applied": False,
        "arbiter_notes": "Full analyst consensus on bullish continuation.",
        "audit_log": {
            "run_id": "placeholder",
            "analysts_received": 4,
            "analysts_valid": 4,
            "htf_consensus": True,
            "setup_consensus": True,
            "risk_override": False,
        },
    }
)


def _make_mock_completion(content: str) -> SimpleNamespace:
    """Build a litellm-style ModelResponse stub."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ),
        model="mock-model",
    )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


async def test_full_pipeline_produces_valid_verdict(
    sample_ground_truth,
    sample_lens_config,
    tmp_path,
):
    """
    Run the full LangGraph pipeline with mocked LLM calls and verify a
    valid FinalVerdict is produced. Exercises real prompt building, Pydantic
    validation, and node logic end-to-end.
    """
    call_log: list[str] = []

    async def mock_acompletion_metered(*, stage, **kwargs):
        call_log.append(stage)
        if stage == "arbiter":
            return _make_mock_completion(_ARBITER_RESPONSE)
        return _make_mock_completion(_ANALYST_RESPONSE)

    initial_state: GraphState = {
        "ground_truth": sample_ground_truth,
        "lens_config": sample_lens_config,
        "analyst_outputs": [],
        "analyst_configs_used": [],
        "overlay_delta_reports": [],
        "chart_analysis_runtime": None,
        "macro_context": None,
        "final_verdict": None,
        "error": None,
        "enable_deliberation": False,
        "deliberation_outputs": [],
        "_pipeline_start_ts": None,
        "_node_timings": None,
        "_feeder_context": None,
        "_feeder_ingested_at": None,
    }

    with (
        patch(
            "ai_analyst.core.usage_meter.acompletion_metered",
            new=mock_acompletion_metered,
        ),
        patch(
            "ai_analyst.graph.analyst_nodes.acompletion_metered",
            new=mock_acompletion_metered,
        ),
        patch(
            "ai_analyst.graph.arbiter_node.acompletion_metered",
            new=mock_acompletion_metered,
        ),
        patch(
            "ai_analyst.graph.macro_context_node._get_scheduler",
            return_value=None,
        ),
        patch(
            "ai_analyst.core.logger.log_run",
            return_value=tmp_path / "run.jsonl",
        ),
        patch(
            "ai_analyst.graph.logging_node.summarize_usage",
            return_value={"total_calls": 5, "total_cost_usd": 0.01, "failed_calls": 0},
        ),
    ):
        graph = build_analysis_graph()
        result = await graph.ainvoke(initial_state)

    # ── Assertions ─────────────────────────────────────────────────────
    verdict = result["final_verdict"]
    assert isinstance(verdict, FinalVerdict), (
        f"Expected FinalVerdict, got {type(verdict).__name__}"
    )
    assert verdict.decision == "ENTER_LONG"
    assert verdict.overall_confidence == 0.75
    assert verdict.analyst_agreement_pct == 100
    assert len(verdict.approved_setups) == 1

    # Verify that analysts ran (at least 2 model calls + 1 arbiter)
    analyst_calls = [s for s in call_log if s != "arbiter"]
    assert len(analyst_calls) >= 2, f"Expected ≥2 analyst calls, got {len(analyst_calls)}"
    assert "arbiter" in call_log, "Arbiter was never called"

    # Verify analyst outputs were populated
    assert len(result["analyst_outputs"]) >= 2, (
        f"Expected ≥2 analyst outputs, got {len(result['analyst_outputs'])}"
    )

    # Verify macro_context was None (scheduler mocked to None)
    assert result["macro_context"] is None

    # Verify chart_analysis_runtime was populated
    runtime = result.get("chart_analysis_runtime")
    assert runtime is not None
    assert runtime.get("base_loaded") is True
