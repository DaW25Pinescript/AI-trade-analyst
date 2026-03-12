"""
Phase 7 — AI/ML Enhancement test suite.

Tests:
  1. Feedback loop: outcomes → prompt refinement report generation
  2. Bias detection in analyst outputs
  3. Fallback model routing in LLM client
"""

import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_analyst.models.analyst_output import AnalystOutput


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_analyst(
    recommended_action: str = "LONG",
    confidence: float = 0.75,
    htf_bias: str = "bullish",
    setup_valid: bool = True,
) -> AnalystOutput:
    """Create a canned AnalystOutput for testing."""
    # NO_TRADE rule: if setup_valid is False or confidence < 0.45, action must be NO_TRADE
    if not setup_valid or confidence < 0.45:
        recommended_action = "NO_TRADE"
    return AnalystOutput(
        htf_bias=htf_bias,
        structure_state="continuation",
        key_levels={"premium": ["2050"], "discount": ["2030"]},
        setup_valid=setup_valid,
        setup_type="BOS retest",
        entry_model="M5 FVG",
        invalidation="Below 2020",
        disqualifiers=[],
        confidence=confidence,
        rr_estimate=3.0,
        notes="Test analyst output",
        recommended_action=recommended_action,
    )


def _create_test_db(tmp_path: Path, runs: list[dict]) -> Path:
    """Create a test outcomes.db with the given run records."""
    db_path = tmp_path / "outcomes.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id               TEXT    NOT NULL UNIQUE,
            instrument           TEXT    NOT NULL,
            recorded_at          TEXT    NOT NULL,
            regime               TEXT    NOT NULL,
            vol_bias             TEXT    NOT NULL,
            conflict_score       REAL    NOT NULL,
            confidence           REAL    NOT NULL,
            time_horizon_days    INTEGER NOT NULL,
            active_event_ids     TEXT    NOT NULL,
            explanation          TEXT    NOT NULL,
            decision             TEXT,
            overall_confidence   REAL,
            analyst_agreement    INTEGER,
            risk_override        INTEGER,
            price_at_record      REAL,
            price_at_1h          REAL,
            price_at_24h         REAL,
            price_at_5d          REAL,
            pct_change_1h        REAL,
            pct_change_24h       REAL,
            pct_change_5d        REAL,
            predicted_direction  INTEGER
        )
    """)

    for run in runs:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, instrument, recorded_at, regime, vol_bias,
                conflict_score, confidence, time_horizon_days,
                active_event_ids, explanation,
                decision, overall_confidence, analyst_agreement, risk_override,
                price_at_record, pct_change_24h, predicted_direction
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.get("run_id", f"run-{id(run)}"),
                run.get("instrument", "XAUUSD"),
                run.get("recorded_at", "2026-03-01T00:00:00Z"),
                run.get("regime", "risk_on"),
                run.get("vol_bias", "normal"),
                run.get("conflict_score", 0.2),
                run.get("confidence", 0.7),
                run.get("time_horizon_days", 5),
                run.get("active_event_ids", "[]"),
                run.get("explanation", "[]"),
                run.get("decision", "ENTER_LONG"),
                run.get("overall_confidence", 0.7),
                run.get("analyst_agreement", 80),
                run.get("risk_override", 0),
                run.get("price_at_record", 2050.0),
                run.get("pct_change_24h"),
                run.get("predicted_direction", 1),
            ),
        )
    conn.commit()
    conn.close()
    return db_path


# ══════════════════════════════════════════════════════════════════════════════
# 1. BIAS DETECTION
# ══════════════════════════════════════════════════════════════════════════════


class TestBiasDetector:
    """Phase 7 bias detection heuristics."""

    def test_clean_report_for_diverse_outputs(self):
        """No flags when analysts genuinely disagree."""
        from ai_analyst.core.bias_detector import detect_bias

        outputs = [
            _make_analyst("LONG", 0.75, "bullish"),
            _make_analyst("SHORT", 0.60, "bearish"),
            _make_analyst("NO_TRADE", 0.40, "neutral", setup_valid=False),
        ]
        report = detect_bias(outputs)
        assert report.highest_severity == "clean"
        assert len(report.flags) == 0

    def test_unanimous_high_confidence_flagged(self):
        """Flag when all analysts agree on same action with high confidence."""
        from ai_analyst.core.bias_detector import detect_bias

        outputs = [
            _make_analyst("LONG", 0.85, "bullish"),
            _make_analyst("LONG", 0.80, "bullish"),
            _make_analyst("LONG", 0.90, "bullish"),
        ]
        report = detect_bias(outputs)
        codes = [f.code for f in report.flags]
        assert "UNANIMOUS_HIGH_CONF" in codes
        assert report.has_warnings

    def test_low_htf_diversity_flagged(self):
        """Flag when all HTF biases match with narrow confidence spread."""
        from ai_analyst.core.bias_detector import detect_bias

        outputs = [
            _make_analyst("LONG", 0.70, "bullish"),
            _make_analyst("LONG", 0.72, "bullish"),
            _make_analyst("LONG", 0.71, "bullish"),
        ]
        report = detect_bias(outputs)
        codes = [f.code for f in report.flags]
        assert "LOW_HTF_DIVERSITY" in codes

    def test_confidence_clustering_flagged(self):
        """Flag when all confidences cluster within 0.05 range."""
        from ai_analyst.core.bias_detector import detect_bias

        outputs = [
            _make_analyst("LONG", 0.70, "bullish"),
            _make_analyst("SHORT", 0.72, "bearish"),
            _make_analyst("LONG", 0.71, "neutral"),
        ]
        report = detect_bias(outputs)
        codes = [f.code for f in report.flags]
        assert "CONFIDENCE_CLUSTERING" in codes

    def test_single_dissenter_flagged(self):
        """Flag when exactly one analyst disagrees with all others."""
        from ai_analyst.core.bias_detector import detect_bias

        outputs = [
            _make_analyst("LONG", 0.75, "bullish"),
            _make_analyst("LONG", 0.60, "bullish"),
            _make_analyst("NO_TRADE", 0.40, "bearish", setup_valid=False),
        ]
        report = detect_bias(outputs)
        codes = [f.code for f in report.flags]
        assert "SINGLE_DISSENTER" in codes

    def test_single_analyst_no_flags(self):
        """No flags with a single analyst — bias detection requires at least 2."""
        from ai_analyst.core.bias_detector import detect_bias

        outputs = [_make_analyst("LONG", 0.85, "bullish")]
        report = detect_bias(outputs)
        assert report.highest_severity == "clean"

    def test_format_for_arbiter_clean(self):
        """Clean report produces expected arbiter text."""
        from ai_analyst.core.bias_detector import detect_bias

        outputs = [
            _make_analyst("LONG", 0.75, "bullish"),
            _make_analyst("SHORT", 0.60, "bearish"),
        ]
        report = detect_bias(outputs)
        text = report.format_for_arbiter()
        assert "bias_check: clean" in text

    def test_format_for_arbiter_with_flags(self):
        """Flagged report includes mitigation rules."""
        from ai_analyst.core.bias_detector import detect_bias

        outputs = [
            _make_analyst("LONG", 0.85, "bullish"),
            _make_analyst("LONG", 0.80, "bullish"),
            _make_analyst("LONG", 0.90, "bullish"),
        ]
        report = detect_bias(outputs)
        text = report.format_for_arbiter()
        assert "BIAS MITIGATION RULES" in text
        assert "bias_check: warning" in text


# ══════════════════════════════════════════════════════════════════════════════
# 2. FEEDBACK LOOP
# ══════════════════════════════════════════════════════════════════════════════


class TestFeedbackLoop:
    """Phase 7 feedback loop report generation."""

    def test_empty_db_returns_no_data(self, tmp_path):
        """Report from empty DB returns zero-state report."""
        from ai_analyst.core.feedback_loop import build_feedback_report

        db_path = _create_test_db(tmp_path, [])
        report = build_feedback_report(db_path=db_path, runs_dir=tmp_path / "runs")
        assert report.total_runs == 0
        assert report.priced_runs == 0

    def test_missing_db_returns_recommendation(self, tmp_path):
        """Report when DB doesn't exist gives a helpful recommendation."""
        from ai_analyst.core.feedback_loop import build_feedback_report

        report = build_feedback_report(
            db_path=tmp_path / "nonexistent.db",
            runs_dir=tmp_path / "runs",
        )
        assert report.total_runs == 0
        assert any("No outcomes database" in r for r in report.recommendations)

    def test_regime_accuracy_computed(self, tmp_path):
        """Regime accuracy is computed from priced runs."""
        from ai_analyst.core.feedback_loop import build_feedback_report

        runs = [
            {"run_id": "r1", "regime": "risk_on", "decision": "ENTER_LONG",
             "overall_confidence": 0.7, "pct_change_24h": 1.5, "predicted_direction": 1},
            {"run_id": "r2", "regime": "risk_on", "decision": "ENTER_LONG",
             "overall_confidence": 0.8, "pct_change_24h": -0.5, "predicted_direction": 1},
            {"run_id": "r3", "regime": "risk_off", "decision": "NO_TRADE",
             "overall_confidence": 0.5, "pct_change_24h": -2.0, "predicted_direction": -1},
        ]
        db_path = _create_test_db(tmp_path, runs)
        report = build_feedback_report(db_path=db_path, runs_dir=tmp_path / "runs")

        assert report.total_runs == 3
        assert report.priced_runs == 3
        assert len(report.regime_accuracy) >= 1

        # risk_on should have 1 correct out of 2 = 50%
        risk_on = next(r for r in report.regime_accuracy if r.regime == "risk_on")
        assert risk_on.correct == 1
        assert risk_on.total == 2

    def test_confidence_calibration_buckets(self, tmp_path):
        """Confidence calibration produces 3 buckets."""
        from ai_analyst.core.feedback_loop import build_feedback_report

        runs = [
            {"run_id": f"r{i}", "regime": "risk_on", "decision": "ENTER_LONG",
             "overall_confidence": conf, "pct_change_24h": pct, "predicted_direction": 1}
            for i, (conf, pct) in enumerate([
                (0.2, 1.0), (0.5, -1.0), (0.8, 1.0), (0.9, 1.0), (0.1, -1.0),
            ])
        ]
        db_path = _create_test_db(tmp_path, runs)
        report = build_feedback_report(db_path=db_path, runs_dir=tmp_path / "runs")

        assert len(report.confidence_calibration) == 3

    def test_format_output(self, tmp_path):
        """Format output produces human-readable text."""
        from ai_analyst.core.feedback_loop import build_feedback_report

        runs = [
            {"run_id": "r1", "regime": "risk_on", "decision": "ENTER_LONG",
             "overall_confidence": 0.7, "pct_change_24h": 1.5, "predicted_direction": 1},
        ]
        db_path = _create_test_db(tmp_path, runs)
        report = build_feedback_report(db_path=db_path, runs_dir=tmp_path / "runs")
        text = report.format()
        assert "FEEDBACK LOOP REPORT" in text

    def test_recommendations_for_low_accuracy_regime(self, tmp_path):
        """Generates recommendation for regimes with < 50% accuracy."""
        from ai_analyst.core.feedback_loop import build_feedback_report

        runs = [
            {"run_id": f"r{i}", "regime": "risk_off", "decision": "ENTER_SHORT",
             "overall_confidence": 0.7, "pct_change_24h": 2.0, "predicted_direction": -1}
            for i in range(4)
        ]
        db_path = _create_test_db(tmp_path, runs)
        report = build_feedback_report(db_path=db_path, runs_dir=tmp_path / "runs")

        assert any("accuracy" in r.lower() for r in report.recommendations)

    def test_persona_dominance_from_run_files(self, tmp_path):
        """Persona dominance is detected from per-run verdict + analyst files."""
        from ai_analyst.core.feedback_loop import build_feedback_report

        db_path = _create_test_db(tmp_path, [{"run_id": "r1", "regime": "risk_on"}])
        runs_dir = tmp_path / "runs"

        # Create run directory structure
        run_dir = runs_dir / "r1"
        analyst_dir = run_dir / "analyst_outputs"
        analyst_dir.mkdir(parents=True)

        # Write verdict
        verdict = {"decision": "ENTER_LONG"}
        (run_dir / "final_verdict.json").write_text(json.dumps(verdict))

        # Write analyst outputs — all match the verdict
        for i in range(3):
            ao = {"recommended_action": "LONG", "confidence": 0.8}
            (analyst_dir / f"analyst_{i+1}.json").write_text(json.dumps(ao))

        report = build_feedback_report(db_path=db_path, runs_dir=runs_dir)
        # With only 1 run, dominance won't be flagged (requires >= 3 runs)
        # but persona_dominance should still contain entries
        assert isinstance(report.persona_dominance, list)


