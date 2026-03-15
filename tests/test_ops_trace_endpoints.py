"""Deterministic tests for Agent Operations trace endpoint (PR-OPS-4a).

Covers AC-1 through AC-9, AC-18, AC-19, AC-20, AC-21, AC-22, AC-24, AC-25
from docs/PR_OPS_4_SPEC_FINAL.md §11.

All tests are fixture-based — no live provider dependency.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_analyst.api.models.ops_trace import (
    AgentTraceResponse,
    ArbiterTraceSummary,
    ArtifactRef,
    ParticipantContribution,
    TraceSummary,
    TraceEdge,
    TraceParticipant,
    TraceStage,
)
from ai_analyst.api.services.ops_roster import get_all_roster_ids
from ai_analyst.api.services.ops_trace import (
    TraceProjectionError,
    project_trace,
)


# ── Paths ────────────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_RUN_RECORD = FIXTURES_DIR / "sample_run_record.json"
SAMPLE_AUDIT_LOG = FIXTURES_DIR / "sample_audit_log.jsonl"
SAMPLE_RUN_ID = "run_20260314_test001"


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def client():
    """Lightweight TestClient with only the ops router mounted."""
    from ai_analyst.api.routers.ops import router as ops_router

    app = FastAPI()
    app.include_router(ops_router)
    app.state.feeder_context = None
    app.state.feeder_payload_meta = None
    app.state.feeder_ingested_at = None
    return TestClient(app)


@pytest.fixture()
def trace_response() -> AgentTraceResponse:
    """Project a trace from the sample fixtures."""
    return project_trace(
        run_id=SAMPLE_RUN_ID,
        run_record_path=SAMPLE_RUN_RECORD,
        audit_log_path=SAMPLE_AUDIT_LOG,
    )


@pytest.fixture()
def trace_response_no_audit() -> AgentTraceResponse:
    """Project a trace from run_record only (audit log missing)."""
    return project_trace(
        run_id=SAMPLE_RUN_ID,
        run_record_path=SAMPLE_RUN_RECORD,
        audit_log_path=Path("/nonexistent/audit.jsonl"),
    )


@pytest.fixture()
def trace_dict(trace_response: AgentTraceResponse) -> dict:
    """Serialized trace response dict (by_alias=True for from→from)."""
    return trace_response.model_dump(by_alias=True)


# ═══════════════════════════════════════════════════════════════════════════════
# AC-1 — Trace shape: valid AgentTraceResponse with all required fields
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceResponseShape:
    """AC-1: /runs/{run_id}/agent-trace returns valid AgentTraceResponse."""

    def test_trace_returns_all_required_fields(self, trace_dict):
        required = [
            "version", "generated_at", "data_state", "run_id",
            "run_status", "summary", "stages", "participants",
            "trace_edges", "arbiter_summary", "artifact_refs",
        ]
        for field in required:
            assert field in trace_dict, f"Missing required field: {field}"

    def test_run_id_matches(self, trace_dict):
        assert trace_dict["run_id"] == SAMPLE_RUN_ID

    def test_run_status_valid(self, trace_dict):
        assert trace_dict["run_status"] in ("completed", "failed", "partial")

    def test_instrument_and_session_present(self, trace_dict):
        assert trace_dict["instrument"] == "XAUUSD"
        assert trace_dict["session"] == "NY"

    def test_stages_non_empty(self, trace_dict):
        assert len(trace_dict["stages"]) > 0

    def test_participants_non_empty(self, trace_dict):
        assert len(trace_dict["participants"]) > 0

    def test_trace_participant_required_fields(self, trace_dict):
        required = [
            "entity_id", "entity_type", "display_name",
            "participated", "contribution", "status",
        ]
        for p in trace_dict["participants"]:
            for field in required:
                assert field in p, f"Participant missing field: {field}"

    def test_contribution_required_fields(self, trace_dict):
        required = ["role", "summary", "was_overridden"]
        for p in trace_dict["participants"]:
            contrib = p["contribution"]
            for field in required:
                assert field in contrib, f"Contribution missing field: {field}"

    def test_trace_edge_required_fields(self, trace_dict):
        required = ["from", "to", "type"]
        for edge in trace_dict["trace_edges"]:
            for field in required:
                assert field in edge, f"Edge missing field: {field}"


# ═══════════════════════════════════════════════════════════════════════════════
# AC-2 — Trace ordering: stages in ascending stage_index
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceOrdering:
    """AC-2: stages returned in ascending stage_index order."""

    def test_stages_ascending_order(self, trace_dict):
        indices = [s["stage_index"] for s in trace_dict["stages"]]
        assert indices == sorted(indices)

    def test_stage_index_monotonic(self, trace_dict):
        indices = [s["stage_index"] for s in trace_dict["stages"]]
        for i in range(1, len(indices)):
            assert indices[i] > indices[i - 1]

    def test_stage_keys_present_and_nonempty(self, trace_dict):
        for s in trace_dict["stages"]:
            assert s["stage_key"]
            assert isinstance(s["stage_key"], str)

    def test_known_stage_vocabulary(self, trace_dict):
        known = {
            "validate_input", "macro_context", "chart_setup",
            "analyst_execution", "arbiter", "logging",
        }
        for s in trace_dict["stages"]:
            assert s["stage_key"] in known, f"Unknown stage: {s['stage_key']}"


# ═══════════════════════════════════════════════════════════════════════════════
# AC-3 — Trace participant join: entity_ids map to roster
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceParticipantJoin:
    """AC-3: every entity_id in participants maps to a valid roster id."""

    def test_all_participant_ids_in_roster(self, trace_dict):
        roster_ids = get_all_roster_ids()
        for p in trace_dict["participants"]:
            assert p["entity_id"] in roster_ids, (
                f"Participant {p['entity_id']} not in roster"
            )

    def test_participant_ids_in_stage_participants_valid(self, trace_dict):
        roster_ids = get_all_roster_ids()
        for stage in trace_dict["stages"]:
            for pid in stage["participant_ids"]:
                assert pid in roster_ids, (
                    f"Stage participant {pid} not in roster"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# AC-4 — Trace edges: from/to map to roster
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceEdges:
    """AC-4: every from/to in trace_edges maps to a valid roster id."""

    def test_edge_from_valid_roster_ids(self, trace_dict):
        roster_ids = get_all_roster_ids()
        for edge in trace_dict["trace_edges"]:
            assert edge["from"] in roster_ids, (
                f"Edge from={edge['from']} not in roster"
            )

    def test_edge_to_valid_roster_ids(self, trace_dict):
        roster_ids = get_all_roster_ids()
        for edge in trace_dict["trace_edges"]:
            assert edge["to"] in roster_ids, (
                f"Edge to={edge['to']} not in roster"
            )

    def test_edge_type_valid(self, trace_dict):
        allowed = {
            "considered_by_arbiter",
            "skipped_before_arbiter",
            "failed_before_arbiter",
            "override",
        }
        for edge in trace_dict["trace_edges"]:
            assert edge["type"] in allowed, (
                f"Edge type={edge['type']} not in allowed set"
            )

    def test_from_field_serialized_as_from(self, trace_dict):
        """Confirm alias: Python from_ → JSON 'from'."""
        for edge in trace_dict["trace_edges"]:
            assert "from" in edge
            assert "from_" not in edge


# ═══════════════════════════════════════════════════════════════════════════════
# AC-5 — Trace arbiter null: null when run did not reach arbiter stage
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceArbiterNull:
    """AC-5: arbiter_summary is null when run did not reach arbiter."""

    def test_arbiter_summary_present_when_ran(self, trace_dict):
        """Sample fixture has arbiter.ran=true."""
        assert trace_dict["arbiter_summary"] is not None

    def test_arbiter_summary_null_when_not_ran(self, tmp_path):
        """Create a run_record where arbiter did not run."""
        run_record = {
            "run_id": "run_no_arbiter",
            "timestamp": "2026-03-14T11:00:00Z",
            "duration_ms": 5000,
            "request": {"instrument": "XAUUSD", "session": "NY",
                        "timeframes": ["H4"], "smoke_mode": False},
            "stages": [
                {"stage": "validate_input", "status": "ok"},
                {"stage": "analyst_execution", "status": "ok"},
            ],
            "analysts": [
                {"persona": "default_analyst", "status": "success",
                 "model": "test", "provider": "test"}
            ],
            "analysts_skipped": [],
            "analysts_failed": [],
            "arbiter": {"ran": False},
            "artifacts": {},
            "usage_summary": {},
            "warnings": [],
            "errors": [],
        }
        rr_path = tmp_path / "run_record.json"
        rr_path.write_text(json.dumps(run_record))
        resp = project_trace(
            "run_no_arbiter",
            run_record_path=rr_path,
            audit_log_path=Path("/nonexistent"),
        )
        assert resp.arbiter_summary is None
        assert resp.run_status == "partial"


# ═══════════════════════════════════════════════════════════════════════════════
# AC-6 — Trace run not found: 404 with RUN_NOT_FOUND
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceRunNotFound:
    """AC-6: missing run_id returns 404 with RUN_NOT_FOUND."""

    def test_missing_run_id_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            project_trace(
                "nonexistent_run",
                run_record_path=Path("/nonexistent/run_record.json"),
            )

    def test_404_via_endpoint(self, client):
        resp = client.get("/runs/nonexistent_run_xyz/agent-trace")
        assert resp.status_code == 404
        body = resp.json()
        detail = body.get("detail", body)
        assert detail["error"] == "RUN_NOT_FOUND"

    def test_malformed_returns_422(self, client, tmp_path):
        """Malformed run_record.json returns 422 with RUN_ARTIFACTS_MALFORMED."""
        with patch(
            "ai_analyst.api.routers.ops.project_trace",
            side_effect=TraceProjectionError("Malformed"),
        ):
            resp = client.get("/runs/bad_run/agent-trace")
            assert resp.status_code == 422
            detail = resp.json().get("detail", resp.json())
            assert detail["error"] == "RUN_ARTIFACTS_MALFORMED"


# ═══════════════════════════════════════════════════════════════════════════════
# AC-7 — Trace bounded payload
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceBoundedPayload:
    """AC-7: contribution.summary ≤ 500, override_reason ≤ 300."""

    def test_contribution_summary_bounded(self, trace_dict):
        for p in trace_dict["participants"]:
            summary = p["contribution"]["summary"]
            assert len(summary) <= 500, (
                f"summary too long ({len(summary)}): {summary[:50]}…"
            )

    def test_override_reason_bounded(self, trace_dict):
        for p in trace_dict["participants"]:
            reason = p["contribution"].get("override_reason")
            if reason is not None:
                assert len(reason) <= 300

    def test_arbiter_summary_bounded(self, trace_dict):
        arb = trace_dict["arbiter_summary"]
        if arb:
            assert len(arb["summary"]) <= 500
            if arb.get("dissent_summary"):
                assert len(arb["dissent_summary"]) <= 500

    def test_edge_summary_bounded(self, trace_dict):
        for edge in trace_dict["trace_edges"]:
            s = edge.get("summary")
            if s:
                assert len(s) <= 300

    def test_trace_edges_capped_at_50(self, trace_dict):
        assert len(trace_dict["trace_edges"]) <= 50

    def test_truncation_works(self, tmp_path):
        """Prove truncation fires when source data exceeds limits."""
        long_notes = "X" * 600
        run_record = {
            "run_id": "run_trunc",
            "timestamp": "2026-03-14T11:00:00Z",
            "duration_ms": 1000,
            "request": {"instrument": "XAUUSD", "session": "NY",
                        "timeframes": ["H4"], "smoke_mode": False},
            "stages": [{"stage": "analyst_execution", "status": "ok"}],
            "analysts": [
                {"persona": "default_analyst", "status": "success",
                 "model": "test", "provider": "test"}
            ],
            "analysts_skipped": [],
            "analysts_failed": [],
            "arbiter": {"ran": False},
            "artifacts": {},
            "usage_summary": {},
            "warnings": [],
            "errors": [],
        }
        rr_path = tmp_path / "run_record.json"
        rr_path.write_text(json.dumps(run_record))

        # Audit log with very long notes
        audit = {
            "run_id": "run_trunc",
            "analyst_outputs": [
                {"htf_bias": "bullish", "confidence": 0.8,
                 "notes": long_notes, "recommended_action": "LONG"}
            ],
            "final_verdict": None,
        }
        al_path = tmp_path / "audit.jsonl"
        al_path.write_text(json.dumps(audit))

        resp = project_trace("run_trunc", rr_path, al_path)
        for p in resp.participants:
            assert len(p.contribution.summary) <= 500


# ═══════════════════════════════════════════════════════════════════════════════
# AC-8 — Trace summary block
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceSummaryBlock:
    """AC-8: summary block has entity_count, stage_count, arbiter_override."""

    def test_summary_required_fields(self, trace_dict):
        summary = trace_dict["summary"]
        assert "entity_count" in summary
        assert "stage_count" in summary
        assert "arbiter_override" in summary

    def test_entity_count_matches_active_participants(self, trace_response):
        active = [p for p in trace_response.participants if p.participated]
        assert trace_response.summary.entity_count == len(active)

    def test_stage_count_matches(self, trace_response):
        assert trace_response.summary.stage_count == len(trace_response.stages)

    def test_arbiter_override_is_bool(self, trace_dict):
        assert isinstance(trace_dict["summary"]["arbiter_override"], bool)

    def test_final_bias_valid(self, trace_dict):
        fb = trace_dict["summary"].get("final_bias")
        if fb is not None:
            assert fb in ("bullish", "bearish", "neutral")


# ═══════════════════════════════════════════════════════════════════════════════
# AC-9 — Trace artifact refs
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceArtifactRefs:
    """AC-9: artifact_refs present with valid artifact_type and artifact_key."""

    def test_artifact_refs_present(self, trace_dict):
        assert "artifact_refs" in trace_dict
        assert len(trace_dict["artifact_refs"]) > 0

    def test_artifact_ref_shape(self, trace_dict):
        for ref in trace_dict["artifact_refs"]:
            assert "artifact_type" in ref
            assert "artifact_key" in ref
            assert isinstance(ref["artifact_type"], str)
            assert isinstance(ref["artifact_key"], str)

    def test_run_record_ref_present(self, trace_dict):
        types = [r["artifact_type"] for r in trace_dict["artifact_refs"]]
        assert "run_record" in types


# ═══════════════════════════════════════════════════════════════════════════════
# AC-18 — ResponseMeta consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceResponseMeta:
    """AC-18: ResponseMeta with version, generated_at, data_state."""

    def test_version_present(self, trace_dict):
        assert trace_dict["version"] == "2026.03"

    def test_generated_at_valid_iso(self, trace_dict):
        # Should parse without error
        datetime.fromisoformat(trace_dict["generated_at"].replace("Z", "+00:00"))

    def test_data_state_valid(self, trace_dict):
        assert trace_dict["data_state"] in ("live", "stale", "unavailable")

    def test_data_state_live_with_audit(self, trace_response):
        """With audit log, data_state should be 'live'."""
        assert trace_response.data_state == "live"

    def test_data_state_stale_without_audit(self, trace_response_no_audit):
        """Without audit log, data_state should be 'stale'."""
        assert trace_response_no_audit.data_state == "stale"

    def test_source_of_truth(self, trace_dict):
        assert trace_dict["source_of_truth"] == "run_artifacts"


# ═══════════════════════════════════════════════════════════════════════════════
# AC-19 — Error envelope: OpsErrorEnvelope for all HTTP errors
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceErrorEnvelope:
    """AC-19: all errors use OpsErrorEnvelope."""

    def test_404_is_ops_error(self, client):
        resp = client.get("/runs/does_not_exist/agent-trace")
        assert resp.status_code == 404
        detail = resp.json().get("detail", resp.json())
        assert "error" in detail
        assert "message" in detail

    def test_422_is_ops_error(self, client):
        with patch(
            "ai_analyst.api.routers.ops.project_trace",
            side_effect=TraceProjectionError("Bad data"),
        ):
            resp = client.get("/runs/bad/agent-trace")
            assert resp.status_code == 422
            detail = resp.json().get("detail", resp.json())
            assert "error" in detail
            assert "message" in detail

    def test_500_is_ops_error(self, client):
        with patch(
            "ai_analyst.api.routers.ops.project_trace",
            side_effect=RuntimeError("Unexpected"),
        ):
            resp = client.get("/runs/err/agent-trace")
            assert resp.status_code == 500
            detail = resp.json().get("detail", resp.json())
            assert detail["error"] == "TRACE_PROJECTION_FAILED"


# ═══════════════════════════════════════════════════════════════════════════════
# AC-20 — No raw dumps: no prompt text or unbounded blobs
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceNoRawDumps:
    """AC-20: no raw prompt text, full transcripts, or unbounded blobs."""

    def test_no_raw_prompt_content(self, trace_dict):
        """No field should contain typical prompt markers."""
        raw = json.dumps(trace_dict)
        prompt_markers = ["system:", "You are a", "<<SYS>>", "Human:", "Assistant:"]
        for marker in prompt_markers:
            assert marker not in raw, f"Found prompt marker: {marker}"

    def test_serialized_size_bounded(self, trace_dict):
        """Total response should be reasonable (< 50KB for test fixture)."""
        raw = json.dumps(trace_dict)
        assert len(raw) < 50_000


# ═══════════════════════════════════════════════════════════════════════════════
# AC-21 — Existing endpoints unchanged: 55/55 PR-OPS-2 baseline preserved
# ═══════════════════════════════════════════════════════════════════════════════


class TestBaselinePreserved:
    """AC-21: PR-OPS-2 roster and health endpoints still work."""

    def test_roster_still_works(self, client):
        resp = client.get("/ops/agent-roster")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "governance_layer" in data

    def test_health_still_works(self, client):
        resp = client.get("/ops/agent-health")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "entities" in data


# ═══════════════════════════════════════════════════════════════════════════════
# AC-22 — No new persistence: read-side only
# ═══════════════════════════════════════════════════════════════════════════════


class TestNoNewPersistence:
    """AC-22: no file writes in trace projection."""

    def test_trace_service_does_not_write(self, tmp_path):
        """Trace projection should not create any new files."""
        # Copy fixture to tmp
        rr_path = tmp_path / "run_record.json"
        rr_path.write_text(SAMPLE_RUN_RECORD.read_text())

        before = set(tmp_path.iterdir())
        project_trace(SAMPLE_RUN_ID, rr_path, Path("/nonexistent"))
        after = set(tmp_path.iterdir())
        assert before == after, "Trace projection created new files"


# ═══════════════════════════════════════════════════════════════════════════════
# AC-24 — Flat ResponseMeta envelope: no data/meta wrapper
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlatEnvelope:
    """AC-24: flat ResponseMeta & {} — no data/meta wrapper."""

    def test_no_data_wrapper(self, trace_dict):
        assert "data" not in trace_dict

    def test_no_meta_wrapper(self, trace_dict):
        assert "meta" not in trace_dict

    def test_version_at_top_level(self, trace_dict):
        assert "version" in trace_dict

    def test_run_id_at_top_level(self, trace_dict):
        assert "run_id" in trace_dict


# ═══════════════════════════════════════════════════════════════════════════════
# AC-25 — ID convention consistency: plain slugs, no namespace
# ═══════════════════════════════════════════════════════════════════════════════


class TestIDConvention:
    """AC-25: entity_ids use plain slug convention, no namespace."""

    def test_participant_ids_are_plain_slugs(self, trace_dict):
        for p in trace_dict["participants"]:
            eid = p["entity_id"]
            assert ":" not in eid, f"Namespaced ID found: {eid}"
            assert eid == eid.lower(), f"Non-lowercase ID: {eid}"

    def test_edge_ids_are_plain_slugs(self, trace_dict):
        for edge in trace_dict["trace_edges"]:
            for field in ("from", "to"):
                eid = edge[field]
                assert ":" not in eid
                assert eid == eid.lower()

    def test_persona_ids_mapped_correctly(self, trace_dict):
        """Bare persona names from run_record should be mapped to persona_ prefix."""
        persona_ids = [
            p["entity_id"]
            for p in trace_dict["participants"]
            if p["entity_type"] == "persona"
        ]
        for pid in persona_ids:
            assert pid.startswith("persona_"), f"Unmapped persona ID: {pid}"


# ═══════════════════════════════════════════════════════════════════════════════
# §14.5 — Arbiter override indicators
# ═══════════════════════════════════════════════════════════════════════════════


class TestArbiterOverrideIndicators:
    """§14.5: override consistency between arbiter_summary and participants."""

    def test_override_applied_explicit(self, trace_response):
        arb = trace_response.arbiter_summary
        assert arb is not None
        assert isinstance(arb.override_applied, bool)

    def test_override_count_matches_ids(self, trace_response):
        arb = trace_response.arbiter_summary
        assert arb is not None
        assert arb.override_count == len(arb.overridden_entity_ids)

    def test_overridden_ids_cross_reference(self, trace_response):
        """overridden_entity_ids should match participants with was_overridden=True."""
        arb = trace_response.arbiter_summary
        assert arb is not None
        overridden_participants = {
            p.entity_id
            for p in trace_response.participants
            if p.contribution.was_overridden
        }
        assert set(arb.overridden_entity_ids) == overridden_participants

    def test_non_overridden_participants(self, trace_response):
        """Participants NOT in override list should have was_overridden=False."""
        arb = trace_response.arbiter_summary
        assert arb is not None
        override_set = set(arb.overridden_entity_ids)
        for p in trace_response.participants:
            if p.entity_id not in override_set:
                assert not p.contribution.was_overridden, (
                    f"{p.entity_id} not in override list but was_overridden=True"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# §14.3 — Ordered trace semantics: partial run
# ═══════════════════════════════════════════════════════════════════════════════


class TestPartialRun:
    """§14.11: partial run returns run_status='partial' with available stages."""

    def test_partial_run_status(self, tmp_path):
        run_record = {
            "run_id": "run_partial",
            "timestamp": "2026-03-14T11:00:00Z",
            "duration_ms": 3000,
            "request": {"instrument": "EURUSD", "session": "London",
                        "timeframes": ["H4"], "smoke_mode": False},
            "stages": [
                {"stage": "validate_input", "status": "ok"},
                {"stage": "macro_context", "status": "ok"},
            ],
            "analysts": [],
            "analysts_skipped": [],
            "analysts_failed": [
                {"persona": "default_analyst", "status": "failed",
                 "model": "test", "provider": "test",
                 "reason": "schema_validation: bad output"}
            ],
            "arbiter": {"ran": False},
            "artifacts": {},
            "usage_summary": {},
            "warnings": [],
            "errors": [],
        }
        rr_path = tmp_path / "run_record.json"
        rr_path.write_text(json.dumps(run_record))
        resp = project_trace("run_partial", rr_path, Path("/nonexistent"))
        assert resp.run_status == "partial"
        assert len(resp.stages) == 2
        assert resp.arbiter_summary is None


class TestFailedRun:
    """Runs with errors get run_status='failed'."""

    def test_failed_run_status(self, tmp_path):
        run_record = {
            "run_id": "run_failed",
            "timestamp": "2026-03-14T11:00:00Z",
            "duration_ms": 1000,
            "request": {"instrument": "XAUUSD", "session": "NY",
                        "timeframes": ["H4"], "smoke_mode": False},
            "stages": [{"stage": "validate_input", "status": "ok"}],
            "analysts": [],
            "analysts_skipped": [],
            "analysts_failed": [],
            "arbiter": {"ran": False},
            "artifacts": {},
            "usage_summary": {},
            "warnings": [],
            "errors": ["Pipeline crashed"],
        }
        rr_path = tmp_path / "run_record.json"
        rr_path.write_text(json.dumps(run_record))
        resp = project_trace("run_failed", rr_path, Path("/nonexistent"))
        assert resp.run_status == "failed"


# ═══════════════════════════════════════════════════════════════════════════════
# Service-level: audit log degradation
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditLogDegradation:
    """Audit log missing → data_state stale, no stances, no override detail."""

    def test_no_audit_data_state_stale(self, trace_response_no_audit):
        assert trace_response_no_audit.data_state == "stale"

    def test_no_audit_participants_still_present(self, trace_response_no_audit):
        assert len(trace_response_no_audit.participants) > 0

    def test_no_audit_stances_absent(self, trace_response_no_audit):
        for p in trace_response_no_audit.participants:
            if p.entity_type == "persona":
                assert p.contribution.stance is None


# ═══════════════════════════════════════════════════════════════════════════════
# Model-level tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceEdgeAlias:
    """TraceEdge.from_ serializes as 'from' in JSON."""

    def test_from_alias_in_json(self):
        edge = TraceEdge(from_="a", to="b", type="considered_by_arbiter")
        d = edge.model_dump(by_alias=True)
        assert "from" in d
        assert "from_" not in d

    def test_from_field_accessible(self):
        edge = TraceEdge(from_="a", to="b", type="considered_by_arbiter")
        assert edge.from_ == "a"

    def test_construct_with_alias(self):
        edge = TraceEdge(**{"from": "x", "to": "y", "type": "override"})
        assert edge.from_ == "x"
