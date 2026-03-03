"""
Regression tests for CRITICAL-4: Overlay delta node model alignment.

When Phase 1 has partial failures (e.g., analysts 0 and 2 fail, but 1 and 3
succeed), Phase 2 must use the SAME model config that produced each surviving
analyst output — not re-index by position into the global ANALYST_CONFIGS list.

Before the fix, overlay_delta_node used ANALYST_CONFIGS[i % len(ANALYST_CONFIGS)]
which assigned wrong model configs when partial Phase 1 failures shifted indices.
After the fix, analyst_configs_used is populated in parallel_analyst_node and
consumed by overlay_delta_node, guaranteeing correct config→output alignment.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from ai_analyst.graph.analyst_nodes import (
    ANALYST_CONFIGS,
    parallel_analyst_node,
    overlay_delta_node,
)
from ai_analyst.models.analyst_output import AnalystOutput, OverlayDeltaReport
from ai_analyst.models.ground_truth import (
    GroundTruthPacket,
    MarketContext,
    RiskConstraints,
    ScreenshotMetadata,
)
from ai_analyst.models.lens_config import LensConfig


pytestmark = pytest.mark.asyncio


# ── Helpers ────────────────────────────────────────────────────────────────


def _sample_analyst_output(**overrides) -> AnalystOutput:
    defaults = {
        "htf_bias": "bullish",
        "structure_state": "continuation",
        "key_levels": {"premium": ["2050"], "discount": ["2000"]},
        "setup_valid": True,
        "disqualifiers": [],
        "confidence": 0.75,
        "notes": "Test output",
        "recommended_action": "LONG",
    }
    defaults.update(overrides)
    return AnalystOutput(**defaults)


def _sample_overlay_delta() -> OverlayDeltaReport:
    return OverlayDeltaReport(
        confirms=["Price confirms FVG zone"],
        refines=[],
        contradicts=[],
        indicator_only_claims=[],
    )


def _make_ground_truth(with_overlay: bool = False) -> GroundTruthPacket:
    gt = GroundTruthPacket(
        instrument="XAUUSD",
        session="NY",
        timeframes=["H4", "M15"],
        charts={"H4": "base64-h4", "M15": "base64-m15"},
        screenshot_metadata=[
            ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only"),
            ScreenshotMetadata(timeframe="M15", lens="NONE", evidence_type="price_only"),
        ],
        risk_constraints=RiskConstraints(),
        context=MarketContext(account_balance=10000.0),
    )
    if with_overlay:
        gt = gt.model_copy(update={
            "m15_overlay": "base64-overlay",
            "m15_overlay_metadata": ScreenshotMetadata(
                timeframe="M15",
                lens="ICT",
                evidence_type="indicator_overlay",
                indicator_claims=["Fair value gap boundary from ICT tool"],
                indicator_source="TradingView ICT tool",
                settings_locked=True,
            ),
        })
    return gt


def _make_state(with_overlay: bool = False) -> dict:
    return {
        "ground_truth": _make_ground_truth(with_overlay),
        "lens_config": LensConfig(),
        "analyst_outputs": [],
        "analyst_configs_used": [],
        "overlay_delta_reports": [],
        "chart_analysis_runtime": None,
        "macro_context": None,
        "final_verdict": None,
        "error": None,
    }


# ── Phase 1: parallel_analyst_node tracks configs ─────────────────────────


class TestParallelAnalystNodeConfigTracking:
    async def test_all_succeed_configs_match_analyst_configs(self, monkeypatch):
        """When all analysts succeed, analyst_configs_used == ANALYST_CONFIGS."""
        output = _sample_analyst_output()

        async def mock_run_analyst(config, prompt, run_id):
            return output

        monkeypatch.setattr(
            "ai_analyst.graph.analyst_nodes.run_analyst", mock_run_analyst
        )
        state = _make_state()
        result = await parallel_analyst_node(state)

        assert len(result["analyst_configs_used"]) == len(ANALYST_CONFIGS)
        for i, cfg in enumerate(result["analyst_configs_used"]):
            assert cfg is ANALYST_CONFIGS[i]

    async def test_partial_failure_configs_match_survivors(self, monkeypatch):
        """When analysts 0 and 2 fail, configs_used contains only configs 1 and 3."""
        output = _sample_analyst_output()

        call_index = {"n": 0}

        async def mock_run_analyst(config, prompt, run_id):
            idx = call_index["n"]
            call_index["n"] += 1
            if idx in (0, 2):
                raise RuntimeError(f"Simulated failure for analyst {idx}")
            return output

        monkeypatch.setattr(
            "ai_analyst.graph.analyst_nodes.run_analyst", mock_run_analyst
        )
        state = _make_state()
        result = await parallel_analyst_node(state)

        assert len(result["analyst_outputs"]) == 2
        assert len(result["analyst_configs_used"]) == 2
        assert result["analyst_configs_used"][0] is ANALYST_CONFIGS[1]
        assert result["analyst_configs_used"][1] is ANALYST_CONFIGS[3]

    async def test_configs_used_parallel_to_outputs(self, monkeypatch):
        """analyst_configs_used[i] is always the config that produced analyst_outputs[i]."""
        outputs_by_model = {}

        async def mock_run_analyst(config, prompt, run_id):
            out = _sample_analyst_output(notes=f"from-{config['model']}")
            outputs_by_model[config["model"]] = out
            return out

        monkeypatch.setattr(
            "ai_analyst.graph.analyst_nodes.run_analyst", mock_run_analyst
        )
        state = _make_state()
        result = await parallel_analyst_node(state)

        for i, output in enumerate(result["analyst_outputs"]):
            cfg = result["analyst_configs_used"][i]
            assert output.notes == f"from-{cfg['model']}"


# ── Phase 2: overlay_delta_node uses correct configs ──────────────────────


class TestOverlayDeltaConfigAlignment:
    async def test_uses_configs_used_not_positional_index(self, monkeypatch):
        """
        Core CRITICAL-4 regression test: after Phase 1 partial failure where
        analysts 0 (gpt-4o) and 2 (gemini) fail, Phase 2 must use configs 1
        (claude-sonnet) and 3 (grok) — NOT re-index to configs 0 and 1.
        """
        called_with_models: list[str] = []

        async def mock_run_overlay_delta(config, prompt, run_id):
            called_with_models.append(config["model"])
            return _sample_overlay_delta()

        monkeypatch.setattr(
            "ai_analyst.graph.analyst_nodes.run_overlay_delta",
            mock_run_overlay_delta,
        )

        # Simulate: analysts 1 and 3 survived Phase 1
        state = _make_state(with_overlay=True)
        state["analyst_outputs"] = [_sample_analyst_output(), _sample_analyst_output()]
        state["analyst_configs_used"] = [ANALYST_CONFIGS[1], ANALYST_CONFIGS[3]]

        result = await overlay_delta_node(state)

        assert called_with_models == [
            ANALYST_CONFIGS[1]["model"],  # claude-sonnet-4-6
            ANALYST_CONFIGS[3]["model"],  # grok/grok-4-vision
        ]
        assert len(result["overlay_delta_reports"]) == 2

    async def test_single_survivor_uses_its_original_config(self, monkeypatch):
        """When only one analyst survives Phase 1, Phase 2 uses that analyst's config."""
        called_with_models: list[str] = []

        async def mock_run_overlay_delta(config, prompt, run_id):
            called_with_models.append(config["model"])
            return _sample_overlay_delta()

        monkeypatch.setattr(
            "ai_analyst.graph.analyst_nodes.run_overlay_delta",
            mock_run_overlay_delta,
        )

        # Only analyst 2 (gemini) survived
        state = _make_state(with_overlay=True)
        state["analyst_outputs"] = [_sample_analyst_output()]
        state["analyst_configs_used"] = [ANALYST_CONFIGS[2]]

        result = await overlay_delta_node(state)

        assert called_with_models == ["gemini/gemini-1.5-pro"]
        assert len(result["overlay_delta_reports"]) == 1

    async def test_all_succeed_models_match_analyst_configs_order(self, monkeypatch):
        """When all analysts succeed, overlay delta models follow ANALYST_CONFIGS order."""
        called_with_models: list[str] = []

        async def mock_run_overlay_delta(config, prompt, run_id):
            called_with_models.append(config["model"])
            return _sample_overlay_delta()

        monkeypatch.setattr(
            "ai_analyst.graph.analyst_nodes.run_overlay_delta",
            mock_run_overlay_delta,
        )

        state = _make_state(with_overlay=True)
        state["analyst_outputs"] = [_sample_analyst_output() for _ in ANALYST_CONFIGS]
        state["analyst_configs_used"] = list(ANALYST_CONFIGS)

        result = await overlay_delta_node(state)

        expected = [cfg["model"] for cfg in ANALYST_CONFIGS]
        assert called_with_models == expected

    async def test_no_overlay_returns_empty_reports(self, monkeypatch):
        """overlay_delta_node with no m15_overlay skips Phase 2 entirely."""
        state = _make_state(with_overlay=False)
        state["analyst_outputs"] = [_sample_analyst_output()]
        state["analyst_configs_used"] = [ANALYST_CONFIGS[0]]

        result = await overlay_delta_node(state)

        assert result["overlay_delta_reports"] == []

    async def test_phase2_partial_failure_logs_correct_model_name(self, monkeypatch, capsys):
        """When Phase 2 fails for a specific analyst, the warning shows the correct model name."""
        call_index = {"n": 0}

        async def mock_run_overlay_delta(config, prompt, run_id):
            idx = call_index["n"]
            call_index["n"] += 1
            if idx == 0:
                raise RuntimeError("API timeout")
            return _sample_overlay_delta()

        monkeypatch.setattr(
            "ai_analyst.graph.analyst_nodes.run_overlay_delta",
            mock_run_overlay_delta,
        )

        # Analysts 1 and 3 survived Phase 1
        state = _make_state(with_overlay=True)
        state["analyst_outputs"] = [_sample_analyst_output(), _sample_analyst_output()]
        state["analyst_configs_used"] = [ANALYST_CONFIGS[1], ANALYST_CONFIGS[3]]

        result = await overlay_delta_node(state)

        captured = capsys.readouterr()
        # The warning should reference claude-sonnet-4-6 (configs_used[0]), not gpt-4o
        assert ANALYST_CONFIGS[1]["model"] in captured.out
        assert len(result["overlay_delta_reports"]) == 1
