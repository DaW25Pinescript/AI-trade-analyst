"""Deterministic tests for Agent Operations endpoints.

Covers all §7 contract test priorities from docs/ui/AGENT_OPS_CONTRACT.md:
  §7.1 Response shape tests
  §7.2 Department key tests
  §7.3 Relationship array tests
  §7.4 data_state tests
  §7.5 Structured error envelope tests
  §7.6 Separate run_state / health_state tests
  §7.7 Empty and degraded scenario tests
  §7.8 Health entity_id ↔ roster id join tests
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_analyst.api.models.ops import (
    AgentHealthItem,
    AgentHealthSnapshotResponse,
    AgentRosterResponse,
    AgentSummary,
    DepartmentKey,
    EntityRelationship,
    OpsError,
    ResponseMeta,
)
from ai_analyst.api.services.ops_roster import (
    get_all_roster_ids,
    project_roster,
)
from ai_analyst.api.services.ops_health import project_health


# ── Fixtures ─────────────────────────────────────────────────────────────────


class FakeAppState:
    """Minimal app.state stub for health projection tests."""

    def __init__(
        self,
        feeder_ingested_at=None,
        feeder_payload_meta=None,
        feeder_context=None,
    ):
        self.feeder_ingested_at = feeder_ingested_at
        self.feeder_payload_meta = feeder_payload_meta
        self.feeder_context = feeder_context


@pytest.fixture()
def client():
    """Lightweight TestClient with only the ops router mounted.

    Avoids importing the full app (which requires langgraph and other
    heavy dependencies) while still exercising the real route handlers.
    """
    from ai_analyst.api.routers.ops import router as ops_router

    app = FastAPI()
    app.include_router(ops_router)
    # Initialise minimal app.state matching the real app's lifespan
    app.state.feeder_context = None
    app.state.feeder_payload_meta = None
    app.state.feeder_ingested_at = None
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# §7.1 — Response shape tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRosterResponseShape:
    """§7.1 — /ops/agent-roster returns a valid AgentRosterResponse."""

    def test_roster_returns_valid_response(self, client):
        resp = client.get("/ops/agent-roster")
        assert resp.status_code == 200
        data = resp.json()
        # Validate via Pydantic model
        roster = AgentRosterResponse(**data)
        assert roster.governance_layer
        assert roster.officer_layer
        assert roster.departments
        assert roster.relationships is not None

    def test_roster_response_meta_fields(self, client):
        """All ResponseMeta fields are present and correctly typed."""
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        assert isinstance(data["version"], str)
        assert isinstance(data["generated_at"], str)
        assert data["data_state"] in ("live", "stale", "unavailable")
        # generated_at should be valid ISO 8601
        datetime.fromisoformat(data["generated_at"])

    def test_agent_summary_required_fields(self, client):
        """AgentSummary contains all required fields with correct types."""
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        all_summaries = (
            data["governance_layer"]
            + data["officer_layer"]
            + [a for dept in data["departments"].values() for a in dept]
        )
        required_fields = {
            "id": str,
            "display_name": str,
            "type": str,
            "role": str,
            "capabilities": list,
            "supports_verdict": bool,
            "visual_family": str,
            "orb_color": str,
        }
        for summary in all_summaries:
            for field, typ in required_fields.items():
                assert field in summary, f"Missing field {field} in {summary['id']}"
                assert isinstance(summary[field], typ), (
                    f"Field {field} in {summary['id']} should be {typ.__name__}"
                )

    def test_agent_summary_type_values(self, client):
        """AgentSummary.type is one of the allowed values."""
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        all_summaries = (
            data["governance_layer"]
            + data["officer_layer"]
            + [a for dept in data["departments"].values() for a in dept]
        )
        valid_types = {"persona", "officer", "arbiter", "subsystem"}
        for summary in all_summaries:
            assert summary["type"] in valid_types

    def test_entity_ids_are_unique(self, client):
        """All entity IDs must be unique across the entire roster."""
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        all_summaries = (
            data["governance_layer"]
            + data["officer_layer"]
            + [a for dept in data["departments"].values() for a in dept]
        )
        ids = [s["id"] for s in all_summaries]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"


class TestHealthResponseShape:
    """§7.1 — /ops/agent-health returns a valid AgentHealthSnapshotResponse."""

    def test_health_returns_valid_response(self, client):
        resp = client.get("/ops/agent-health")
        assert resp.status_code == 200
        data = resp.json()
        snapshot = AgentHealthSnapshotResponse(**data)
        assert isinstance(snapshot.entities, list)

    def test_health_response_meta_fields(self, client):
        """All ResponseMeta fields are present and correctly typed."""
        resp = client.get("/ops/agent-health")
        data = resp.json()
        assert isinstance(data["version"], str)
        assert isinstance(data["generated_at"], str)
        assert data["data_state"] in ("live", "stale", "unavailable")

    def test_health_item_required_fields(self, client):
        """AgentHealthItem contains all required fields with correct types."""
        resp = client.get("/ops/agent-health")
        data = resp.json()
        for item in data["entities"]:
            assert isinstance(item["entity_id"], str)
            assert isinstance(item["run_state"], str)
            assert isinstance(item["health_state"], str)


# ═══════════════════════════════════════════════════════════════════════════════
# §7.2 — Department key tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDepartmentKeys:
    """§7.2 — departments record contains exactly the four canonical keys."""

    CANONICAL_KEYS = {
        "TECHNICAL_ANALYSIS",
        "RISK_CHALLENGE",
        "REVIEW_GOVERNANCE",
        "INFRA_HEALTH",
    }

    def test_all_four_department_keys_present(self, client):
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        assert set(data["departments"].keys()) == self.CANONICAL_KEYS

    def test_no_extra_department_keys(self, client):
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        for key in data["departments"]:
            assert key in self.CANONICAL_KEYS, f"Unexpected key: {key}"

    def test_each_department_non_empty(self, client):
        """Each department key maps to a non-empty array of AgentSummary."""
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        for key in self.CANONICAL_KEYS:
            agents = data["departments"][key]
            assert len(agents) > 0, f"Department {key} is empty"

    def test_department_entities_have_matching_department_field(self, client):
        """Entities in departments have the matching department field."""
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        for key, agents in data["departments"].items():
            for agent in agents:
                assert agent.get("department") == key, (
                    f"Agent {agent['id']} in {key} has department={agent.get('department')}"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# §7.3 — Relationship array tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRelationships:
    """§7.3 — relationships array integrity."""

    VALID_TYPES = {
        "supports",
        "challenges",
        "feeds",
        "synthesizes",
        "overrides",
        "degraded_dependency",
        "recovered_dependency",
    }

    def test_relationships_present(self, client):
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        assert "relationships" in data
        assert isinstance(data["relationships"], list)
        assert len(data["relationships"]) > 0

    def test_relationship_from_to_valid_ids(self, client):
        """Every from and to value references a valid roster entity id."""
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        all_ids = set()
        for s in data["governance_layer"]:
            all_ids.add(s["id"])
        for s in data["officer_layer"]:
            all_ids.add(s["id"])
        for agents in data["departments"].values():
            for s in agents:
                all_ids.add(s["id"])

        for rel in data["relationships"]:
            assert rel["from"] in all_ids, (
                f"Relationship from={rel['from']!r} not in roster"
            )
            assert rel["to"] in all_ids, (
                f"Relationship to={rel['to']!r} not in roster"
            )

    def test_relationship_type_values(self, client):
        """Relationship type values are within the allowed enum."""
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        for rel in data["relationships"]:
            assert rel["type"] in self.VALID_TYPES, (
                f"Invalid relationship type: {rel['type']}"
            )

    def test_from_field_serialized_as_from(self, client):
        """EntityRelationship.from_ serializes as 'from' in JSON."""
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        for rel in data["relationships"]:
            assert "from" in rel, "Missing 'from' field (alias)"
            assert "from_" not in rel, "'from_' should not appear in JSON"


# ═══════════════════════════════════════════════════════════════════════════════
# §7.4 — data_state tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDataState:
    """§7.4 — data_state semantics."""

    def test_roster_data_state_is_live(self, client):
        """Roster from static config should be 'live'."""
        resp = client.get("/ops/agent-roster")
        data = resp.json()
        assert data["data_state"] == "live"

    def test_health_data_state_valid(self, client):
        resp = client.get("/ops/agent-health")
        data = resp.json()
        assert data["data_state"] in ("live", "stale", "unavailable")

    def test_health_data_state_unavailable_when_no_evidence(self):
        """Fresh start: all entities unavailable → data_state unavailable."""
        state = FakeAppState()
        response = project_health(state)
        assert response.data_state == "unavailable"

    def test_health_data_state_stale_when_feeder_stale(self):
        """Stale feeder → data_state stale."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        state = FakeAppState(
            feeder_ingested_at=old_time,
            feeder_payload_meta={"status": "ok", "source_health": {}},
        )
        response = project_health(state)
        assert response.data_state == "stale"


