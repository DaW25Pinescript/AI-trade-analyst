"""
Contract tests for the ticket_draft builder (v2.0).

Verifies deterministic field mapping from FinalVerdict + GroundTruthPacket
to the partial ticket_draft dict returned in the POST /analyse envelope.
"""
import pytest

from ..models.arbiter_output import FinalVerdict, ApprovedSetup, AuditLog
from ..models.ground_truth import (
    GroundTruthPacket,
    RiskConstraints,
    MarketContext,
    ScreenshotMetadata,
)
from ..output.ticket_draft import (
    build_ticket_draft,
    _try_parse_price,
    _conviction_from_confidence,
    _confluence_score,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_packet(**overrides) -> GroundTruthPacket:
    defaults = dict(
        instrument="XAUUSD",
        session="NY",
        timeframes=["H4", "M15"],
        charts={"H4": "base64data", "M15": "base64data2"},
        screenshot_metadata=[
            ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only"),
            ScreenshotMetadata(timeframe="M15", lens="NONE", evidence_type="price_only"),
        ],
        risk_constraints=RiskConstraints(
            min_rr=2.0, max_risk_per_trade=0.5, max_daily_risk=2.0
        ),
        context=MarketContext(
            market_regime="trending",
            news_risk="none_noted",
            account_balance=10000.0,
        ),
    )
    defaults.update(overrides)
    return GroundTruthPacket(**defaults)


def _make_approved_setup(**overrides) -> ApprovedSetup:
    defaults = dict(
        type="Liquidity Grab Reversal",
        entry_zone="1930–1935",
        stop="Below 1925.00",
        targets=["1950.00", "1960.00"],
        rr_estimate=2.5,
        confidence=0.72,
    )
    defaults.update(overrides)
    return ApprovedSetup(**defaults)


def _make_verdict(**overrides) -> FinalVerdict:
    defaults = dict(
        final_bias="bullish",
        decision="ENTER_LONG",
        approved_setups=[_make_approved_setup()],
        no_trade_conditions=[],
        overall_confidence=0.72,
        analyst_agreement_pct=75,
        risk_override_applied=False,
        arbiter_notes="Strong ICT sweep + displacement confluence.",
        audit_log=AuditLog(
            run_id="test-run-001",
            analysts_received=4,
            analysts_valid=3,
            htf_consensus=True,
            setup_consensus=True,
            risk_override=False,
        ),
    )
    defaults.update(overrides)
    return FinalVerdict(**defaults)


# ── Decision mapping ──────────────────────────────────────────────────────────


class TestDecisionMapping:
    @pytest.mark.parametrize(
        "decision,expected",
        [
            ("ENTER_LONG", "LONG"),
            ("ENTER_SHORT", "SHORT"),
            ("WAIT_FOR_CONFIRMATION", "WAIT"),
            ("NO_TRADE", "WAIT"),
        ],
    )
    def test_decision_maps_correctly(self, decision, expected):
        approved = [] if decision == "NO_TRADE" else [_make_approved_setup()]
        verdict = _make_verdict(decision=decision, approved_setups=approved)
        draft = build_ticket_draft(verdict, _make_packet())
        assert draft["decisionMode"] == expected


# ── Bias mapping ──────────────────────────────────────────────────────────────


class TestBiasMapping:
    @pytest.mark.parametrize(
        "bias,expected",
        [
            ("bullish", "Bullish"),
            ("bearish", "Bearish"),
            ("neutral", "Neutral"),
            ("ranging", "Range"),
            ("BULLISH", "Bullish"),    # case-insensitive
            ("unknown_bias", ""),      # unmapped → empty string
        ],
    )
    def test_bias_maps_correctly(self, bias, expected):
        verdict = _make_verdict(final_bias=bias)
        draft = build_ticket_draft(verdict, _make_packet())
        assert draft["rawAIReadBias"] == expected


# ── Conviction ────────────────────────────────────────────────────────────────


class TestConviction:
    @pytest.mark.parametrize(
        "confidence,expected",
        [
            (0.80, "Very High"),
            (0.90, "Very High"),
            (0.65, "High"),
            (0.70, "High"),
            (0.50, "Medium"),
            (0.55, "Medium"),
            (0.45, "Low"),
            (0.20, "Low"),
        ],
    )
    def test_conviction_from_confidence(self, confidence, expected):
        assert _conviction_from_confidence(confidence) == expected

    def test_conviction_embedded_in_checklist(self):
        verdict = _make_verdict(overall_confidence=0.80)
        draft = build_ticket_draft(verdict, _make_packet())
        assert draft["checklist"]["conviction"] == "Very High"


# ── Gate mapping ──────────────────────────────────────────────────────────────


class TestGateMapping:
    def test_no_trade_produces_wait_gate(self):
        verdict = _make_verdict(
            decision="NO_TRADE",
            approved_setups=[],
            no_trade_conditions=["No sweep", "Low confluence"],
        )
        draft = build_ticket_draft(verdict, _make_packet())
        assert draft["gate"]["status"] == "WAIT"
        assert "No sweep" in draft["gate"]["reentryCondition"]
        assert "Low confluence" in draft["gate"]["reentryCondition"]

    def test_enter_long_produces_proceed_gate(self):
        draft = build_ticket_draft(_make_verdict(decision="ENTER_LONG"), _make_packet())
        assert draft["gate"]["status"] == "PROCEED"

    def test_no_approved_setups_produces_wait_gate(self):
        verdict = _make_verdict(decision="WAIT_FOR_CONFIRMATION", approved_setups=[])
        draft = build_ticket_draft(verdict, _make_packet())
        assert draft["gate"]["status"] == "WAIT"


# ── Setup field mapping ───────────────────────────────────────────────────────


class TestSetupMapping:
    def test_entry_zone_preserved(self):
        draft = build_ticket_draft(_make_verdict(), _make_packet())
        assert draft["entry"]["zone"] == "1930–1935"

    def test_stop_rationale_preserved(self):
        draft = build_ticket_draft(_make_verdict(), _make_packet())
        assert draft["stop"]["rationale"] == "Below 1925.00"

    def test_stop_price_parsed(self):
        draft = build_ticket_draft(_make_verdict(), _make_packet())
        assert draft["stop"]["price"] == 1925.0

    def test_targets_mapped_with_labels(self):
        draft = build_ticket_draft(_make_verdict(), _make_packet())
        assert draft["targets"][0]["label"] == "TP1"
        assert draft["targets"][1]["label"] == "TP2"
        assert draft["targets"][0]["price"] == 1950.0
        assert draft["targets"][1]["price"] == 1960.0

    def test_max_three_targets(self):
        setup = _make_approved_setup(targets=["1940.0", "1950.0", "1960.0", "1970.0"])
        verdict = _make_verdict(approved_setups=[setup])
        draft = build_ticket_draft(verdict, _make_packet())
        assert len(draft["targets"]) == 3

    def test_no_approved_setups_omits_entry_stop_targets(self):
        verdict = _make_verdict(decision="NO_TRADE", approved_setups=[])
        draft = build_ticket_draft(verdict, _make_packet())
        assert "entry" not in draft
        assert "stop" not in draft
        assert "targets" not in draft


# ── Confluence score ──────────────────────────────────────────────────────────


class TestConfluenceScore:
    @pytest.mark.parametrize(
        "pct,expected",
        [
            (100, 10),
            (75, 8),   # round(7.5) = 8 (banker's rounding — rounds to even)
            (50, 5),
            (25, 2),   # round(2.5) = 2 (banker's rounding — rounds to even)
            (0, 1),    # min clamp
        ],
    )
    def test_confluence_score_scaling(self, pct, expected):
        verdict = _make_verdict(analyst_agreement_pct=pct)
        draft = build_ticket_draft(verdict, _make_packet())
        assert draft["checklist"]["confluenceScore"] == expected

    def test_confluence_helper_clamps_to_1(self):
        assert _confluence_score(0) == 1

    def test_confluence_helper_clamps_to_10(self):
        assert _confluence_score(100) == 10


# ── Traceability ──────────────────────────────────────────────────────────────


class TestTraceability:
    def test_source_run_id_present(self):
        packet = _make_packet()
        draft = build_ticket_draft(_make_verdict(), packet)
        assert draft["source_run_id"] == packet.run_id

    def test_source_ticket_id_included_when_set(self):
        packet = _make_packet(source_ticket_id="TICKET-001")
        draft = build_ticket_draft(_make_verdict(), packet)
        assert draft["source_ticket_id"] == "TICKET-001"

    def test_source_ticket_id_absent_when_not_set(self):
        packet = _make_packet()   # source_ticket_id defaults to None
        draft = build_ticket_draft(_make_verdict(), packet)
        assert "source_ticket_id" not in draft


# ── Screenshot mapping ────────────────────────────────────────────────────────


class TestScreenshotMapping:
    def test_clean_charts_mapped(self):
        draft = build_ticket_draft(_make_verdict(), _make_packet())
        assert len(draft["screenshots"]["cleanCharts"]) == 2
        assert draft["screenshots"]["cleanCharts"][0]["timeframe"] == "H4"
        assert draft["screenshots"]["cleanCharts"][1]["timeframe"] == "M15"

    def test_no_overlay_produces_null(self):
        draft = build_ticket_draft(_make_verdict(), _make_packet())
        assert draft["screenshots"]["m15Overlay"] is None


# ── Price parser helper ───────────────────────────────────────────────────────


class TestPriceParser:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("1925.00", 1925.0),
            ("Below 1920.50", 1920.5),
            ("1930–1935", 1930.0),    # first number extracted
            ("", None),
            ("No level identified", None),
            ("above key zone", None),
        ],
    )
    def test_try_parse_price(self, text, expected):
        assert _try_parse_price(text) == expected


# ── Defaults ──────────────────────────────────────────────────────────────────


class TestDefaults:
    def test_shadow_mode_defaults_false(self):
        draft = build_ticket_draft(_make_verdict(), _make_packet())
        assert draft["shadowMode"] is False

    def test_ai_edge_score_is_rounded(self):
        verdict = _make_verdict(overall_confidence=0.723456)
        draft = build_ticket_draft(verdict, _make_packet())
        assert draft["aiEdgeScore"] == round(0.723456, 4)
