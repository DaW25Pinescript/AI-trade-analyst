"""
Pydantic schema validation tests.

Covers:
- Valid analyst outputs pass validation.
- The NO_TRADE enforcement rule fires on setup_valid=false, low confidence, and disqualifiers.
- FinalVerdict schema validates correctly.
- GroundTruthPacket immutability (frozen model).
"""
import pytest
from pydantic import ValidationError
from ..models.analyst_output import AnalystOutput, KeyLevels
from ..models.arbiter_output import FinalVerdict, ApprovedSetup, AuditLog
from ..models.ground_truth import GroundTruthPacket, RiskConstraints, MarketContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_analyst_payload(**overrides) -> dict:
    base = {
        "htf_bias": "bearish",
        "structure_state": "continuation",
        "key_levels": {"premium": ["1950–1955"], "discount": ["1910–1915"]},
        "setup_valid": True,
        "setup_type": "liquidity_sweep_reversal",
        "entry_model": "Pullback to FVG on 15m after sweep",
        "invalidation": "Close above 1955",
        "disqualifiers": [],
        "sweep_status": "yes — bearish sweep of 1948 highs",
        "fvg_zones": ["1935–1938"],
        "displacement_quality": "strong",
        "confidence": 0.72,
        "rr_estimate": 2.8,
        "notes": "Clean sweep + displacement. HTF and LTF aligned bearish.",
        "recommended_action": "SHORT",
    }
    base.update(overrides)
    return base


def _valid_verdict_payload(**overrides) -> dict:
    base = {
        "final_bias": "bearish",
        "decision": "ENTER_SHORT",
        "approved_setups": [
            {
                "type": "liquidity_sweep_reversal",
                "entry_zone": "1935–1938",
                "stop": "Close above 1955",
                "targets": ["1920", "1910"],
                "rr_estimate": 2.8,
                "confidence": 0.68,
            }
        ],
        "no_trade_conditions": [],
        "overall_confidence": 0.68,
        "analyst_agreement_pct": 75,
        "risk_override_applied": False,
        "arbiter_notes": "Three of four analysts agree on bearish setup. Strong sweep evidence.",
        "audit_log": {
            "run_id": "test-run-001",
            "analysts_received": 4,
            "analysts_valid": 3,
            "htf_consensus": True,
            "setup_consensus": True,
            "risk_override": False,
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AnalystOutput tests
# ---------------------------------------------------------------------------

class TestAnalystOutput:
    def test_valid_short_setup(self):
        output = AnalystOutput(**_valid_analyst_payload())
        assert output.recommended_action == "SHORT"
        assert output.setup_valid is True

    def test_valid_no_trade_all_conditions(self):
        """A properly formed NO_TRADE with all three triggers passes."""
        output = AnalystOutput(**_valid_analyst_payload(
            setup_valid=False,
            confidence=0.3,
            disqualifiers=["no displacement after sweep"],
            recommended_action="NO_TRADE",
        ))
        assert output.recommended_action == "NO_TRADE"

    def test_setup_false_must_be_no_trade(self):
        with pytest.raises(ValidationError, match="NO_TRADE"):
            AnalystOutput(**_valid_analyst_payload(
                setup_valid=False,
                recommended_action="SHORT",  # invalid
            ))

    def test_low_confidence_must_be_no_trade(self):
        with pytest.raises(ValidationError, match="NO_TRADE"):
            AnalystOutput(**_valid_analyst_payload(
                confidence=0.44,
                recommended_action="LONG",  # invalid
            ))

    def test_confidence_boundary_at_045(self):
        """confidence=0.45 is the exact threshold — just at the limit is valid."""
        output = AnalystOutput(**_valid_analyst_payload(
            confidence=0.45,
            recommended_action="SHORT",
            disqualifiers=[],
        ))
        assert output.confidence == 0.45

    def test_disqualifiers_must_be_no_trade(self):
        with pytest.raises(ValidationError, match="NO_TRADE"):
            AnalystOutput(**_valid_analyst_payload(
                disqualifiers=["HTF ranging — continuation disallowed"],
                recommended_action="LONG",  # invalid
            ))

    def test_disqualifiers_with_no_trade_is_valid(self):
        output = AnalystOutput(**_valid_analyst_payload(
            setup_valid=False,
            confidence=0.3,
            disqualifiers=["range market", "no sweep"],
            recommended_action="NO_TRADE",
        ))
        assert output.recommended_action == "NO_TRADE"

    def test_invalid_htf_bias_rejected(self):
        with pytest.raises(ValidationError):
            AnalystOutput(**_valid_analyst_payload(htf_bias="sideways"))  # not in Literal

    def test_invalid_recommended_action_rejected(self):
        with pytest.raises(ValidationError):
            AnalystOutput(**_valid_analyst_payload(recommended_action="MAYBE"))


# ---------------------------------------------------------------------------
# FinalVerdict tests
# ---------------------------------------------------------------------------

class TestFinalVerdict:
    def test_valid_enter_short_verdict(self):
        verdict = FinalVerdict(**_valid_verdict_payload())
        assert verdict.decision == "ENTER_SHORT"

    def test_valid_no_trade_verdict(self):
        verdict = FinalVerdict(**_valid_verdict_payload(
            decision="NO_TRADE",
            approved_setups=[],
            no_trade_conditions=["insufficient analyst consensus"],
            risk_override_applied=True,
        ))
        assert verdict.decision == "NO_TRADE"

    def test_invalid_decision_rejected(self):
        with pytest.raises(ValidationError):
            FinalVerdict(**_valid_verdict_payload(decision="MAYBE_LONG"))

    def test_audit_log_fields_present(self):
        verdict = FinalVerdict(**_valid_verdict_payload())
        assert verdict.audit_log.analysts_received == 4
        assert verdict.audit_log.htf_consensus is True


# ---------------------------------------------------------------------------
# GroundTruthPacket immutability
# ---------------------------------------------------------------------------

class TestGroundTruthImmutability:
    def test_packet_is_frozen(self):
        """GroundTruthPacket must be immutable after creation (design rule #1)."""
        packet = GroundTruthPacket(
            instrument="XAUUSD",
            session="NY",
            timeframes=["H4", "H1", "M15"],
            charts={"H4": "base64data"},
            risk_constraints=RiskConstraints(),
            context=MarketContext(account_balance=10000.0),
        )
        with pytest.raises(Exception):   # ValidationError or TypeError depending on Pydantic version
            packet.instrument = "EURUSD"  # type: ignore
