"""
Observability Phase 1 — deterministic tests for run record and stdout summary.

Covers:
  AC-8:  run_record.json is produced and contains required fields
  AC-9:  stdout summary is emitted on run completion
  AC-10: smoke_mode visibility — skipped analysts listed with reason
  AC-11: failure visibility — failed analysts captured in run record
  AC-12: run record produced even on partial data
"""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_analyst.models.ground_truth import (
    GroundTruthPacket,
    MarketContext,
    RiskConstraints,
    ScreenshotMetadata,
)
from ai_analyst.models.arbiter_output import AuditLog, FinalVerdict
from ai_analyst.graph.logging_node import _build_run_record, _emit_stdout_summary


# ── Fixtures ────────────────────────────────────────────────────────────────

def _make_ground_truth(run_id: str = "test-run-001") -> GroundTruthPacket:
    return GroundTruthPacket(
        run_id=run_id,
        instrument="XAUUSD",
        session="London",
        timeframes=["H4"],
        charts={"H4": "base64-h4"},
        screenshot_metadata=[
            ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only"),
        ],
        risk_constraints=RiskConstraints(),
        context=MarketContext(account_balance=10000.0),
    )


def _make_verdict(run_id: str = "test-run-001") -> FinalVerdict:
    return FinalVerdict(
        final_bias="neutral",
        decision="NO_TRADE",
        approved_setups=[],
        no_trade_conditions=["Test run — no real analysis"],
        overall_confidence=0.0,
        analyst_agreement_pct=0,
        risk_override_applied=False,
        arbiter_notes="Deterministic test verdict",
        audit_log=AuditLog(
            run_id=run_id,
            analysts_received=1,
            analysts_valid=1,
            htf_consensus=False,
            setup_consensus=False,
            risk_override=False,
        ),
    )


def _make_state(
    run_id: str = "test-run-001",
    smoke_mode: bool = False,
    analyst_results: list | None = None,
    arbiter_meta: dict | None = None,
    error: str | None = None,
) -> dict:
    """Build a minimal GraphState-compatible dict for testing."""
    return {
        "ground_truth": _make_ground_truth(run_id),
        "final_verdict": _make_verdict(run_id),
        "analyst_outputs": [],
        "smoke_mode": smoke_mode,
        "_analyst_results": analyst_results or [],
        "_arbiter_meta": arbiter_meta,
        "_node_timings": {
            "validate_input_node": 5,
            "macro_context_node": 120,
            "chart_setup_node": 30,
            "chart_lenses_node": 3000,
            "arbiter_node": 2000,
            "logging_node": 10,
        },
        "_pipeline_start_ts": 1000.0,
        "error": error,
    }


def _make_usage() -> dict:
    return {
        "total_calls": 2,
        "successful_calls": 2,
        "failed_calls": 0,
        "calls_by_stage": {"phase1_analyst": 1, "arbiter": 1},
        "calls_by_model": {"claude-sonnet-4-6": 1, "claude-opus-4-6": 1},
        "calls_by_provider": {},
        "tokens": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        "total_cost_usd": 0.01,
    }


# ── AC-8: Run record shape ─────────────────────────────────────────────────

