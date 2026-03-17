# ---------------------------------------------------------------------------
# Tests — Journal / Review endpoint repair (Post-Phase-8 stabilisation).
#
# Covers:
#   POST /journey/decision  — snapshot_id primary, journey_id fallback
#   GET  /journal/decisions  — { records: DecisionSnapshot[] } envelope
#   GET  /review/records     — { records: ReviewRecord[] } envelope
#
# Also verifies legacy /journey/journal and /journey/review still work.
# ---------------------------------------------------------------------------

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_journeys(tmp_path):
    """Create isolated journey directories and patch module-level paths."""
    decisions = tmp_path / "decisions"
    results = tmp_path / "results"
    drafts = tmp_path / "drafts"
    decisions.mkdir()
    results.mkdir()
    drafts.mkdir()
    return {"decisions": decisions, "results": results, "drafts": drafts}


@pytest.fixture()
def client(tmp_journeys):
    """TestClient with patched journey directories."""
    with patch("ai_analyst.api.routers.journey._DECISIONS_DIR", tmp_journeys["decisions"]), \
         patch("ai_analyst.api.routers.journey._RESULTS_DIR", tmp_journeys["results"]), \
         patch("ai_analyst.api.routers.journey._DRAFTS_DIR", tmp_journeys["drafts"]):
        from ai_analyst.api.main import app
        yield TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_DECISION_PAYLOAD = {
    "snapshot_id": "EURUSD-1710000000000",
    "instrument": "EURUSD",
    "decision": "long",
    "thesis": "Bullish momentum on H4",
    "conviction": "high",
    "notes": "Clean break of structure",
    "bootstrap_summary": {
        "arbiter_decision": "bullish",
        "arbiter_bias": "neutral",
        "analyst_verdict": "bullish",
    },
}


def _write_decision_file(decisions_dir: Path, snapshot_id: str, **overrides):
    """Write a decision JSON file directly for read-path testing."""
    record = {
        "snapshot_id": snapshot_id,
        "instrument": "XAUUSD",
        "saved_at": "2026-03-17T10:00:00Z",
        "journey_status": "frozen",
        "verdict": "bearish",
        "user_decision": "short",
        **overrides,
    }
    path = decisions_dir / f"{snapshot_id}.json"
    path.write_text(json.dumps(record, indent=2))
    return record


def _write_result_file(results_dir: Path, snapshot_id: str):
    """Write a result JSON file for has_result linkage testing."""
    record = {
        "snapshot_id": snapshot_id,
        "instrument": "XAUUSD",
        "logged_at": "2026-03-17T12:00:00Z",
        "outcome": "win",
    }
    path = results_dir / f"{snapshot_id}.json"
    path.write_text(json.dumps(record, indent=2))


# ===========================================================================
# POST /journey/decision — Write Path
# ===========================================================================


