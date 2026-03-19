"""Tests for ai_analyst.core.engine_prompt_builder.

Covers prompt content validation for the Analysis Engine persona prompt builder.
"""

import json

import pytest

from ai_analyst.models.persona import PersonaType
from ai_analyst.models.persona_contract import (
    DEFAULT_ANALYST_CONTRACT,
    RISK_OFFICER_CONTRACT,
)
from ai_analyst.core.engine_prompt_builder import (
    build_engine_prompt,
    load_engine_persona_prompt,
)


# ---------------------------------------------------------------------------
# Shared fixture — structurally correct snapshot
# ---------------------------------------------------------------------------

def _make_snapshot() -> dict:
    return {
        "context": {
            "instrument": "XAUUSD",
            "timeframe": "1H",
            "timestamp": "2025-01-15T12:00:00Z",
        },
        "lenses": {
            "structure": {
                "trend": {"local_direction": "bullish", "structure_state": "HH_HL"},
                "levels": {"support": 2000.0, "resistance": 2100.0},
                "distance": {"to_support": 0.8, "to_resistance": 1.5},
            },
            "trend": {
                "direction": {"overall": "bullish", "ema_alignment": "bullish"},
                "strength": {"slope": "positive"},
            },
            "momentum": {
                "direction": {"state": "bullish", "roc_sign": "positive"},
                "strength": {"impulse": "strong"},
                "risk": {"exhaustion": False},
            },
        },
        "derived": {
            "alignment_score": 1.0,
            "conflict_score": 0.0,
            "signal_state": "SIGNAL",
            "coverage": None,
            "persona_agreement_score": None,
        },
        "meta": {
            "active_lenses": ["structure", "trend", "momentum"],
            "inactive_lenses": [],
            "failed_lenses": [],
            "lens_errors": {},
            "evidence_version": "v1.0",
            "snapshot_id": "abc123",
        },
    }


# ---------------------------------------------------------------------------
# Prompt loading tests
# ---------------------------------------------------------------------------

class TestLoadPersonaPrompt:
    def test_default_analyst_loads(self):
        text = load_engine_persona_prompt(PersonaType.DEFAULT_ANALYST)
        assert len(text) > 0
        assert "Default Analyst" in text

    def test_risk_officer_loads(self):
        text = load_engine_persona_prompt(PersonaType.RISK_OFFICER)
        assert len(text) > 0
        assert "Risk Officer" in text

    def test_unsupported_persona_raises(self):
        with pytest.raises(ValueError, match="No v2.0 persona prompt file"):
            load_engine_persona_prompt(PersonaType.PROSECUTOR)


# ---------------------------------------------------------------------------
# System prompt content tests
# ---------------------------------------------------------------------------

class TestSystemPromptContent:
    @pytest.fixture
    def prompt(self):
        return build_engine_prompt(
            snapshot=_make_snapshot(),
            persona_contract=DEFAULT_ANALYST_CONTRACT,
            run_status="SUCCESS",
        )

    def test_includes_all_8_output_fields(self, prompt):
        system = prompt["system"]
        for field in [
            "persona_id", "bias", "recommended_action", "confidence",
            "reasoning", "evidence_used", "counterpoints", "what_would_change_my_mind",
        ]:
            assert field in system, f"Missing field '{field}' in system prompt"

    def test_includes_lenses_citation_rule(self, prompt):
        system = prompt["system"]
        assert "lenses.*" in system or "lenses." in system

    def test_includes_confidence_bands(self, prompt):
        system = prompt["system"]
        assert "0.0" in system and "0.35" in system  # weak band
        assert "0.36" in system and "0.65" in system  # moderate band
        assert "0.66" in system and "1.00" in system  # strong band

    def test_includes_degraded_confidence_rule(self, prompt):
        system = prompt["system"]
        assert "DEGRADED" in system
        assert "0.65" in system

    def test_forbids_citing_inactive_failed_lenses(self, prompt):
        system = prompt["system"]
        assert "inactive" in system.lower()
        assert "failed" in system.lower()


# ---------------------------------------------------------------------------
# User prompt content tests
# ---------------------------------------------------------------------------

class TestUserPromptContent:
    @pytest.fixture
    def prompt(self):
        return build_engine_prompt(
            snapshot=_make_snapshot(),
            persona_contract=DEFAULT_ANALYST_CONTRACT,
            run_status="DEGRADED",
        )

    def test_includes_serialized_snapshot(self, prompt):
        user = prompt["user"]
        assert "EVIDENCE SNAPSHOT" in user
        assert '"lenses"' in user
        assert '"structure"' in user

    def test_includes_meta(self, prompt):
        user = prompt["user"]
        assert "META" in user
        assert "active_lenses" in user

    def test_includes_derived(self, prompt):
        user = prompt["user"]
        assert "DERIVED" in user
        assert "alignment_score" in user

    def test_includes_run_status(self, prompt):
        user = prompt["user"]
        assert "run_status: DEGRADED" in user

    def test_includes_instrument_timeframe_timestamp(self, prompt):
        user = prompt["user"]
        assert "XAUUSD" in user
        assert "1H" in user
        assert "2025-01-15T12:00:00Z" in user


# ---------------------------------------------------------------------------
# Macro context tests
# ---------------------------------------------------------------------------

class TestMacroContext:
    def test_macro_advisory_included_when_provided(self):
        macro = {"cpi_surprise": "negative", "risk_level": "elevated"}
        prompt = build_engine_prompt(
            snapshot=_make_snapshot(),
            persona_contract=DEFAULT_ANALYST_CONTRACT,
            run_status="SUCCESS",
            macro_context=macro,
        )
        user = prompt["user"]
        assert "MACRO ADVISORY" in user
        assert "cpi_surprise" in user
        assert "context only, not authority" in user.lower() or "not authority" in user

    def test_macro_advisory_absent_when_none(self):
        prompt = build_engine_prompt(
            snapshot=_make_snapshot(),
            persona_contract=DEFAULT_ANALYST_CONTRACT,
            run_status="SUCCESS",
            macro_context=None,
        )
        user = prompt["user"]
        assert "MACRO ADVISORY" not in user


# ---------------------------------------------------------------------------
# No legacy / chart language tests
# ---------------------------------------------------------------------------

class TestNoLegacyOrChartLanguage:
    """Ensure v2.0 prompts contain no chart/image/legacy language."""

    @pytest.fixture
    def all_prompt_text(self):
        prompt = build_engine_prompt(
            snapshot=_make_snapshot(),
            persona_contract=DEFAULT_ANALYST_CONTRACT,
            run_status="SUCCESS",
        )
        combined = prompt["system"] + prompt["persona"] + prompt["user"]
        return combined.lower()

    def test_no_chart_language(self, all_prompt_text):
        for term in ["chart", "screenshot", "overlay", "image"]:
            assert term not in all_prompt_text, f"Found forbidden term '{term}' in prompt"

    def test_no_legacy_schema_terms(self, all_prompt_text):
        for term in ["setup_valid", "sweep_status", "fvg_zones", "displacement_quality"]:
            assert term not in all_prompt_text, f"Found legacy term '{term}' in prompt"
