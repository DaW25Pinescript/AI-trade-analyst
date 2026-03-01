"""
Schema round-trip contract test.

Loads sample artefacts from examples/ and fixtures/, validates every enum
field against docs/schema/enums.json, asserts ticketId alignment between
the sample ticket and AAR, and validates the FinalVerdict fixture against
the Pydantic model.

No live LLM calls — all inputs are deterministic JSON files.
"""
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
ENUMS_PATH = REPO_ROOT / "docs" / "schema" / "enums.json"
TICKET_PATH = REPO_ROOT / "examples" / "sample_ticket.json"
AAR_PATH = REPO_ROOT / "examples" / "sample_aar.json"
VERDICT_FIXTURE = Path(__file__).parent / "fixtures" / "sample_final_verdict.json"


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def enums():
    return json.loads(ENUMS_PATH.read_text())


@pytest.fixture(scope="module")
def sample_ticket():
    return json.loads(TICKET_PATH.read_text())


@pytest.fixture(scope="module")
def sample_aar():
    return json.loads(AAR_PATH.read_text())


@pytest.fixture(scope="module")
def sample_verdict():
    return json.loads(VERDICT_FIXTURE.read_text())


# ── enums.json structural sanity ──────────────────────────────────────────────

def test_enums_json_has_expected_namespaces(enums):
    assert "ticket" in enums, "enums.json missing 'ticket' namespace"
    assert "aar" in enums, "enums.json missing 'aar' namespace"


def test_enums_json_ticket_has_required_keys(enums):
    required = [
        "decisionMode", "ticketType", "entryType", "entryTrigger",
        "confirmationTF", "timeInForce", "gateStatus", "waitReasonCode",
        "stopLogic", "checklist.htfState", "checklist.conviction",
    ]
    for key in required:
        assert key in enums["ticket"], f"enums.json ticket missing key: {key}"


def test_enums_json_aar_has_required_keys(enums):
    required = ["outcomeEnum", "verdictEnum", "exitReasonEnum", "failureReasonCodes", "psychologicalTag"]
    for key in required:
        assert key in enums["aar"], f"enums.json aar missing key: {key}"


# ── ticket enum field validation ──────────────────────────────────────────────

def test_ticket_top_level_enum_fields_are_valid(sample_ticket, enums):
    """Every present top-level enum field in sample_ticket must be in enums.json."""
    t_enums = enums["ticket"]
    checks = [
        ("decisionMode",  "decisionMode"),
        ("ticketType",    "ticketType"),
        ("entryType",     "entryType"),
        ("entryTrigger",  "entryTrigger"),
        ("confirmationTF","confirmationTF"),
        ("timeInForce",   "timeInForce"),
    ]
    for field, enum_key in checks:
        if field in sample_ticket:
            assert sample_ticket[field] in t_enums[enum_key], (
                f"sample_ticket.{field}={sample_ticket[field]!r} "
                f"not in enums.json ticket.{enum_key}"
            )


def test_ticket_gate_enum_fields_are_valid(sample_ticket, enums):
    if "gate" not in sample_ticket:
        pytest.skip("sample_ticket has no gate field")
    t_enums = enums["ticket"]
    gate = sample_ticket["gate"]
    assert gate["status"] in t_enums["gateStatus"], (
        f"gate.status={gate['status']!r} not in enums.json ticket.gateStatus"
    )
    assert gate["waitReasonCode"] in t_enums["waitReasonCode"], (
        f"gate.waitReasonCode={gate['waitReasonCode']!r} not in enums.json ticket.waitReasonCode"
    )


def test_ticket_stop_logic_is_valid(sample_ticket, enums):
    if "stop" not in sample_ticket:
        pytest.skip("sample_ticket has no stop field")
    logic = sample_ticket["stop"]["logic"]
    assert logic in enums["ticket"]["stopLogic"], (
        f"stop.logic={logic!r} not in enums.json ticket.stopLogic"
    )


