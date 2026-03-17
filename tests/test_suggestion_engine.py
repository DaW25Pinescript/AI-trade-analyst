"""Suggestion engine v0 contract tests (PR-REFLECT-3).

Tests for both rules, ordering, deduplication, template conformance,
navigable_entity_id, and malformed input handling.
"""

import pytest

from ai_analyst.api.models.reflect import (
    PatternBucket,
    PersonaStats,
    Suggestion,
    VerdictCount,
)
from ai_analyst.api.services.suggestion_engine import (
    OVERRIDE_RATE_THRESHOLD,
    NO_TRADE_RATE_THRESHOLD,
    PERSONA_MIN_PARTICIPATION,
    compute_navigable_entity_id,
    generate_pattern_suggestions,
    generate_persona_suggestions,
    humanise_persona,
)


# ---- Helpers ----

def _persona(
    persona: str = "default_analyst",
    participation_count: int = 20,
    override_count: int = 12,
    override_rate: float | None = 0.6,
    flagged: bool = True,
) -> PersonaStats:
    return PersonaStats(
        persona=persona,
        participation_count=participation_count,
        skip_count=0,
        fail_count=0,
        participation_rate=1.0,
        override_count=override_count,
        override_rate=override_rate,
        stance_alignment=None,
        avg_confidence=None,
        flagged=flagged,
    )


def _bucket(
    instrument: str = "XAUUSD",
    session: str = "NY",
    run_count: int = 15,
    threshold_met: bool = True,
    no_trade_rate: float | None = 0.9,
    no_trade_count: int = 13,
    other_verdicts: list[VerdictCount] | None = None,
) -> PatternBucket:
    vd = [VerdictCount(verdict="NO_TRADE", count=no_trade_count)]
    if other_verdicts:
        vd.extend(other_verdicts)
    else:
        vd.append(VerdictCount(verdict="BUY", count=run_count - no_trade_count))
    return PatternBucket(
        instrument=instrument,
        session=session,
        run_count=run_count,
        threshold_met=threshold_met,
        verdict_distribution=vd,
        no_trade_rate=no_trade_rate,
        flagged=no_trade_rate is not None and no_trade_rate > 0.8,
    )


# ===== RULE 1: OVERRIDE_FREQ_HIGH =====

class TestOverrideFreqHigh:
    def test_fires_when_above_threshold(self):
        stats = [_persona(override_rate=0.6, participation_count=15)]
        result = generate_persona_suggestions(stats)
        assert len(result) == 1
        assert result[0].rule_id == "OVERRIDE_FREQ_HIGH"
        assert result[0].severity == "warning"
        assert result[0].category == "persona"

    def test_does_not_fire_below_threshold(self):
        stats = [_persona(override_rate=0.4, participation_count=15)]
        result = generate_persona_suggestions(stats)
        assert len(result) == 0

    def test_does_not_fire_at_exact_threshold(self):
        stats = [_persona(override_rate=0.5, participation_count=15)]
        result = generate_persona_suggestions(stats)
        assert len(result) == 0

    def test_does_not_fire_null_override_rate(self):
        stats = [_persona(override_rate=None, participation_count=15)]
        result = generate_persona_suggestions(stats)
        assert len(result) == 0

    def test_does_not_fire_below_participation(self):
        stats = [_persona(override_rate=0.8, participation_count=9)]
        result = generate_persona_suggestions(stats)
        assert len(result) == 0

    def test_fires_at_exact_min_participation(self):
        stats = [_persona(override_rate=0.6, participation_count=10, override_count=6)]
        result = generate_persona_suggestions(stats)
        assert len(result) == 1

    def test_template_conformance(self):
        stats = [_persona(
            persona="default_analyst",
            override_rate=0.6,
            participation_count=20,
            override_count=12,
        )]
        result = generate_persona_suggestions(stats)
        msg = result[0].message
        assert "Default Analyst" in msg
        assert "12 of 20 recent runs" in msg
        assert "override rate 60%" in msg
        assert "consider reviewing" in msg

    def test_evidence_fields(self):
        stats = [_persona(override_rate=0.75, participation_count=20)]
        result = generate_persona_suggestions(stats)
        ev = result[0].evidence
        assert ev.metric_name == "override_rate"
        assert ev.metric_value == 0.75
        assert ev.threshold == OVERRIDE_RATE_THRESHOLD
        assert ev.sample_size == 20

    def test_target_is_humanised(self):
        stats = [_persona(persona="ict_purist", override_rate=0.7, participation_count=15)]
        result = generate_persona_suggestions(stats)
        assert result[0].target == "Ict Purist"