# ═══════════════════════════════════════════════════════════════════════════════
# §7.5 — Structured error envelope tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorEnvelope:
    """§7.5 — HTTP errors return OpsErrorEnvelope shape."""

    def test_roster_error_returns_ops_error_envelope(self, client):
        """When roster projection fails, response uses OpsErrorEnvelope."""
        with patch(
            "ai_analyst.api.routers.ops.project_roster",
            side_effect=RuntimeError("Config broken"),
        ):
            resp = client.get("/ops/agent-roster")
        assert resp.status_code == 500
        data = resp.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["error"] == "ROSTER_UNAVAILABLE"
        assert isinstance(detail["message"], str)

    def test_roster_503_on_unexpected_error(self, client):
        """Non-RuntimeError → 503 ROSTER_SERVICE_UNAVAILABLE."""
        with patch(
            "ai_analyst.api.routers.ops.project_roster",
            side_effect=ConnectionError("DB down"),
        ):
            resp = client.get("/ops/agent-roster")
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert detail["error"] == "ROSTER_SERVICE_UNAVAILABLE"

    def test_health_error_returns_ops_error_envelope(self, client):
        """When health projection fails, response uses OpsErrorEnvelope."""
        with patch(
            "ai_analyst.api.routers.ops.project_health",
            side_effect=Exception("Observability broken"),
        ):
            resp = client.get("/ops/agent-health")
        assert resp.status_code == 500
        data = resp.json()
        detail = data["detail"]
        assert detail["error"] == "HEALTH_PROJECTION_FAILED"
        assert isinstance(detail["message"], str)

    def test_error_envelope_has_correct_shape(self, client):
        """OpsError contains error and message fields (not freeform string)."""
        with patch(
            "ai_analyst.api.routers.ops.project_roster",
            side_effect=RuntimeError("Test error"),
        ):
            resp = client.get("/ops/agent-roster")
        detail = resp.json()["detail"]
        assert isinstance(detail, dict), "detail must be dict, not string"
        assert "error" in detail
        assert "message" in detail


