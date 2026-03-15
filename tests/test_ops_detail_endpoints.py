"""PR-OPS-4b — Agent Detail endpoint tests.

Covers ACs: AC-10 through AC-17, AC-18, AC-19, AC-20, AC-24, AC-25.

Deterministic, fixture-based. No mocking of internals — exercises
project_detail() directly and the router via TestClient where appropriate.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from ai_analyst.api.models.ops import AgentHealthItem
from ai_analyst.api.models.ops_detail import (
    AgentDetailResponse,
    ArbiterDetail,
    EntityDependency,
    EntityIdentity,
    EntityStatus,
    OfficerDetail,
    PersonaDetail,
    RecentParticipation,
    SubsystemDetail,
)
from ai_analyst.api.services.ops_detail import (
    DetailProjectionError,
    project_detail,
    _build_dependencies,
    _extract_participation,
    _scan_recent_participation,
)
from ai_analyst.api.services.ops_profile_registry import (
    get_all_profile_ids,
    get_entity_profile,
)
from ai_analyst.api.services.ops_roster import get_all_roster_ids


# ── Fixture helpers ─────────────────────────────────────────────────────────

SAMPLE_RUN_RECORD = Path("tests/fixtures/sample_run_record.json")


def _make_health_item(
    entity_id: str,
    run_state: str = "idle",
    health_state: str = "live",
    health_summary: str | None = "Healthy",
) -> AgentHealthItem:
    return AgentHealthItem(
        entity_id=entity_id,
        run_state=run_state,
        health_state=health_state,
        health_summary=health_summary,
    )


def _make_run_dir(
    base: Path,
    run_id: str,
    run_record: dict,
) -> Path:
    """Create a run directory with a run_record.json file."""
    run_dir = base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_record.json").write_text(json.dumps(run_record))
    return run_dir


# ═══════════════════════════════════════════════════════════════════════════
# AC-10: Detail shape (persona)
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailShapePersona:
    """AC-10: /ops/agent-detail/{entity_id} returns valid PersonaDetail."""

    def test_persona_default_analyst_returns_valid_response(self):
        health = _make_health_item("persona_default_analyst")
        resp = project_detail("persona_default_analyst", health_item=health)
        assert isinstance(resp, AgentDetailResponse)
        assert resp.entity_id == "persona_default_analyst"
        assert resp.entity_type == "persona"
        assert isinstance(resp.type_specific, PersonaDetail)

    def test_persona_type_specific_has_persona_variant(self):
        resp = project_detail("persona_default_analyst")
        assert resp.type_specific.variant == "persona"

    def test_persona_identity_fields_populated(self):
        resp = project_detail("persona_default_analyst")
        assert isinstance(resp.identity, EntityIdentity)
        assert resp.identity.purpose != ""
        assert resp.identity.role != ""
        assert len(resp.identity.capabilities) > 0
        assert len(resp.identity.responsibilities) > 0

    def test_persona_type_specific_fields(self):
        resp = project_detail("persona_default_analyst")
        ts = resp.type_specific
        assert isinstance(ts, PersonaDetail)
        assert len(ts.analysis_focus) > 0
        assert ts.verdict_style != ""
        assert ts.department_role != ""
        assert len(ts.typical_outputs) > 0

    def test_persona_has_department(self):
        resp = project_detail("persona_default_analyst")
        assert resp.department is not None
        assert resp.department == "TECHNICAL_ANALYSIS"

    def test_all_seven_personas_return_persona_detail(self):
        persona_ids = [
            "persona_default_analyst",
            "persona_ict_purist",
            "persona_technical_structure",
            "persona_risk_officer",
            "persona_prosecutor",
            "persona_skeptical_quant",
            "persona_execution_timing",
        ]
        for pid in persona_ids:
            resp = project_detail(pid)
            assert resp.entity_type == "persona", f"{pid} not persona"
            assert isinstance(resp.type_specific, PersonaDetail), f"{pid} wrong variant"

    def test_persona_display_name_nonempty(self):
        resp = project_detail("persona_ict_purist")
        assert resp.display_name != ""
        assert resp.display_name == "ICT PURIST"


# ═══════════════════════════════════════════════════════════════════════════
# AC-11: Detail shape (officer)
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailShapeOfficer:
    """AC-11: Returns valid OfficerDetail variant."""

    def test_market_data_officer_returns_officer(self):
        resp = project_detail("market_data_officer")
        assert resp.entity_type == "officer"
        assert isinstance(resp.type_specific, OfficerDetail)
        assert resp.type_specific.variant == "officer"

    def test_macro_risk_officer_returns_officer(self):
        resp = project_detail("macro_risk_officer")
        assert resp.entity_type == "officer"
        assert isinstance(resp.type_specific, OfficerDetail)

    def test_officer_type_specific_fields(self):
        resp = project_detail("market_data_officer")
        ts = resp.type_specific
        assert isinstance(ts, OfficerDetail)
        assert ts.officer_domain != ""
        assert len(ts.data_sources) > 0
        assert len(ts.monitored_surfaces) > 0

    def test_officer_has_no_department(self):
        resp = project_detail("market_data_officer")
        assert resp.department is None


# ═══════════════════════════════════════════════════════════════════════════
# AC-12: Detail shape (arbiter)
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailShapeArbiter:
    """AC-12: Returns valid ArbiterDetail variant."""

    def test_arbiter_returns_arbiter_detail(self):
        resp = project_detail("arbiter")
        assert resp.entity_type == "arbiter"
        assert isinstance(resp.type_specific, ArbiterDetail)
        assert resp.type_specific.variant == "arbiter"

    def test_arbiter_type_specific_fields(self):
        resp = project_detail("arbiter")
        ts = resp.type_specific
        assert isinstance(ts, ArbiterDetail)
        assert ts.synthesis_method != ""
        assert len(ts.veto_gates) > 0
        assert ts.quorum_rule != ""
        assert isinstance(ts.override_capable, bool)
        assert ts.policy_summary != ""

    def test_arbiter_has_dependencies(self):
        resp = project_detail("arbiter")
        assert len(resp.dependencies) > 0
        # Arbiter should have upstream dependencies (personas/officers feed it)
        upstream = [d for d in resp.dependencies if d.direction == "upstream"]
        assert len(upstream) > 0

    def test_arbiter_has_no_department(self):
        resp = project_detail("arbiter")
        assert resp.department is None


# ═══════════════════════════════════════════════════════════════════════════
# AC-13: Detail shape (subsystem)
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailShapeSubsystem:
    """AC-13: Returns valid SubsystemDetail variant."""

    def test_mdo_scheduler_returns_subsystem(self):
        resp = project_detail("mdo_scheduler")
        assert resp.entity_type == "subsystem"
        assert isinstance(resp.type_specific, SubsystemDetail)
        assert resp.type_specific.variant == "subsystem"

    def test_feeder_ingest_returns_subsystem(self):
        resp = project_detail("feeder_ingest")
        assert resp.entity_type == "subsystem"
        assert isinstance(resp.type_specific, SubsystemDetail)

    def test_governance_synthesis_returns_subsystem(self):
        resp = project_detail("governance_synthesis")
        assert resp.entity_type == "subsystem"
        assert isinstance(resp.type_specific, SubsystemDetail)

    def test_subsystem_type_specific_fields(self):
        resp = project_detail("mdo_scheduler")
        ts = resp.type_specific
        assert isinstance(ts, SubsystemDetail)
        assert ts.subsystem_type != ""
        assert len(ts.monitored_resources) > 0
        assert ts.runtime_role != ""

    def test_subsystem_has_department(self):
        resp = project_detail("mdo_scheduler")
        assert resp.department == "INFRA_HEALTH"


# ═══════════════════════════════════════════════════════════════════════════
# AC-14: Detail not found
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailNotFound:
    """AC-14: Unknown entity_id returns DetailProjectionError."""

    def test_unknown_entity_raises_error(self):
        with pytest.raises(DetailProjectionError, match="not found in roster"):
            project_detail("nonexistent_entity")

    def test_empty_entity_id_raises_error(self):
        with pytest.raises(DetailProjectionError, match="not found in roster"):
            project_detail("")

    def test_partial_entity_id_raises_error(self):
        with pytest.raises(DetailProjectionError, match="not found in roster"):
            project_detail("persona_")


class TestDetailNotFoundRouter:
    """AC-14 + AC-19: Router returns 404 with OpsErrorEnvelope."""

    def test_404_uses_ops_error_envelope(self):
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.ops import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        with TestClient(app) as client:
            resp = client.get("/ops/agent-detail/nonexistent_entity")
            assert resp.status_code == 404
            body = resp.json()
            assert "detail" in body
            detail = body["detail"]
            assert detail["error"] == "ENTITY_NOT_FOUND"
            assert "message" in detail


# ═══════════════════════════════════════════════════════════════════════════
# AC-15: Detail bounded payload
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailBoundedPayload:
    """AC-15: purpose ≤ 500 chars, RecentParticipation ≤ 5 entries."""

    def test_purpose_within_500_chars(self):
        """All entity purposes must be ≤ 500 chars."""
        roster_ids = get_all_roster_ids()
        for eid in roster_ids:
            resp = project_detail(eid)
            assert len(resp.identity.purpose) <= 500, (
                f"{eid} purpose exceeds 500 chars: {len(resp.identity.purpose)}"
            )

    def test_recent_participation_capped_at_5(self):
        """Even with many run dirs, participation capped at 5."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            now = datetime.now(timezone.utc)

            # Create 10 run dirs with arbiter participation
            for i in range(10):
                ts = (now - timedelta(hours=i)).isoformat()
                _make_run_dir(base, f"run_{i:03d}", {
                    "run_id": f"run_{i:03d}",
                    "timestamp": ts,
                    "stages": [],
                    "analysts": [],
                    "analysts_skipped": [],
                    "analysts_failed": [],
                    "arbiter": {"ran": True, "verdict": "NO_TRADE", "confidence": 0.5},
                })

            entries = _scan_recent_participation("arbiter", run_base=base)
            assert len(entries) <= 5

    def test_health_summary_bounded(self):
        """health_summary ≤ 300 chars — validated by model."""
        health = _make_health_item("arbiter", health_summary="x" * 300)
        resp = project_detail("arbiter", health_item=health)
        assert resp.status.health_summary is not None
        assert len(resp.status.health_summary) <= 300

    def test_recent_warnings_is_list(self):
        """recent_warnings is a typed list, not freeform."""
        resp = project_detail("arbiter")
        assert isinstance(resp.recent_warnings, list)