# ===== RULE 2: NO_TRADE_CONCENTRATION =====

class TestNoTradeConcentration:
    def test_fires_when_above_threshold(self):
        buckets = [_bucket(no_trade_rate=0.9)]
        result = generate_pattern_suggestions(buckets)
        assert len(result) == 1
        assert result[0].rule_id == "NO_TRADE_CONCENTRATION"
        assert result[0].category == "pattern"

    def test_does_not_fire_below_threshold(self):
        buckets = [_bucket(no_trade_rate=0.7, no_trade_count=10, run_count=15)]
        result = generate_pattern_suggestions(buckets)
        assert len(result) == 0

    def test_does_not_fire_at_exact_threshold(self):
        buckets = [_bucket(no_trade_rate=0.8, no_trade_count=12, run_count=15)]
        result = generate_pattern_suggestions(buckets)
        assert len(result) == 0

    def test_does_not_fire_threshold_not_met(self):
        buckets = [_bucket(threshold_met=False, no_trade_rate=0.95)]
        result = generate_pattern_suggestions(buckets)
        assert len(result) == 0

    def test_does_not_fire_null_no_trade_rate(self):
        buckets = [_bucket(no_trade_rate=None)]
        result = generate_pattern_suggestions(buckets)
        assert len(result) == 0

    def test_verdict_distribution_no_no_trade_entry(self):
        bucket = PatternBucket(
            instrument="XAUUSD", session="NY", run_count=15,
            threshold_met=True,
            verdict_distribution=[VerdictCount(verdict="BUY", count=15)],
            no_trade_rate=0.0, flagged=False,
        )
        result = generate_pattern_suggestions([bucket])
        assert len(result) == 0

    def test_template_conformance(self):
        buckets = [_bucket(
            instrument="XAUUSD", session="NY",
            no_trade_rate=0.9, no_trade_count=13, run_count=15,
        )]
        result = generate_pattern_suggestions(buckets)
        msg = result[0].message
        assert "XAUUSD NY session" in msg
        assert "NO_TRADE in 13 of 15 recent runs" in msg
        assert "90%" in msg
        assert "confidence threshold may be too high" in msg

    def test_evidence_fields(self):
        buckets = [_bucket(no_trade_rate=0.85, no_trade_count=12, run_count=14)]
        result = generate_pattern_suggestions(buckets)
        ev = result[0].evidence
        assert ev.metric_name == "no_trade_rate"
        assert ev.metric_value == 0.85
        assert ev.threshold == NO_TRADE_RATE_THRESHOLD
        assert ev.sample_size == 14

    def test_target_format(self):
        buckets = [_bucket(instrument="EURUSD", session="LDN")]
        result = generate_pattern_suggestions(buckets)
        assert result[0].target == "EURUSD × LDN"


# ===== EMPTY / MULTIPLE =====

class TestEmptyAndMultiple:
    def test_no_triggers_empty_list(self):
        stats = [_persona(override_rate=0.3, participation_count=20)]
        assert generate_persona_suggestions(stats) == []

    def test_empty_input_empty_output(self):
        assert generate_persona_suggestions([]) == []
        assert generate_pattern_suggestions([]) == []

    def test_multiple_persona_suggestions(self):
        stats = [
            _persona(persona="a_persona", override_rate=0.7, participation_count=15, override_count=10),
            _persona(persona="b_persona", override_rate=0.6, participation_count=12, override_count=7),
        ]
        result = generate_persona_suggestions(stats)
        assert len(result) == 2

    def test_multiple_pattern_suggestions(self):
        buckets = [
            _bucket(instrument="XAUUSD", session="NY", no_trade_rate=0.95),
            _bucket(instrument="EURUSD", session="LDN", no_trade_rate=0.85),
        ]
        result = generate_pattern_suggestions(buckets)
        assert len(result) == 2


# ===== SCHEMA VALIDATION =====