class TestRunRecordShape:
    """AC-8: run_record.json contains required fields."""

    def test_run_record_has_required_top_level_keys(self):
        state = _make_state(analyst_results=[
            {"persona": "default_analyst", "status": "success", "model": "m1", "provider": "p1"},
        ])
        record = _build_run_record(state, _make_usage(), 5000)

        required_keys = {
            "run_id", "timestamp", "duration_ms", "request", "stages",
            "analysts", "analysts_skipped", "analysts_failed",
            "arbiter", "artifacts", "usage_summary", "warnings", "errors",
        }
        assert required_keys.issubset(record.keys()), (
            f"Missing keys: {required_keys - record.keys()}"
        )

    def test_run_record_run_id_matches(self):
        state = _make_state(run_id="abc-123")
        record = _build_run_record(state, _make_usage(), 1000)
        assert record["run_id"] == "abc-123"

    def test_run_record_request_section(self):
        state = _make_state()
        record = _build_run_record(state, _make_usage(), 1000)
        req = record["request"]
        assert req["instrument"] == "XAUUSD"
        assert req["session"] == "London"
        assert req["timeframes"] == ["H4"]
        assert req["smoke_mode"] is False

    def test_run_record_stages_present(self):
        """AC-3: stage trace includes required stages."""
        state = _make_state()
        record = _build_run_record(state, _make_usage(), 1000)
        stage_names = [s["stage"] for s in record["stages"]]
        for required in ["validate_input", "analyst_execution", "arbiter", "logging"]:
            assert required in stage_names, f"Missing stage: {required}"

    def test_run_record_stages_have_status(self):
        state = _make_state()
        record = _build_run_record(state, _make_usage(), 1000)
        for s in record["stages"]:
            assert "status" in s, f"Stage {s['stage']} missing status"

    def test_run_record_stages_use_node_timings(self):
        """Stage timing derived from _node_timings, not duplicated."""
        state = _make_state()
        record = _build_run_record(state, _make_usage(), 1000)
        # validate_input maps to validate_input_node which has timing=5
        vi = next(s for s in record["stages"] if s["stage"] == "validate_input")
        assert vi.get("duration_ms") == 5

    def test_run_record_arbiter_section(self):
        """AC-5: arbiter record includes ran, verdict, confidence."""
        state = _make_state(arbiter_meta={
            "model": "claude-opus-4-6",
            "provider": "openai",
            "duration_ms": 2500,
        })
        record = _build_run_record(state, _make_usage(), 1000)
        arb = record["arbiter"]
        assert arb["ran"] is True
        assert arb["verdict"] == "NO_TRADE"
        assert arb["confidence"] == 0.0
        assert arb["model"] == "claude-opus-4-6"
        assert arb["provider"] == "openai"
        assert arb["duration_ms"] == 2500

    def test_run_record_artifacts_paths(self):
        state = _make_state()
        record = _build_run_record(state, _make_usage(), 1000)
        assert "run_record" in record["artifacts"]
        assert "usage_jsonl" in record["artifacts"]
        assert record["artifacts"]["run_record"].endswith("run_record.json")
        assert record["artifacts"]["usage_jsonl"].endswith("usage.jsonl")

    def test_run_record_usage_summary_passthrough(self):
        """AC-7: usage_summary is consumed from summarize_usage(), not duplicated."""
        usage = _make_usage()
        state = _make_state()
        record = _build_run_record(state, usage, 1000)
        assert record["usage_summary"] is usage  # exact same object — no copy


# ── AC-9: Stdout summary ───────────────────────────────────────────────────

class TestStdoutSummary:
    """AC-9: structured stdout summary emitted on run completion."""

    def test_stdout_summary_emitted(self, capsys):
        state = _make_state(analyst_results=[
            {"persona": "default_analyst", "status": "success", "model": "m1", "provider": "p1"},
        ])
        record = _build_run_record(state, _make_usage(), 5000)
        output = _emit_stdout_summary(record)

        captured = capsys.readouterr().out
        assert "Run Complete" in captured
        assert "test-run-001" in captured

    def test_stdout_contains_instrument_and_session(self, capsys):
        state = _make_state()
        record = _build_run_record(state, _make_usage(), 5000)
        _emit_stdout_summary(record)

        captured = capsys.readouterr().out
        assert "XAUUSD" in captured
        assert "London" in captured

    def test_stdout_contains_verdict(self, capsys):
        state = _make_state()
        record = _build_run_record(state, _make_usage(), 5000)
        _emit_stdout_summary(record)

        captured = capsys.readouterr().out
        assert "NO_TRADE" in captured

    def test_stdout_contains_pipeline_stages(self, capsys):
        state = _make_state()
        record = _build_run_record(state, _make_usage(), 5000)
        _emit_stdout_summary(record)

        captured = capsys.readouterr().out
        assert "validate_input" in captured
        assert "arbiter" in captured

    def test_stdout_contains_model_counts(self, capsys):
        state = _make_state()
        record = _build_run_record(state, _make_usage(), 5000)
        _emit_stdout_summary(record)

        captured = capsys.readouterr().out
        assert "claude-sonnet-4-6" in captured

    def test_stdout_returns_string(self):
        state = _make_state()
        record = _build_run_record(state, _make_usage(), 5000)
        output = _emit_stdout_summary(record)
        assert isinstance(output, str)
        assert len(output) > 0


# ── AC-10: Smoke mode visibility ───────────────────────────────────────────