class TestSaveDecision:
    """POST /journey/decision with snapshot_id as canonical identifier."""

    def test_save_with_snapshot_id(self, client, tmp_journeys):
        """Primary path: snapshot_id accepted, file written, correct response."""
        resp = client.post("/journey/decision", json=VALID_DECISION_PAYLOAD)
        assert resp.status_code == 200

        body = resp.json()
        assert body["success"] is True
        assert body["snapshot_id"] == "EURUSD-1710000000000"
        assert "saved_at" in body
        # journey_id should NOT be in response (Finding 6)
        assert "journey_id" not in body

        # File was actually written
        written = tmp_journeys["decisions"] / "EURUSD-1710000000000.json"
        assert written.exists()

        # Stored record has DecisionSnapshot-compatible shape
        stored = json.loads(written.read_text())
        assert stored["snapshot_id"] == "EURUSD-1710000000000"
        assert stored["instrument"] == "EURUSD"
        assert stored["journey_status"] == "frozen"
        assert stored["user_decision"] == "long"
        assert stored["saved_at"] == body["saved_at"]

    def test_save_with_journey_id_fallback(self, client, tmp_journeys):
        """Legacy fallback: journey_id accepted when snapshot_id absent."""
        payload = {
            "journey_id": "legacy-id-001",
            "instrument": "GBPUSD",
            "decision": "short",
            "bootstrap_summary": {"arbiter_bias": "bearish"},
        }
        resp = client.post("/journey/decision", json=payload)
        assert resp.status_code == 200

        body = resp.json()
        assert body["success"] is True
        assert body["snapshot_id"] == "legacy-id-001"

        written = tmp_journeys["decisions"] / "legacy-id-001.json"
        assert written.exists()

    def test_save_missing_both_ids(self, client):
        """Error when neither snapshot_id nor journey_id is provided."""
        payload = {"instrument": "EURUSD", "decision": "long"}
        resp = client.post("/journey/decision", json=payload)
        assert resp.status_code == 200

        body = resp.json()
        assert body["success"] is False
        assert "snapshot_id" in body.get("error", "").lower()

    def test_verdict_derivation_arbiter_decision_preferred(self, client, tmp_journeys):
        """Verdict derived from arbiter_decision over arbiter_bias."""
        payload = {
            **VALID_DECISION_PAYLOAD,
            "snapshot_id": "verdict-test-1",
            "bootstrap_summary": {
                "arbiter_decision": "bullish",
                "arbiter_bias": "neutral",
            },
        }
        resp = client.post("/journey/decision", json=payload)
        assert resp.status_code == 200

        stored = json.loads(
            (tmp_journeys["decisions"] / "verdict-test-1.json").read_text()
        )
        assert stored["verdict"] == "bullish"

    def test_verdict_derivation_falls_back_to_bias(self, client, tmp_journeys):
        """Verdict falls back to arbiter_bias when arbiter_decision absent."""
        payload = {
            **VALID_DECISION_PAYLOAD,
            "snapshot_id": "verdict-test-2",
            "bootstrap_summary": {"arbiter_bias": "bearish"},
        }
        resp = client.post("/journey/decision", json=payload)
        assert resp.status_code == 200

        stored = json.loads(
            (tmp_journeys["decisions"] / "verdict-test-2.json").read_text()
        )
        assert stored["verdict"] == "bearish"

    def test_verdict_derivation_defaults_to_unknown(self, client, tmp_journeys):
        """Verdict defaults to 'unknown' when no bootstrap summary fields."""
        payload = {
            **VALID_DECISION_PAYLOAD,
            "snapshot_id": "verdict-test-3",
            "bootstrap_summary": {},
        }
        resp = client.post("/journey/decision", json=payload)
        assert resp.status_code == 200

        stored = json.loads(
            (tmp_journeys["decisions"] / "verdict-test-3.json").read_text()
        )
        assert stored["verdict"] == "unknown"

    def test_saved_at_is_single_canonical_timestamp(self, client, tmp_journeys):
        """saved_at is the only outward timestamp — no decided_at in response or storage."""
        resp = client.post("/journey/decision", json=VALID_DECISION_PAYLOAD)
        body = resp.json()

        assert "saved_at" in body
        assert "decided_at" not in body

        stored = json.loads(
            (tmp_journeys["decisions"] / "EURUSD-1710000000000.json").read_text()
        )
        assert "saved_at" in stored
        assert "decided_at" not in stored


# ===========================================================================
# GET /journal/decisions — Journal Read Path
# ===========================================================================


class TestJournalDecisions:
    """GET /journal/decisions returns { records: DecisionSnapshot[] } envelope."""

    def test_empty_returns_envelope(self, client):
        """Empty or missing directory returns { records: [] }, not error."""
        resp = client.get("/journal/decisions")
        assert resp.status_code == 200

        body = resp.json()
        assert "records" in body
        assert isinstance(body["records"], list)
        assert len(body["records"]) == 0

    def test_populated_returns_decision_snapshots(self, client, tmp_journeys):
        """Returns correctly shaped DecisionSnapshot records."""
        _write_decision_file(tmp_journeys["decisions"], "snap-001", saved_at="2026-03-17T10:00:00Z")
        _write_decision_file(tmp_journeys["decisions"], "snap-002", saved_at="2026-03-17T11:00:00Z")

        resp = client.get("/journal/decisions")
        assert resp.status_code == 200

        body = resp.json()
        assert "records" in body
        assert len(body["records"]) == 2

        rec = body["records"][0]
        # Verify DecisionSnapshot field presence
        assert "snapshot_id" in rec
        assert "instrument" in rec
        assert "saved_at" in rec
        assert "journey_status" in rec
        assert "verdict" in rec
        assert "user_decision" in rec
        # Verify envelope, not raw array
        assert isinstance(body, dict)

    def test_sorted_by_saved_at_descending(self, client, tmp_journeys):
        """Most recent decision appears first."""
        _write_decision_file(tmp_journeys["decisions"], "old", saved_at="2026-03-17T08:00:00Z")
        _write_decision_file(tmp_journeys["decisions"], "new", saved_at="2026-03-17T12:00:00Z")

        resp = client.get("/journal/decisions")
        records = resp.json()["records"]

        assert records[0]["snapshot_id"] == "new"
        assert records[1]["snapshot_id"] == "old"

    def test_malformed_files_skipped(self, client, tmp_journeys):
        """Malformed JSON files are skipped; valid records still returned."""
        _write_decision_file(tmp_journeys["decisions"], "good", saved_at="2026-03-17T10:00:00Z")

        # Write a malformed file
        bad_path = tmp_journeys["decisions"] / "bad.json"
        bad_path.write_text("{not valid json!!!")

        resp = client.get("/journal/decisions")
        assert resp.status_code == 200

        records = resp.json()["records"]
        assert len(records) == 1
        assert records[0]["snapshot_id"] == "good"

    def test_missing_snapshot_id_skipped(self, client, tmp_journeys):
        """Records without snapshot_id are skipped."""
        # Good record
        _write_decision_file(tmp_journeys["decisions"], "valid-001")

        # Record missing snapshot_id
        bad_record = {"instrument": "EURUSD", "saved_at": "2026-03-17T10:00:00Z"}
        (tmp_journeys["decisions"] / "no-id.json").write_text(json.dumps(bad_record))

        resp = client.get("/journal/decisions")
        records = resp.json()["records"]
        assert len(records) == 1
        assert records[0]["snapshot_id"] == "valid-001"