class TestFullSchema:
    def test_suggestion_has_all_required_fields(self):
        stats = [_persona(override_rate=0.7, participation_count=15)]
        result = generate_persona_suggestions(stats)
        s = result[0]
        assert isinstance(s, Suggestion)
        assert s.rule_id in ("OVERRIDE_FREQ_HIGH", "NO_TRADE_CONCENTRATION")
        assert s.severity == "warning"
        assert s.category in ("persona", "pattern")
        assert isinstance(s.target, str) and len(s.target) > 0
        assert isinstance(s.message, str) and len(s.message) > 0
        assert isinstance(s.evidence.metric_name, str)
        assert isinstance(s.evidence.metric_value, float)
        assert isinstance(s.evidence.threshold, float)
        assert isinstance(s.evidence.sample_size, int)


# ===== ORDERING =====

class TestOrdering:
    def test_descending_metric_value(self):
        stats = [
            _persona(persona="low", override_rate=0.6, participation_count=20, override_count=12),
            _persona(persona="high", override_rate=0.9, participation_count=20, override_count=18),
        ]
        result = generate_persona_suggestions(stats)
        assert result[0].evidence.metric_value > result[1].evidence.metric_value

    def test_ascending_target_tiebreak(self):
        stats = [
            _persona(persona="beta_persona", override_rate=0.7, participation_count=20, override_count=14),
            _persona(persona="alpha_persona", override_rate=0.7, participation_count=20, override_count=14),
        ]
        result = generate_persona_suggestions(stats)
        assert result[0].target < result[1].target


# ===== DEDUPLICATION =====

class TestDeduplication:
    def test_unique_rule_id_target(self):
        stats = [
            _persona(persona="dup", override_rate=0.7, participation_count=20, override_count=14),
            _persona(persona="dup", override_rate=0.7, participation_count=25, override_count=17),
        ]
        result = generate_persona_suggestions(stats)
        assert len(result) == 1
        assert result[0].evidence.sample_size == 25  # higher sample wins


# ===== NAVIGABLE ENTITY ID =====

class TestNavigableEntityId:
    def test_computed_correctly(self):
        assert compute_navigable_entity_id("default_analyst") == "persona_default_analyst"

    def test_null_when_persona_null(self):
        assert compute_navigable_entity_id(None) is None

    def test_null_when_persona_empty(self):
        assert compute_navigable_entity_id("") is None


# ===== HUMANISE PERSONA =====

class TestHumanisePersona:
    def test_basic(self):
        assert humanise_persona("default_analyst") == "Default Analyst"

    def test_single_word(self):
        assert humanise_persona("prosecutor") == "Prosecutor"


# ===== NON-BREAKING =====

class TestNonBreaking:
    def test_existing_persona_stats_fields_unchanged(self):
        s = _persona(persona="test", override_rate=0.3, participation_count=5)
        assert s.persona == "test"
        assert s.participation_count == 5
        assert s.override_rate == 0.3
        assert s.flagged is True  # since override_rate passed as 0.3 and flagged=True default

    def test_suggestions_default_empty(self):
        from ai_analyst.api.models.reflect import PersonaPerformanceResponse, PatternSummaryResponse, ScanBounds
        bounds = ScanBounds(max_runs=50, inspected_dirs=10, valid_runs=10, skipped_runs=0)
        resp = PersonaPerformanceResponse(
            version="2026.03", generated_at="2026-03-17T00:00:00Z",
            data_state="live", source_of_truth="test",
            threshold_met=True, scan_bounds=bounds, stats=[],
        )
        assert resp.suggestions == []
        presp = PatternSummaryResponse(
            version="2026.03", generated_at="2026-03-17T00:00:00Z",
            data_state="live", source_of_truth="test",
            scan_bounds=bounds, buckets=[],
        )
        assert presp.suggestions == []


# ===== BACKEND NEVER EMITS UNRESOLVABLE TEMPLATE VARIABLES =====

class TestNoUnresolvableTemplateVars:
    def test_override_message_has_no_braces(self):
        stats = [_persona(override_rate=0.7, participation_count=15, override_count=10)]
        result = generate_persona_suggestions(stats)
        assert "{" not in result[0].message
        assert "}" not in result[0].message

    def test_no_trade_message_has_no_braces(self):
        buckets = [_bucket(no_trade_rate=0.9, no_trade_count=13, run_count=15)]
        result = generate_pattern_suggestions(buckets)
        assert "{" not in result[0].message
        assert "}" not in result[0].message