class TestSmokeVisibility:
    """AC-10: smoke_mode skipped analysts listed with reason."""

    def test_smoke_mode_skipped_analysts_in_record(self):
        analyst_results = [
            {"persona": "default_analyst", "status": "success", "model": "m1", "provider": "p1"},
            {"persona": "macro_analyst", "status": "skipped", "reason": "smoke_mode — roster sliced to 1"},
            {"persona": "structure_analyst", "status": "skipped", "reason": "smoke_mode — roster sliced to 1"},
        ]
        state = _make_state(smoke_mode=True, analyst_results=analyst_results)
        record = _build_run_record(state, _make_usage(), 5000)

        assert len(record["analysts"]) == 1
        assert record["analysts"][0]["persona"] == "default_analyst"
        assert len(record["analysts_skipped"]) == 2
        for skipped in record["analysts_skipped"]:
            assert "smoke_mode" in skipped["reason"]

    def test_smoke_mode_flag_in_request(self):
        state = _make_state(smoke_mode=True)
        record = _build_run_record(state, _make_usage(), 1000)
        assert record["request"]["smoke_mode"] is True

    def test_smoke_mode_stdout_shows_skipped_count(self, capsys):
        analyst_results = [
            {"persona": "default_analyst", "status": "success", "model": "m1", "provider": "p1"},
            {"persona": "macro_analyst", "status": "skipped", "reason": "smoke_mode"},
        ]
        state = _make_state(smoke_mode=True, analyst_results=analyst_results)
        record = _build_run_record(state, _make_usage(), 5000)
        _emit_stdout_summary(record)

        captured = capsys.readouterr().out
        assert "1 ran" in captured
        assert "1 skipped" in captured


# ── AC-11: Failure visibility ──────────────────────────────────────────────

class TestFailureVisibility:
    """AC-11: failed analysts captured in run record."""

    def test_failed_analyst_in_record(self):
        analyst_results = [
            {"persona": "default_analyst", "status": "success", "model": "m1", "provider": "p1"},
            {"persona": "macro_analyst", "status": "failed", "model": "m2", "provider": "p1",
             "reason": "RuntimeError: provider returned 500"},
        ]
        state = _make_state(analyst_results=analyst_results)
        record = _build_run_record(state, _make_usage(), 5000)

        assert len(record["analysts_failed"]) == 1
        failed = record["analysts_failed"][0]
        assert failed["persona"] == "macro_analyst"
        assert failed["status"] == "failed"
        assert "500" in failed["reason"]

    def test_failure_generates_warning(self):
        analyst_results = [
            {"persona": "macro_analyst", "status": "failed", "model": "m2", "provider": "p1",
             "reason": "RuntimeError: timeout"},
        ]
        state = _make_state(analyst_results=analyst_results)
        record = _build_run_record(state, _make_usage(), 5000)

        assert len(record["warnings"]) >= 1
        assert any("macro_analyst" in w for w in record["warnings"])


# ── AC-12: Partial pipeline ────────────────────────────────────────────────

class TestPartialPipeline:
    """AC-12: run record produced even with partial state."""

    def test_run_record_with_error_state(self):
        state = _make_state(error="Arbiter response malformed")
        record = _build_run_record(state, _make_usage(), 5000)

        assert len(record["errors"]) >= 1
        assert "malformed" in record["errors"][0]

    def test_run_record_with_no_analyst_results(self):
        state = _make_state(analyst_results=[])
        record = _build_run_record(state, _make_usage(), 1000)

        assert record["analysts"] == []
        assert record["analysts_skipped"] == []
        assert record["analysts_failed"] == []

    def test_run_record_arbiter_not_ran(self):
        state = _make_state()
        state["final_verdict"] = None
        record = _build_run_record(state, _make_usage(), 1000)

        assert record["arbiter"]["ran"] is False


# ── AC-4: Analyst result shape ─────────────────────────────────────────────

class TestAnalystResultShape:
    """AC-4: each analyst has result record with persona/status/model/provider."""

    def test_success_analyst_has_required_fields(self):
        analyst_results = [
            {"persona": "default_analyst", "status": "success",
             "model": "claude-sonnet-4-6", "provider": "openai"},
        ]
        state = _make_state(analyst_results=analyst_results)
        record = _build_run_record(state, _make_usage(), 1000)

        ran = record["analysts"][0]
        assert ran["persona"] == "default_analyst"
        assert ran["status"] == "success"
        assert ran["model"] == "claude-sonnet-4-6"
        assert ran["provider"] == "openai"

    def test_skipped_analyst_has_reason(self):
        analyst_results = [
            {"persona": "macro_analyst", "status": "skipped",
             "reason": "smoke_mode — roster sliced to 1"},
        ]
        state = _make_state(analyst_results=analyst_results)
        record = _build_run_record(state, _make_usage(), 1000)

        skipped = record["analysts_skipped"][0]
        assert "reason" in skipped
        assert len(skipped["reason"]) > 0