# ===========================================================================
# GET /review/records — Review Read Path
# ===========================================================================


class TestReviewRecords:
    """GET /review/records returns { records: ReviewRecord[] } envelope."""

    def test_empty_returns_envelope(self, client):
        """Empty or missing directory returns { records: [] }, not error."""
        resp = client.get("/review/records")
        assert resp.status_code == 200

        body = resp.json()
        assert "records" in body
        assert isinstance(body["records"], list)
        assert len(body["records"]) == 0

    def test_has_result_true_when_result_exists(self, client, tmp_journeys):
        """has_result is true when matching result file exists."""
        _write_decision_file(tmp_journeys["decisions"], "snap-with-result")
        _write_result_file(tmp_journeys["results"], "snap-with-result")

        resp = client.get("/review/records")
        records = resp.json()["records"]

        assert len(records) == 1
        assert records[0]["has_result"] is True

    def test_has_result_false_when_no_result(self, client, tmp_journeys):
        """has_result is false when no matching result file."""
        _write_decision_file(tmp_journeys["decisions"], "snap-no-result")

        resp = client.get("/review/records")
        records = resp.json()["records"]

        assert len(records) == 1
        assert records[0]["has_result"] is False

    def test_mixed_result_linkage(self, client, tmp_journeys):
        """Mixed: one decision with result, one without."""
        _write_decision_file(tmp_journeys["decisions"], "has", saved_at="2026-03-17T11:00:00Z")
        _write_result_file(tmp_journeys["results"], "has")
        _write_decision_file(tmp_journeys["decisions"], "missing", saved_at="2026-03-17T10:00:00Z")

        resp = client.get("/review/records")
        records = resp.json()["records"]

        assert len(records) == 2
        by_id = {r["snapshot_id"]: r for r in records}
        assert by_id["has"]["has_result"] is True
        assert by_id["missing"]["has_result"] is False

    def test_review_returns_envelope_not_raw_array(self, client, tmp_journeys):
        """Response is { records: [...] } envelope, not a raw array."""
        _write_decision_file(tmp_journeys["decisions"], "envelope-test")

        resp = client.get("/review/records")
        body = resp.json()

        assert isinstance(body, dict)
        assert "records" in body
        assert isinstance(body["records"], list)

    def test_review_records_include_decision_snapshot_fields(self, client, tmp_journeys):
        """ReviewRecord includes all DecisionSnapshot fields plus has_result."""
        _write_decision_file(
            tmp_journeys["decisions"], "full-check",
            instrument="EURUSD",
            verdict="bullish",
            user_decision="long",
            journey_status="frozen",
        )

        resp = client.get("/review/records")
        rec = resp.json()["records"][0]

        assert rec["snapshot_id"] == "full-check"
        assert rec["instrument"] == "EURUSD"
        assert rec["verdict"] == "bullish"
        assert rec["user_decision"] == "long"
        assert rec["journey_status"] == "frozen"
        assert "saved_at" in rec
        assert "has_result" in rec


# ===========================================================================
# Regression — Legacy endpoints still work
# ===========================================================================


class TestLegacyEndpointsPreserved:
    """Existing /journey/journal and /journey/review routes still function."""

    def test_journey_journal_still_returns_drafts(self, client, tmp_journeys):
        """GET /journey/journal still returns raw array of drafts."""
        draft = {"journey_id": "draft-1", "updated_at": "2026-03-17T09:00:00Z"}
        (tmp_journeys["drafts"] / "draft-1.json").write_text(json.dumps(draft))

        resp = client.get("/journey/journal")
        assert resp.status_code == 200

        body = resp.json()
        # Legacy endpoint returns raw array, not envelope
        assert isinstance(body, list)
        assert len(body) == 1

    def test_journey_review_still_returns_results(self, client, tmp_journeys):
        """GET /journey/review still returns raw array of results."""
        result = {"journey_id": "result-1", "logged_at": "2026-03-17T12:00:00Z"}
        (tmp_journeys["results"] / "result-1.json").write_text(json.dumps(result))

        resp = client.get("/journey/review")
        assert resp.status_code == 200

        body = resp.json()
        # Legacy endpoint returns raw array, not envelope
        assert isinstance(body, list)
        assert len(body) == 1