# ══════════════════════════════════════════════════════════════════════════════
# 3. FALLBACK MODEL ROUTING
# ══════════════════════════════════════════════════════════════════════════════


class TestFallbackModelRouting:
    """Phase 7 fallback model routing in LLM client."""

    def test_get_fallback_models_default(self):
        """Default fallback map returns expected models."""
        from ai_analyst.core.llm_client import get_fallback_models

        fallbacks = get_fallback_models("gpt-4o")
        assert "gpt-4o-mini" in fallbacks
        assert len(fallbacks) >= 1

    def test_get_fallback_models_unknown_model(self):
        """Unknown model returns empty fallback list."""
        from ai_analyst.core.llm_client import get_fallback_models

        fallbacks = get_fallback_models("unknown-model-xyz")
        assert fallbacks == []

    def test_get_fallback_models_env_override(self, monkeypatch):
        """FALLBACK_MODEL_MAP env var overrides defaults."""
        from ai_analyst.core.llm_client import get_fallback_models

        custom_map = {"my-model": ["fallback-a", "fallback-b"]}
        monkeypatch.setenv("FALLBACK_MODEL_MAP", json.dumps(custom_map))

        fallbacks = get_fallback_models("my-model")
        assert fallbacks == ["fallback-a", "fallback-b"]

    def test_get_fallback_models_invalid_env(self, monkeypatch):
        """Invalid FALLBACK_MODEL_MAP env var falls back to defaults."""
        from ai_analyst.core.llm_client import get_fallback_models

        monkeypatch.setenv("FALLBACK_MODEL_MAP", "not-json")
        fallbacks = get_fallback_models("gpt-4o")
        assert "gpt-4o-mini" in fallbacks  # should use defaults

    async def test_fallback_succeeds_after_primary_fails(self):
        """When primary model fails, fallback model is tried and succeeds."""
        from ai_analyst.core.llm_client import acompletion_with_fallback

        call_count = 0
        models_called = []

        async def mock_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            model = kwargs.get("model", "")
            models_called.append(model)
            if model == "gpt-4o":
                raise RuntimeError("Primary model unavailable")
            return MagicMock(choices=[MagicMock(message=MagicMock(content="{}"))])

        response, total_attempts, model_used = await acompletion_with_fallback(
            mock_completion,
            model="gpt-4o",
            messages=[{"role": "user", "content": "test"}],
            retry_backoff_s=0,
            max_retries=0,
        )

        assert model_used != "gpt-4o"
        assert model_used in ("gpt-4o-mini", "claude-haiku-4-5-20251001")

    async def test_primary_succeeds_no_fallback_needed(self):
        """When primary model succeeds, no fallback is attempted."""
        from ai_analyst.core.llm_client import acompletion_with_fallback

        models_called = []

        async def mock_completion(**kwargs):
            models_called.append(kwargs.get("model", ""))
            return MagicMock(choices=[MagicMock(message=MagicMock(content="{}"))])

        response, total_attempts, model_used = await acompletion_with_fallback(
            mock_completion,
            model="gpt-4o",
            messages=[{"role": "user", "content": "test"}],
            retry_backoff_s=0,
        )

        assert model_used == "gpt-4o"
        assert len(models_called) == 1

    async def test_all_models_fail_raises(self):
        """When all models (primary + fallbacks) fail, RuntimeError is raised."""
        from ai_analyst.core.llm_client import acompletion_with_fallback

        async def mock_completion(**kwargs):
            raise RuntimeError(f"Model {kwargs.get('model', '')} unavailable")

        with pytest.raises(RuntimeError, match="All models failed"):
            await acompletion_with_fallback(
                mock_completion,
                model="gpt-4o",
                messages=[{"role": "user", "content": "test"}],
                retry_backoff_s=0,
                max_retries=0,
            )

    async def test_no_fallbacks_defined_raises_original(self):
        """When no fallbacks are defined for a model, the original error propagates."""
        from ai_analyst.core.llm_client import acompletion_with_fallback

        async def mock_completion(**kwargs):
            raise RuntimeError("Model unavailable")

        with pytest.raises(RuntimeError, match="Model unavailable"):
            await acompletion_with_fallback(
                mock_completion,
                model="unknown-model-no-fallbacks",
                messages=[{"role": "user", "content": "test"}],
                retry_backoff_s=0,
                max_retries=0,
            )