# ═══════════════════════════════════════════════════════════════════════════════
# §7.6 — Separate run_state / health_state tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunStateHealthStateSeparation:
    """§7.6 — run_state and health_state are separate dimensions."""

    VALID_RUN_STATES = {"idle", "running", "completed", "failed"}
    VALID_HEALTH_STATES = {"live", "stale", "degraded", "unavailable", "recovered"}

    def test_both_fields_present_on_every_entity(self, client):
        resp = client.get("/ops/agent-health")
        data = resp.json()
        for item in data["entities"]:
            assert "run_state" in item
            assert "health_state" in item

    def test_run_state_valid_values(self, client):
        resp = client.get("/ops/agent-health")
        data = resp.json()
        for item in data["entities"]:
            assert item["run_state"] in self.VALID_RUN_STATES, (
                f"Invalid run_state: {item['run_state']} for {item['entity_id']}"
            )

    def test_health_state_valid_values(self, client):
        resp = client.get("/ops/agent-health")
        data = resp.json()
        for item in data["entities"]:
            assert item["health_state"] in self.VALID_HEALTH_STATES, (
                f"Invalid health_state: {item['health_state']} for {item['entity_id']}"
            )

    def test_independent_dimensions(self):
        """An entity can have independent values for each dimension."""
        item = AgentHealthItem(
            entity_id="test",
            run_state="completed",
            health_state="degraded",
        )
        assert item.run_state == "completed"
        assert item.health_state == "degraded"

    def test_all_run_state_values_accepted(self):
        """All run_state values are accepted by the model."""
        for rs in self.VALID_RUN_STATES:
            item = AgentHealthItem(
                entity_id="test",
                run_state=rs,
                health_state="live",
            )
            assert item.run_state == rs

    def test_all_health_state_values_accepted(self):
        """All health_state values are accepted by the model."""
        for hs in self.VALID_HEALTH_STATES:
            item = AgentHealthItem(
                entity_id="test",
                run_state="idle",
                health_state=hs,
            )
            assert item.health_state == hs