def test_ticket_checklist_enum_fields_are_valid(sample_ticket, enums):
    if "checklist" not in sample_ticket:
        pytest.skip("sample_ticket has no checklist field")
    c = sample_ticket["checklist"]
    t_enums = enums["ticket"]
    checks = [
        ("htfState",         "checklist.htfState"),
        ("htfLocation",      "checklist.htfLocation"),
        ("ltfAlignment",     "checklist.ltfAlignment"),
        ("liquidityContext", "checklist.liquidityContext"),
        ("volRisk",          "checklist.volRisk"),
        ("execQuality",      "checklist.execQuality"),
        ("conviction",       "checklist.conviction"),
        ("edgeTag",          "checklist.edgeTag"),
    ]
    for field, enum_key in checks:
        if field in c:
            assert c[field] in t_enums[enum_key], (
                f"checklist.{field}={c[field]!r} not in enums.json ticket.{enum_key}"
            )


# ── aar enum field validation ─────────────────────────────────────────────────

def test_aar_enum_fields_are_valid(sample_aar, enums):
    """Every enum field in sample_aar must be in enums.json aar namespace."""
    a_enums = enums["aar"]
    assert sample_aar["outcomeEnum"] in a_enums["outcomeEnum"], (
        f"aar.outcomeEnum={sample_aar['outcomeEnum']!r} not in enums.json"
    )
    assert sample_aar["verdictEnum"] in a_enums["verdictEnum"], (
        f"aar.verdictEnum={sample_aar['verdictEnum']!r} not in enums.json"
    )
    assert sample_aar["exitReasonEnum"] in a_enums["exitReasonEnum"], (
        f"aar.exitReasonEnum={sample_aar['exitReasonEnum']!r} not in enums.json"
    )
    assert sample_aar["psychologicalTag"] in a_enums["psychologicalTag"], (
        f"aar.psychologicalTag={sample_aar['psychologicalTag']!r} not in enums.json"
    )
    for code in sample_aar.get("failureReasonCodes", []):
        assert code in a_enums["failureReasonCodes"], (
            f"failureReasonCode={code!r} not in enums.json aar.failureReasonCodes"
        )


# ── cross-document field alignment ───────────────────────────────────────────

def test_ticket_aar_ticketid_alignment(sample_ticket, sample_aar):
    """sample_ticket.ticketId must match sample_aar.ticketId."""
    assert sample_ticket["ticketId"] == sample_aar["ticketId"], (
        f"ticketId mismatch: ticket={sample_ticket['ticketId']!r}, "
        f"aar={sample_aar['ticketId']!r}"
    )


# ── FinalVerdict fixture round-trip ──────────────────────────────────────────

def test_final_verdict_fixture_loads_and_validates(sample_verdict):
    """FinalVerdict fixture must parse cleanly through the Pydantic model."""
    from ai_analyst.models.arbiter_output import FinalVerdict

    verdict = FinalVerdict.model_validate(sample_verdict)
    assert verdict.decision in ("ENTER_LONG", "ENTER_SHORT", "WAIT_FOR_CONFIRMATION", "NO_TRADE")
    assert 0.0 <= verdict.overall_confidence <= 1.0
    assert verdict.analyst_agreement_pct >= 0
    assert verdict.audit_log.analysts_valid <= verdict.audit_log.analysts_received


def test_final_verdict_decision_consistent_with_ticket_mode(sample_ticket, sample_verdict):
    """
    The CONDITIONAL ticket (sample_ticket) is paired with an ENTER_LONG verdict
    (sample_final_verdict). Both must be in their respective valid sets and the
    specific pairing must hold for this deterministic fixture.
    """
    valid_ticket_modes = {"LONG", "SHORT", "WAIT", "CONDITIONAL"}
    valid_verdict_decisions = {"ENTER_LONG", "ENTER_SHORT", "WAIT_FOR_CONFIRMATION", "NO_TRADE"}

    assert sample_ticket["decisionMode"] in valid_ticket_modes
    assert sample_verdict["decision"] in valid_verdict_decisions

    # Specific fixture contract: CONDITIONAL ticket → ENTER_LONG verdict
    assert sample_ticket["decisionMode"] == "CONDITIONAL"
    assert sample_verdict["decision"] == "ENTER_LONG"