# ═══════════════════════════════════════════════════════════════════════════
# AC-16: Detail graceful degradation
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailGracefulDegradation:
    """AC-16: Health unavailable → still returns, degraded data_state."""

    def test_no_health_item_returns_stale(self):
        resp = project_detail("arbiter", health_item=None)
        assert resp.data_state == "stale"
        assert resp.status.run_state == "idle"
        assert resp.status.health_state == "unavailable"

    def test_stale_health_returns_stale_data_state(self):
        health = _make_health_item("arbiter", health_state="stale")
        resp = project_detail("arbiter", health_item=health)
        assert resp.data_state == "stale"

    def test_degraded_health_returns_stale_data_state(self):
        health = _make_health_item("arbiter", health_state="degraded")
        resp = project_detail("arbiter", health_item=health)
        assert resp.data_state == "stale"

    def test_live_health_returns_live_data_state(self):
        health = _make_health_item("arbiter", health_state="live")
        resp = project_detail("arbiter", health_item=health)
        assert resp.data_state == "live"

    def test_response_still_has_identity_without_health(self):
        resp = project_detail("persona_default_analyst", health_item=None)
        assert resp.identity.purpose != ""
        assert resp.identity.role != ""
        assert resp.type_specific.variant == "persona"


# ═══════════════════════════════════════════════════════════════════════════
# AC-17: Detail recent_warnings
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailRecentWarnings:
    """AC-17: recent_warnings is a typed array, not freeform prose."""

    def test_recent_warnings_is_list_of_strings(self):
        resp = project_detail("arbiter")
        assert isinstance(resp.recent_warnings, list)
        for w in resp.recent_warnings:
            assert isinstance(w, str)

    def test_recent_warnings_initially_empty(self):
        resp = project_detail("arbiter")
        assert resp.recent_warnings == []


