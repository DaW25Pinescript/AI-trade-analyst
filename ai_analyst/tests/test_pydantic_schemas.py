"""
Pydantic schema validation tests.

Covers:
- Valid analyst outputs pass validation.
- The NO_TRADE enforcement rule fires on setup_valid=false, low confidence, and disqualifiers.
- FinalVerdict schema validates correctly, including overlay fields.
- GroundTruthPacket immutability (frozen model).
- ScreenshotMetadata type validation.
- GroundTruthPacket screenshot architecture constraints (cap, overlay binding, metadata count).
- OverlayDeltaReport schema validation.
"""
import pytest
from pydantic import ValidationError
from ..models.analyst_output import AnalystOutput, KeyLevels, OverlayDeltaReport
from ..models.arbiter_output import FinalVerdict, ApprovedSetup, AuditLog
from ..models.ground_truth import (
    GroundTruthPacket,
    RiskConstraints,
    MarketContext,
    ScreenshotMetadata,
)


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
                "indicator_dependent": False,
            }
        ],
        "no_trade_conditions": [],
        "overall_confidence": 0.68,
        "analyst_agreement_pct": 75,
        "risk_override_applied": False,
        "arbiter_notes": "Three of four analysts agree on bearish setup. Strong sweep evidence.",
        "overlay_was_provided": False,
        "indicator_dependent": False,
        "indicator_dependency_notes": None,
        "audit_log": {
            "run_id": "test-run-001",
            "analysts_received": 4,
            "analysts_valid": 3,
            "htf_consensus": True,
            "setup_consensus": True,
            "risk_override": False,
            "overlay_provided": False,
            "indicator_dependent_setups": 0,
        },
    }
    base.update(overrides)
    return base