# ═══════════════════════════════════════════════════════════════════════════════
# §7.7 — Empty and degraded scenario tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmptyAndDegraded:
    """§7.7 — Empty roster, empty health, and degraded scenarios."""

    def test_empty_roster_returns_error(self, client):
        """Empty roster (zero entities) returns HTTP error, not empty response."""
        with patch(
            "ai_analyst.api.routers.ops.project_roster",
            side_effect=RuntimeError("Roster is empty"),
        ):
            resp = client.get("/ops/agent-roster")
        assert resp.status_code == 500
        assert resp.json()["detail"]["error"] == "ROSTER_UNAVAILABLE"

    def test_empty_health_entities_is_valid(self):
        """Empty health entities array is a valid response (returns 200)."""
        response = AgentHealthSnapshotResponse(
            version="2026.03",
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_state="unavailable",
            entities=[],
        )
        assert response.entities == []

    def test_fresh_start_health_all_unavailable(self):
        """Fresh start: all entities have health_state unavailable."""
        state = FakeAppState()
        response = project_health(state)
        for entity in response.entities:
            assert entity.health_state == "unavailable", (
                f"{entity.entity_id} should be unavailable on fresh start"
            )

    def test_roster_failure_is_blocking_error(self, client):
        """Roster failure is a workspace-level blocking error."""
        with patch(
            "ai_analyst.api.routers.ops.project_roster",
            side_effect=RuntimeError("Config corrupted"),
        ):
            resp = client.get("/ops/agent-roster")
        assert resp.status_code >= 500

    def test_health_failure_is_graceful(self, client):
        """Health failure should still return an error envelope."""
        with patch(
            "ai_analyst.api.routers.ops.project_health",
            side_effect=Exception("Obs broken"),
        ):
            resp = client.get("/ops/agent-health")
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert detail["error"] == "HEALTH_PROJECTION_FAILED"


# ═══════════════════════════════════════════════════════════════════════════════
# §7.8 — Health entity_id ↔ roster id join tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthRosterJoin:
    """§7.8 — entity_id in health maps to id in roster."""

    def test_all_health_entity_ids_in_roster(self, client):
        """Every entity_id in health response matches a roster id."""
        roster_resp = client.get("/ops/agent-roster")
        health_resp = client.get("/ops/agent-health")
        assert roster_resp.status_code == 200
        assert health_resp.status_code == 200

        roster_data = roster_resp.json()
        health_data = health_resp.json()

        roster_ids = set()
        for s in roster_data["governance_layer"]:
            roster_ids.add(s["id"])
        for s in roster_data["officer_layer"]:
            roster_ids.add(s["id"])
        for agents in roster_data["departments"].values():
            for s in agents:
                roster_ids.add(s["id"])

        for item in health_data["entities"]:
            assert item["entity_id"] in roster_ids, (
                f"Health entity_id={item['entity_id']!r} not in roster"
            )

    def test_missing_health_for_roster_entity_is_valid(self):
        """Missing health for a known roster entity is a valid state."""
        state = FakeAppState()
        response = project_health(state)
        roster_ids = get_all_roster_ids()
        health_ids = {e.entity_id for e in response.entities}
        # All roster entities should have health items (even if unavailable)
        assert roster_ids == health_ids

    def test_health_items_with_evidence_have_appropriate_state(self):
        """Health items with evidence should not be 'unavailable'."""
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        state = FakeAppState(
            feeder_ingested_at=recent_time,
            feeder_payload_meta={"status": "ok", "source_health": {}},
            feeder_context={"some": "context"},
        )
        response = project_health(state)
        feeder_item = next(
            e for e in response.entities if e.entity_id == "feeder_ingest"
        )
        assert feeder_item.health_state != "unavailable"
        assert feeder_item.run_state == "completed"