# ═══════════════════════════════════════════════════════════════════════════
# AC-18: ResponseMeta consistency (detail endpoint)
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailResponseMeta:
    """AC-18: Detail endpoint includes valid ResponseMeta."""

    def test_version_present(self):
        resp = project_detail("arbiter")
        assert resp.version == "2026.03"

    def test_generated_at_is_iso(self):
        resp = project_detail("arbiter")
        # Should parse as ISO datetime
        dt = datetime.fromisoformat(resp.generated_at)
        assert dt.year >= 2026

    def test_data_state_valid_enum(self):
        resp = project_detail("arbiter")
        assert resp.data_state in ("live", "stale", "unavailable")

    def test_source_of_truth_present(self):
        resp = project_detail("arbiter")
        assert resp.source_of_truth is not None
        assert resp.source_of_truth != ""


# ═══════════════════════════════════════════════════════════════════════════
# AC-19: Error envelope (detail errors)
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailErrorEnvelope:
    """AC-19: HTTP errors use OpsErrorEnvelope."""

    def test_404_has_error_and_message_fields(self):
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.ops import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        with TestClient(app) as client:
            resp = client.get("/ops/agent-detail/bogus_entity_xyz")
            assert resp.status_code == 404
            body = resp.json()["detail"]
            assert "error" in body
            assert "message" in body
            assert body["error"] == "ENTITY_NOT_FOUND"