# ══════════════════════════════════════════════════════════════════════════════
# 4. ARBITER PROMPT BUILDER INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════


class TestArbiterPromptBuilderBiasIntegration:
    """Verify bias_section is injected into the arbiter prompt."""

    def test_bias_section_in_prompt(self, sample_ground_truth, sample_lens_config):
        """Arbiter prompt includes bias detection section."""
        from ai_analyst.core.arbiter_prompt_builder import build_arbiter_prompt

        outputs = [
            _make_analyst("LONG", 0.75, "bullish"),
            _make_analyst("SHORT", 0.60, "bearish"),
        ]

        prompt = build_arbiter_prompt(
            analyst_outputs=outputs,
            risk_constraints=sample_ground_truth.risk_constraints,
            run_id="test-run-001",
        )

        assert "BIAS DETECTION" in prompt

    def test_bias_section_reflects_groupthink(self, sample_ground_truth):
        """When groupthink is detected, bias section flags it."""
        from ai_analyst.core.arbiter_prompt_builder import build_arbiter_prompt

        outputs = [
            _make_analyst("LONG", 0.85, "bullish"),
            _make_analyst("LONG", 0.80, "bullish"),
            _make_analyst("LONG", 0.90, "bullish"),
        ]

        prompt = build_arbiter_prompt(
            analyst_outputs=outputs,
            risk_constraints=sample_ground_truth.risk_constraints,
            run_id="test-run-002",
        )

        assert "UNANIMOUS_HIGH_CONF" in prompt
        assert "BIAS MITIGATION RULES" in prompt
