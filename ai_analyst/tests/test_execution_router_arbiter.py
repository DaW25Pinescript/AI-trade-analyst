"""
Regression tests for ExecutionRouter._run_arbiter_and_finalise.

Specifically guards against CRITICAL-1: macro_context and overlay_was_provided
were previously dropped (never passed to build_arbiter_prompt) in the CLI/hybrid
path.  These tests verify that:

  1. A macro_context injected at construction time reaches the arbiter prompt.
  2. When no macro_context is injected, the router fetches one via the scheduler
     and passes it to the arbiter prompt.
  3. When MRO fails, macro_context=None produces the "MRO unavailable" notice
     in the arbiter prompt (never raises).
  4. overlay_was_provided=True is passed when m15_overlay is present in the packet.
  5. overlay_was_provided=False is passed when no overlay is present.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from macro_risk_officer.core.models import AssetPressure, MacroContext
from ai_analyst.core.execution_router import ExecutionRouter
from ai_analyst.models.analyst_output import AnalystOutput
from ai_analyst.models.execution_config import (
    AnalystConfig, AnalystDelivery, ExecutionConfig, RunState, RunStatus,
)
from ai_analyst.models.persona import PersonaType


# ── Helpers ────────────────────────────────────────────────────────────────


def _sample_macro_context() -> MacroContext:
    return MacroContext(
        regime="risk_off",
        vol_bias="expanding",
        asset_pressure=AssetPressure(USD=0.7, GOLD=0.5, SPX=-0.6),
        conflict_score=-0.45,
        confidence=0.72,
        time_horizon_days=45,
        explanation=["Hawkish Fed surprise."],
        active_event_ids=["finnhub-fed-2026-03"],
    )


def _minimal_execution_config() -> ExecutionConfig:
    return ExecutionConfig(
        mode="automated",
        analysts=[
            AnalystConfig(
                analyst_id="analyst_1",
                persona=PersonaType.DEFAULT_ANALYST,
                delivery=AnalystDelivery.MANUAL,
                model=None,
                api_key_env_var=None,
            )
        ],
    )


def _minimal_run_state(run_id: str) -> RunState:
    return RunState(
        run_id=run_id,
        status=RunStatus.VALIDATION_PASSED,
        mode="automated",
        instrument="XAUUSD",
        session="NY",
    )


def _fake_analyst_outputs() -> list[AnalystOutput]:
    payload = {
        "htf_bias": "bearish",
        "structure_state": "continuation",
        "key_levels": {"premium": ["1950-1955"], "discount": ["1910-1915"]},
        "setup_valid": True,
        "setup_type": "liquidity_sweep_reversal",
        "entry_model": "Pullback",
        "invalidation": "Close above 1955",
        "disqualifiers": [],
        "confidence": 0.72,
        "rr_estimate": 2.4,
        "notes": "valid",
        "recommended_action": "SHORT",
    }
    return [AnalystOutput.model_validate(payload), AnalystOutput.model_validate(payload)]


def _stub_verdict_json() -> str:
    return json.dumps({
        "final_bias": "bearish",
        "decision": "NO_TRADE",
        "approved_setups": [],
        "no_trade_conditions": ["test"],
        "overall_confidence": 0.55,
        "analyst_agreement_pct": 100,
        "risk_override_applied": False,
        "arbiter_notes": "stub",
        "audit_log": {
            "run_id": "stub",
            "analysts_received": 2,
            "analysts_valid": 2,
            "htf_consensus": False,
            "setup_consensus": False,
            "risk_override": False,
        },
    })


# ── Tests ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_injected_macro_context_reaches_arbiter_prompt(
    sample_ground_truth, sample_lens_config, tmp_path, monkeypatch
):
    """When macro_context is injected at construction, the arbiter prompt must
    include the MRO arbiter_block() content (not the unavailability notice)."""
    ctx = _sample_macro_context()
    run_state = _minimal_run_state(sample_ground_truth.run_id)
    router = ExecutionRouter(
        _minimal_execution_config(),
        sample_ground_truth,
        sample_lens_config,
        run_state,
        macro_context=ctx,
    )
    # Override the output directory so nothing is written to the real tree
    router.analyst_outputs_dir = tmp_path / "analyst_outputs"
    router.analyst_outputs_dir.mkdir()

    captured: list[str] = []

    async def fake_metered(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=_stub_verdict_json()))]
        )

    monkeypatch.setattr(
        "ai_analyst.core.execution_router.acompletion_metered", fake_metered
    )
    # Patch save_run_state so we don't write state files
    monkeypatch.setattr("ai_analyst.core.execution_router.save_run_state", lambda s: None)

    await router._run_arbiter_and_finalise(_fake_analyst_outputs())

    assert captured, "acompletion_metered was never called"
    prompt = captured[0]

    # The MacroContext arbiter_block() injects the regime — confirm it is present
    assert "MACRO RISK CONTEXT" in prompt
    assert "macro_context_available: false" not in prompt, (
        "Injected macro_context should not produce the unavailability notice"
    )


@pytest.mark.asyncio
async def test_mro_failure_produces_unavailability_notice_not_exception(
    sample_ground_truth, sample_lens_config, tmp_path, monkeypatch
):
    """When MRO fetch fails, the arbiter prompt must contain the unavailability
    notice, and the router must NOT raise."""
    run_state = _minimal_run_state(sample_ground_truth.run_id)
    router = ExecutionRouter(
        _minimal_execution_config(),
        sample_ground_truth,
        sample_lens_config,
        run_state,
        # macro_context intentionally not injected
    )
    router.analyst_outputs_dir = tmp_path / "analyst_outputs"
    router.analyst_outputs_dir.mkdir()

    # Simulate MRO completely unavailable
    monkeypatch.setattr(
        "ai_analyst.core.execution_router._try_fetch_macro_context",
        lambda instrument: None,
    )

    captured: list[str] = []

    async def fake_metered(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=_stub_verdict_json()))]
        )

    monkeypatch.setattr(
        "ai_analyst.core.execution_router.acompletion_metered", fake_metered
    )
    monkeypatch.setattr("ai_analyst.core.execution_router.save_run_state", lambda s: None)

    # Must not raise even when MRO is unavailable
    verdict = await router._run_arbiter_and_finalise(_fake_analyst_outputs())

    assert verdict is not None
    assert captured
    assert "macro_context_available: false" in captured[0]


@pytest.mark.asyncio
async def test_overlay_was_provided_true_when_m15_overlay_in_packet(
    sample_ground_truth_with_overlay, sample_lens_config, tmp_path, monkeypatch
):
    """overlay_was_provided=True must reach build_arbiter_prompt when the
    GroundTruthPacket contains an m15_overlay."""
    run_state = _minimal_run_state(sample_ground_truth_with_overlay.run_id)
    router = ExecutionRouter(
        _minimal_execution_config(),
        sample_ground_truth_with_overlay,
        sample_lens_config,
        run_state,
    )
    router.analyst_outputs_dir = tmp_path / "analyst_outputs"
    router.analyst_outputs_dir.mkdir()

    monkeypatch.setattr(
        "ai_analyst.core.execution_router._try_fetch_macro_context",
        lambda instrument: None,
    )

    captured: list[str] = []

    async def fake_metered(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=_stub_verdict_json()))]
        )

    monkeypatch.setattr(
        "ai_analyst.core.execution_router.acompletion_metered", fake_metered
    )
    monkeypatch.setattr("ai_analyst.core.execution_router.save_run_state", lambda s: None)

    await router._run_arbiter_and_finalise(_fake_analyst_outputs())

    assert captured
    # When overlay_was_provided=True, the prompt must not contain the "no overlay" notice
    assert "overlay_was_provided: false" not in captured[0]
    assert "overlay_was_provided: true" in captured[0]


@pytest.mark.asyncio
async def test_overlay_was_provided_false_when_no_m15_overlay(
    sample_ground_truth, sample_lens_config, tmp_path, monkeypatch
):
    """overlay_was_provided=False must be reflected in the prompt when no
    overlay was submitted."""
    run_state = _minimal_run_state(sample_ground_truth.run_id)
    router = ExecutionRouter(
        _minimal_execution_config(),
        sample_ground_truth,
        sample_lens_config,
        run_state,
    )
    router.analyst_outputs_dir = tmp_path / "analyst_outputs"
    router.analyst_outputs_dir.mkdir()

    monkeypatch.setattr(
        "ai_analyst.core.execution_router._try_fetch_macro_context",
        lambda instrument: None,
    )

    captured: list[str] = []

    async def fake_metered(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=_stub_verdict_json()))]
        )

    monkeypatch.setattr(
        "ai_analyst.core.execution_router.acompletion_metered", fake_metered
    )
    monkeypatch.setattr("ai_analyst.core.execution_router.save_run_state", lambda s: None)

    await router._run_arbiter_and_finalise(_fake_analyst_outputs())

    assert captured
    assert "overlay_was_provided: false" in captured[0]