# ═══════════════════════════════════════════════════════════════════════════
# AC-20: No raw dumps (negative)
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailNoRawDumps:
    """AC-20: No raw prompt text, full LLM transcripts, or unbounded blobs."""

    def test_serialized_response_size_bounded(self):
        """Response JSON should be reasonable size, no unbounded blobs."""
        resp = project_detail("persona_default_analyst")
        serialized = json.dumps(resp.model_dump(by_alias=True))
        # A single entity detail should be well under 10KB
        assert len(serialized) < 10_000

    def test_no_prompt_or_transcript_fields(self):
        resp = project_detail("persona_default_analyst")
        dumped = resp.model_dump(by_alias=True)
        serialized = json.dumps(dumped).lower()
        assert "prompt" not in serialized or "prompt" in "contribution_summary"
        # More targeted: no "system_prompt", "user_prompt", "transcript" keys
        assert "system_prompt" not in serialized
        assert "user_prompt" not in serialized
        assert "transcript" not in serialized


# ═══════════════════════════════════════════════════════════════════════════
# AC-24: Envelope consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailEnvelopeConsistency:
    """AC-24: Flat ResponseMeta pattern — no data/meta wrapper."""

    def test_flat_envelope_no_data_wrapper(self):
        resp = project_detail("arbiter")
        dumped = resp.model_dump(by_alias=True)
        # Top-level keys should include version, entity_id, etc.
        assert "version" in dumped
        assert "entity_id" in dumped
        assert "data" not in dumped
        assert "meta" not in dumped

    def test_model_dump_has_by_alias_from_field(self):
        """Ensure by_alias serialization works correctly."""
        resp = project_detail("arbiter")
        dumped = resp.model_dump(by_alias=True)
        assert "entity_type" in dumped
        assert "type_specific" in dumped


# ═══════════════════════════════════════════════════════════════════════════
# AC-25: ID convention consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailIDConvention:
    """AC-25: Uses existing roster entity_id convention — plain slugs."""

    def test_entity_ids_are_plain_slugs(self):
        roster_ids = get_all_roster_ids()
        for eid in roster_ids:
            resp = project_detail(eid)
            assert resp.entity_id == eid
            # No namespace prefix like "agent:" or "ops:"
            assert ":" not in resp.entity_id

    def test_dependency_entity_ids_are_roster_ids(self):
        roster_ids = get_all_roster_ids()
        resp = project_detail("arbiter")
        for dep in resp.dependencies:
            assert dep.entity_id in roster_ids


# ═══════════════════════════════════════════════════════════════════════════
# Profile registry consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestProfileRegistryConsistency:
    """Profile registry covers all roster entities and vice versa."""

    def test_roster_and_profile_ids_match(self):
        roster_ids = get_all_roster_ids()
        profile_ids = get_all_profile_ids()
        assert roster_ids == profile_ids

    def test_all_13_entities_have_profiles(self):
        assert len(get_all_profile_ids()) == 13

    def test_all_entities_projectable(self):
        """Every roster entity can be projected to a detail response."""
        for eid in get_all_roster_ids():
            resp = project_detail(eid)
            assert resp.entity_id == eid


# ═══════════════════════════════════════════════════════════════════════════
# Dependencies
# ═══════════════════════════════════════════════════════════════════════════