def _make_ground_truth(**overrides) -> dict:
    base = {
        "instrument": "XAUUSD",
        "session": "NY",
        "timeframes": ["H4", "M15", "M5"],
        "charts": {
            "H4": "base64h4",
            "M15": "base64m15",
            "M5": "base64m5",
        },
        "screenshot_metadata": [
            {"timeframe": "H4",  "lens": "NONE", "evidence_type": "price_only"},
            {"timeframe": "M15", "lens": "NONE", "evidence_type": "price_only"},
            {"timeframe": "M5",  "lens": "NONE", "evidence_type": "price_only"},
        ],
        "risk_constraints": RiskConstraints(),
        "context": MarketContext(account_balance=10000.0),
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
# OverlayDeltaReport tests
# ---------------------------------------------------------------------------

class TestOverlayDeltaReport:
    def test_valid_delta_report_all_fields(self):
        report = OverlayDeltaReport(
            confirms=["discount FVG aligns with price impulse"],
            refines=["order block boundary narrower than price-only estimate"],
            contradicts=[],
            indicator_only_claims=["minor OB not visible in price"],
        )
        assert len(report.confirms) == 1
        assert report.contradicts == []

    def test_valid_delta_report_all_empty(self):
        """All four fields empty (no meaningful delta) is valid."""
        report = OverlayDeltaReport(confirms=[], refines=[], contradicts=[], indicator_only_claims=[])
        assert report.confirms == []
        assert report.indicator_only_claims == []

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            OverlayDeltaReport(
                confirms=["x"],
                refines=["y"],
                # contradicts omitted — should fail
                indicator_only_claims=[],
            )

    def test_multiple_items_per_field(self):
        report = OverlayDeltaReport(
            confirms=["a", "b", "c"],
            refines=["d"],
            contradicts=["e", "f"],
            indicator_only_claims=["g"],
        )
        assert len(report.confirms) == 3
        assert len(report.contradicts) == 2


# ---------------------------------------------------------------------------
# FinalVerdict tests
# ---------------------------------------------------------------------------

class TestFinalVerdict:
    def test_valid_enter_short_verdict(self):
        verdict = FinalVerdict(**_valid_verdict_payload())
        assert verdict.decision == "ENTER_SHORT"
        assert verdict.overlay_was_provided is False
        assert verdict.indicator_dependent is False

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
        assert verdict.audit_log.overlay_provided is False
        assert verdict.audit_log.indicator_dependent_setups == 0

    def test_overlay_verdict_fields(self):
        """Verdict with overlay data sets overlay_was_provided and indicator_dependent."""
        verdict = FinalVerdict(**_valid_verdict_payload(
            overlay_was_provided=True,
            indicator_dependent=True,
            indicator_dependency_notes="FVG boundary from overlay only",
            audit_log={
                "run_id": "test-overlay-001",
                "analysts_received": 4,
                "analysts_valid": 4,
                "htf_consensus": True,
                "setup_consensus": True,
                "risk_override": False,
                "overlay_provided": True,
                "indicator_dependent_setups": 1,
            },
        ))
        assert verdict.overlay_was_provided is True
        assert verdict.indicator_dependent is True
        assert verdict.indicator_dependency_notes == "FVG boundary from overlay only"
        assert verdict.audit_log.overlay_provided is True
        assert verdict.audit_log.indicator_dependent_setups == 1


# ---------------------------------------------------------------------------
# ScreenshotMetadata tests
# ---------------------------------------------------------------------------

class TestScreenshotMetadata:
    def test_valid_clean_price_metadata(self):
        meta = ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only")
        assert meta.lens == "NONE"
        assert meta.evidence_type == "price_only"

    def test_valid_overlay_metadata(self):
        meta = ScreenshotMetadata(
            timeframe="M15",
            lens="ICT",
            evidence_type="indicator_overlay",
            indicator_claims=["FVG", "OrderBlock", "SessionLiquidity"],
            indicator_source="TradingView",
            settings_locked=True,
        )
        assert meta.lens == "ICT"
        assert len(meta.indicator_claims) == 3

    def test_overlay_without_claims_rejected(self):
        with pytest.raises(ValidationError):
            ScreenshotMetadata(
                timeframe="M15",
                lens="ICT",
                evidence_type="indicator_overlay",
                indicator_claims=[],  # empty — invalid for overlay
            )

    def test_overlay_missing_claims_rejected(self):
        with pytest.raises(ValidationError):
            ScreenshotMetadata(
                timeframe="M15",
                lens="ICT",
                evidence_type="indicator_overlay",
                # indicator_claims omitted — required for overlay
            )

    def test_price_only_with_non_none_lens_rejected(self):
        with pytest.raises(ValidationError):
            ScreenshotMetadata(
                timeframe="H4",
                lens="ICT",            # invalid for price_only
                evidence_type="price_only",
            )

    def test_overlay_type_with_none_lens_rejected(self):
        with pytest.raises(ValidationError):
            ScreenshotMetadata(
                timeframe="M15",
                lens="NONE",           # invalid for indicator_overlay
                evidence_type="indicator_overlay",
                indicator_claims=["FVG"],
            )


# ---------------------------------------------------------------------------
# GroundTruthPacket tests
# ---------------------------------------------------------------------------

class TestGroundTruthPacket:
    def test_valid_three_clean_charts(self):
        packet = GroundTruthPacket(**_make_ground_truth())
        assert len(packet.charts) == 3
        assert packet.m15_overlay is None

    def test_valid_with_overlay(self):
        packet = GroundTruthPacket(**_make_ground_truth(
            m15_overlay="base64overlaydata",
            m15_overlay_metadata=ScreenshotMetadata(
                timeframe="M15",
                lens="ICT",
                evidence_type="indicator_overlay",
                indicator_claims=["FVG", "OrderBlock"],
                indicator_source="TradingView",
                settings_locked=True,
            ),
        ))
        assert packet.m15_overlay == "base64overlaydata"
        assert packet.m15_overlay_metadata.lens == "ICT"

    def test_packet_is_frozen(self):
        """GroundTruthPacket must be immutable after creation (design rule #1)."""
        packet = GroundTruthPacket(**_make_ground_truth())
        with pytest.raises(Exception):   # ValidationError or TypeError depending on Pydantic version
            packet.instrument = "EURUSD"  # type: ignore

    def test_screenshot_cap_exceeded_rejected(self):
        """More than 4 screenshots (3 clean + 1 overlay) must be rejected."""
        with pytest.raises(ValidationError):
            GroundTruthPacket(**_make_ground_truth(
                charts={
                    "H4": "b64", "H1": "b64", "M15": "b64", "M5": "b64",  # 4 clean
                },
                screenshot_metadata=[
                    {"timeframe": "H4",  "lens": "NONE", "evidence_type": "price_only"},
                    {"timeframe": "H1",  "lens": "NONE", "evidence_type": "price_only"},
                    {"timeframe": "M15", "lens": "NONE", "evidence_type": "price_only"},
                    {"timeframe": "M5",  "lens": "NONE", "evidence_type": "price_only"},
                ],
                m15_overlay="b64overlay",  # 4 clean + 1 overlay = 5 — over cap
                m15_overlay_metadata=ScreenshotMetadata(
                    timeframe="M15",
                    lens="ICT",
                    evidence_type="indicator_overlay",
                    indicator_claims=["FVG"],
                    indicator_source="TradingView",
                    settings_locked=True,
                ),
            ))

    def test_metadata_count_mismatch_rejected(self):
        """screenshot_metadata count must match charts count."""
        with pytest.raises(ValidationError):
            GroundTruthPacket(**_make_ground_truth(
                screenshot_metadata=[
                    {"timeframe": "H4", "lens": "NONE", "evidence_type": "price_only"},
                    # missing M15 and M5 entries
                ],
            ))

    def test_overlay_without_m15_clean_rejected(self):
        """Overlay requires the M15 clean chart to also be present."""
        with pytest.raises(ValidationError):
            GroundTruthPacket(**_make_ground_truth(
                charts={"H4": "b64", "M5": "b64"},  # M15 missing
                screenshot_metadata=[
                    {"timeframe": "H4", "lens": "NONE", "evidence_type": "price_only"},
                    {"timeframe": "M5", "lens": "NONE", "evidence_type": "price_only"},
                ],
                m15_overlay="b64overlay",
                m15_overlay_metadata=ScreenshotMetadata(
                    timeframe="M15",
                    lens="ICT",
                    evidence_type="indicator_overlay",
                    indicator_claims=["FVG"],
                    indicator_source="TradingView",
                    settings_locked=True,
                ),
            ))

    def test_overlay_metadata_wrong_timeframe_rejected(self):
        """Overlay metadata timeframe must be M15."""
        with pytest.raises(ValidationError):
            GroundTruthPacket(**_make_ground_truth(
                m15_overlay="b64overlay",
                m15_overlay_metadata=ScreenshotMetadata(
                    timeframe="H4",   # wrong timeframe
                    lens="ICT",
                    evidence_type="indicator_overlay",
                    indicator_claims=["FVG"],
                    indicator_source="TradingView",
                    settings_locked=True,
                ),
            ))

    def test_overlay_metadata_without_image_rejected(self):
        """m15_overlay_metadata without m15_overlay image must be rejected."""
        with pytest.raises(ValidationError):
            GroundTruthPacket(**_make_ground_truth(
                m15_overlay=None,  # no image
                m15_overlay_metadata=ScreenshotMetadata(
                    timeframe="M15",
                    lens="ICT",
                    evidence_type="indicator_overlay",
                    indicator_claims=["FVG"],
                    indicator_source="TradingView",
                    settings_locked=True,
                ),
            ))

    def test_overlay_image_without_metadata_rejected(self):
        """m15_overlay without m15_overlay_metadata must be rejected."""
        with pytest.raises(ValidationError):
            GroundTruthPacket(**_make_ground_truth(
                m15_overlay="b64overlay",
                # m15_overlay_metadata omitted
            ))

    def test_disallowed_clean_timeframe_rejected(self):
        """Clean chart timeframes must be H4, H1, M15, or M5 only."""
        with pytest.raises(ValidationError):
            GroundTruthPacket(**_make_ground_truth(
                charts={"D1": "b64", "M15": "b64", "M5": "b64"},  # D1 not allowed
                screenshot_metadata=[
                    {"timeframe": "D1",  "lens": "NONE", "evidence_type": "price_only"},
                    {"timeframe": "M15", "lens": "NONE", "evidence_type": "price_only"},
                    {"timeframe": "M5",  "lens": "NONE", "evidence_type": "price_only"},
                ],
            ))