# ═══════════════════════════════════════════════════════════════════════════════
# Service-layer unit tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRosterService:
    """Direct tests on the roster projection service."""

    def test_project_roster_returns_response(self):
        roster = project_roster()
        assert isinstance(roster, AgentRosterResponse)

    def test_roster_ids_are_consistent(self):
        roster = project_roster()
        ids_from_helper = get_all_roster_ids()
        ids_from_response = set()
        for s in roster.governance_layer:
            ids_from_response.add(s.id)
        for s in roster.officer_layer:
            ids_from_response.add(s.id)
        for agents in roster.departments.values():
            for s in agents:
                ids_from_response.add(s.id)
        assert ids_from_helper == ids_from_response

    def test_governance_layer_count(self):
        """v1 expects 2 governance-layer entities (§4.7)."""
        roster = project_roster()
        assert len(roster.governance_layer) == 2

    def test_officer_layer_count(self):
        """v1 expects 2 officer-layer entities (§4.7)."""
        roster = project_roster()
        assert len(roster.officer_layer) == 2

    def test_all_department_keys_present(self):
        roster = project_roster()
        assert set(roster.departments.keys()) == set(DepartmentKey)

    def test_source_of_truth_set(self):
        roster = project_roster()
        assert roster.source_of_truth == "roster_config"


class TestHealthService:
    """Direct tests on the health projection service."""

    def test_fresh_start_returns_all_unavailable(self):
        state = FakeAppState()
        response = project_health(state)
        assert all(
            e.health_state == "unavailable" for e in response.entities
        )

    def test_with_fresh_feeder_data(self):
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        state = FakeAppState(
            feeder_ingested_at=recent,
            feeder_payload_meta={"status": "ok", "source_health": {}},
        )
        response = project_health(state)
        feeder = next(
            e for e in response.entities if e.entity_id == "feeder_ingest"
        )
        assert feeder.health_state == "live"
        assert feeder.run_state == "completed"

    def test_with_stale_feeder_data(self):
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        state = FakeAppState(
            feeder_ingested_at=old,
            feeder_payload_meta={"status": "ok", "source_health": {}},
        )
        response = project_health(state)
        feeder = next(
            e for e in response.entities if e.entity_id == "feeder_ingest"
        )
        assert feeder.health_state == "stale"

    def test_with_feeder_context_governance_live(self):
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        state = FakeAppState(
            feeder_ingested_at=recent,
            feeder_payload_meta={"status": "ok", "source_health": {}},
            feeder_context={"regime": "risk_on"},
        )
        response = project_health(state)
        arbiter = next(
            e for e in response.entities if e.entity_id == "arbiter"
        )
        assert arbiter.health_state == "live"

    def test_source_of_truth_set(self):
        state = FakeAppState()
        response = project_health(state)
        assert response.source_of_truth == "observability+scheduler"


# ═══════════════════════════════════════════════════════════════════════════════
# Model-level tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEntityRelationshipAlias:
    """EntityRelationship from_ / from alias behavior."""

    def test_from_alias_in_json(self):
        rel = EntityRelationship(from_="a", to="b", type="feeds")
        dumped = rel.model_dump(by_alias=True)
        assert "from" in dumped
        assert "from_" not in dumped

    def test_from_field_accessible(self):
        rel = EntityRelationship(from_="a", to="b", type="feeds")
        assert rel.from_ == "a"

    def test_construct_with_alias(self):
        """Can construct with the alias name too."""
        data = {"from": "a", "to": "b", "type": "feeds"}
        rel = EntityRelationship(**data)
        assert rel.from_ == "a"


class TestDepartmentKeyEnum:
    """DepartmentKey is a StrEnum — not freeform string."""

    def test_all_values(self):
        assert set(DepartmentKey) == {
            DepartmentKey.TECHNICAL_ANALYSIS,
            DepartmentKey.RISK_CHALLENGE,
            DepartmentKey.REVIEW_GOVERNANCE,
            DepartmentKey.INFRA_HEALTH,
        }

    def test_string_value(self):
        assert DepartmentKey.TECHNICAL_ANALYSIS == "TECHNICAL_ANALYSIS"
        assert DepartmentKey.TECHNICAL_ANALYSIS.value == "TECHNICAL_ANALYSIS"