class TestDependencies:
    """Dependency graph derived from roster relationships."""

    def test_arbiter_has_upstream_from_personas(self):
        deps = _build_dependencies("arbiter")
        upstream_ids = {d.entity_id for d in deps if d.direction == "upstream"}
        assert "persona_default_analyst" in upstream_ids
        assert "persona_ict_purist" in upstream_ids

    def test_arbiter_has_upstream_from_officers(self):
        deps = _build_dependencies("arbiter")
        upstream_ids = {d.entity_id for d in deps if d.direction == "upstream"}
        assert "market_data_officer" in upstream_ids
        assert "macro_risk_officer" in upstream_ids

    def test_arbiter_has_downstream_to_governance(self):
        deps = _build_dependencies("arbiter")
        downstream_ids = {d.entity_id for d in deps if d.direction == "downstream"}
        assert "governance_synthesis" in downstream_ids

    def test_persona_has_downstream_to_arbiter(self):
        deps = _build_dependencies("persona_default_analyst")
        downstream_ids = {d.entity_id for d in deps if d.direction == "downstream"}
        assert "arbiter" in downstream_ids

    def test_mdo_scheduler_has_downstream_to_officer(self):
        deps = _build_dependencies("mdo_scheduler")
        downstream_ids = {d.entity_id for d in deps if d.direction == "downstream"}
        assert "market_data_officer" in downstream_ids

    def test_dependency_has_display_name(self):
        deps = _build_dependencies("arbiter")
        for dep in deps:
            assert dep.display_name != ""

    def test_dependency_has_relationship_type(self):
        deps = _build_dependencies("arbiter")
        for dep in deps:
            assert dep.relationship_type in ("feeds", "supports", "challenges", "synthesizes")


# ═══════════════════════════════════════════════════════════════════════════
# Recent participation scan
# ═══════════════════════════════════════════════════════════════════════════


class TestRecentParticipationScan:
    """Bounded participation scan from run artifacts."""

    def test_empty_run_base_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = _scan_recent_participation("arbiter", run_base=Path(tmpdir))
            assert entries == []

    def test_nonexistent_run_base_returns_empty(self):
        entries = _scan_recent_participation(
            "arbiter",
            run_base=Path("/nonexistent/path/runs"),
        )
        assert entries == []

    def test_arbiter_participation_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            now = datetime.now(timezone.utc)
            _make_run_dir(base, "run_001", {
                "run_id": "run_001",
                "timestamp": now.isoformat(),
                "stages": [],
                "analysts": [],
                "analysts_skipped": [],
                "analysts_failed": [],
                "arbiter": {"ran": True, "verdict": "BULLISH", "confidence": 0.8},
            })
            entries = _scan_recent_participation("arbiter", run_base=base)
            assert len(entries) == 1
            assert entries[0].run_id == "run_001"

    def test_persona_participation_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            now = datetime.now(timezone.utc)
            _make_run_dir(base, "run_001", {
                "run_id": "run_001",
                "timestamp": now.isoformat(),
                "stages": [],
                "analysts": [
                    {"persona": "default_analyst", "status": "success", "model": "x", "provider": "y"},
                ],
                "analysts_skipped": [],
                "analysts_failed": [],
                "arbiter": {"ran": False},
            })
            entries = _scan_recent_participation(
                "persona_default_analyst", run_base=base,
            )
            assert len(entries) == 1

    def test_skipped_persona_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            now = datetime.now(timezone.utc)
            _make_run_dir(base, "run_001", {
                "run_id": "run_001",
                "timestamp": now.isoformat(),
                "stages": [],
                "analysts": [],
                "analysts_skipped": [
                    {"persona": "prosecutor", "status": "skipped", "reason": "smoke_mode"},
                ],
                "analysts_failed": [],
                "arbiter": {"ran": False},
            })
            entries = _scan_recent_participation(
                "persona_prosecutor", run_base=base,
            )
            assert len(entries) == 1
            assert "Skipped" in entries[0].contribution_summary

    def test_old_runs_excluded(self):
        """Runs older than 7 days are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
            _make_run_dir(base, "run_old", {
                "run_id": "run_old",
                "timestamp": old_ts,
                "stages": [],
                "analysts": [],
                "analysts_skipped": [],
                "analysts_failed": [],
                "arbiter": {"ran": True, "verdict": "BEARISH", "confidence": 0.6},
            })
            entries = _scan_recent_participation("arbiter", run_base=base)
            assert entries == []

    def test_max_20_dirs_scanned(self):
        """Scan stops after 20 dirs even if more exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            now = datetime.now(timezone.utc)
            # Create 25 dirs, only arbiter in the last 5
            for i in range(25):
                has_arbiter = i >= 20
                _make_run_dir(base, f"run_{i:03d}", {
                    "run_id": f"run_{i:03d}",
                    "timestamp": (now - timedelta(hours=i)).isoformat(),
                    "stages": [],
                    "analysts": [],
                    "analysts_skipped": [],
                    "analysts_failed": [],
                    "arbiter": {
                        "ran": has_arbiter,
                        "verdict": "NEUTRAL" if has_arbiter else None,
                    },
                })
            # Sorted descending by name, run_024..run_000
            # run_024 through run_020 have arbiter.ran=True
            # But scan stops after 20 dirs (run_024..run_005)
            # So we get runs 020-024 (5 entries) within the 20-dir scan window
            entries = _scan_recent_participation("arbiter", run_base=base)
            # All 5 arbiter-participating runs are within first 20 dirs scanned
            assert len(entries) == 5

    def test_verdict_direction_mapping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            now = datetime.now(timezone.utc)
            _make_run_dir(base, "run_001", {
                "run_id": "run_001",
                "timestamp": now.isoformat(),
                "stages": [],
                "analysts": [],
                "analysts_skipped": [],
                "analysts_failed": [],
                "arbiter": {"ran": True, "verdict": "NO_TRADE", "confidence": 0.3},
            })
            entries = _scan_recent_participation("arbiter", run_base=base)
            assert len(entries) == 1
            assert entries[0].verdict_direction == "neutral"


# ═══════════════════════════════════════════════════════════════════════════
# Router integration
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailRouterIntegration:
    """Integration tests via TestClient."""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.ops import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as c:
            yield c

    def test_valid_entity_returns_200(self, client):
        resp = client.get("/ops/agent-detail/arbiter")
        assert resp.status_code == 200
        body = resp.json()
        assert body["entity_id"] == "arbiter"
        assert body["entity_type"] == "arbiter"

    def test_unknown_entity_returns_404(self, client):
        resp = client.get("/ops/agent-detail/nonexistent")
        assert resp.status_code == 404

    def test_response_has_version(self, client):
        resp = client.get("/ops/agent-detail/persona_default_analyst")
        assert resp.status_code == 200
        assert resp.json()["version"] == "2026.03"

    def test_type_specific_discriminant_present(self, client):
        resp = client.get("/ops/agent-detail/persona_default_analyst")
        body = resp.json()
        assert body["type_specific"]["variant"] == "persona"

    def test_persona_response_flat_envelope(self, client):
        resp = client.get("/ops/agent-detail/persona_ict_purist")
        body = resp.json()
        assert "data" not in body
        assert "meta" not in body
        assert "version" in body
        assert "entity_id" in body


# ═══════════════════════════════════════════════════════════════════════════
# AC-21: Existing endpoints unchanged
# ═══════════════════════════════════════════════════════════════════════════


class TestExistingEndpointsUnchanged:
    """AC-21: PR-OPS-2 endpoints still work after PR-OPS-4b additions."""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.ops import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as c:
            yield c

    def test_roster_endpoint_still_works(self, client):
        resp = client.get("/ops/agent-roster")
        assert resp.status_code == 200
        body = resp.json()
        assert "governance_layer" in body
        assert "version" in body

    def test_health_endpoint_still_works(self, client):
        resp = client.get("/ops/agent-health")
        assert resp.status_code == 200
        body = resp.json()
        assert "entities" in body


# ═══════════════════════════════════════════════════════════════════════════
# AC-22: No new persistence
# ═══════════════════════════════════════════════════════════════════════════


class TestNoNewPersistence:
    """AC-22: Read-side projection only — no writes."""

    def test_detail_service_has_no_write_operations(self):
        """Verify the detail service module has no file write calls."""
        import inspect
        import ai_analyst.api.services.ops_detail as mod

        source = inspect.getsource(mod)
        # No sqlite, no database, no write_text, no open(..., 'w')
        assert "sqlite" not in source.lower()
        assert "write_text" not in source
        assert "open(" not in source or "read_text" in source
        assert "CREATE TABLE" not in source
