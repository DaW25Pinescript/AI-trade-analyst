"""
Regression tests for v2.1 fixes.

Covers:
- TEST-10 (HIGH-3): FinalVerdict.final_bias is now a Literal enum — unexpected values
  raise ValidationError; valid values map correctly through build_ticket_draft.
- TEST-9  (HIGH-4): MacroScheduler thread safety — concurrent cache misses call
  _refresh() exactly once per cache miss window (thundering herd guard).
- HIGH-2  (datetime.utcnow deprecation): timestamp_utc and created_at/updated_at
  fields produce timezone-aware datetimes.
- MED-7   (is_text_only routing gap): list-format content blocks with only text
  items are correctly detected as text-only.
- LOW-5   (ExecutionConfig.mode Literal): invalid mode values are rejected.
"""
import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

# ── TEST-10: HIGH-3 — FinalVerdict.final_bias Literal enum ──────────────────


def _make_verdict_payload(**overrides) -> dict:
    base = {
        "final_bias": "bearish",
        "decision": "ENTER_SHORT",
        "approved_setups": [],
        "no_trade_conditions": [],
        "overall_confidence": 0.70,
        "analyst_agreement_pct": 75,
        "risk_override_applied": False,
        "arbiter_notes": "Test verdict",
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


def test_final_bias_valid_values_accepted():
    """All four permitted final_bias values must pass FinalVerdict validation."""
    from ai_analyst.models.arbiter_output import FinalVerdict

    for bias in ("bullish", "bearish", "neutral", "ranging"):
        verdict = FinalVerdict(**_make_verdict_payload(final_bias=bias))
        assert verdict.final_bias == bias


def test_final_bias_invalid_value_raises_validation_error():
    """An unrecognised final_bias string must now raise ValidationError (was silently accepted)."""
    from ai_analyst.models.arbiter_output import FinalVerdict

    with pytest.raises(ValidationError, match="final_bias"):
        FinalVerdict(**_make_verdict_payload(final_bias="sideways"))


def test_final_bias_unknown_value_produces_empty_raw_ai_read_bias():
    """
    Guard for TEST-10: when the Arbiter emits an unexpected bias string, the
    schema now rejects it (ValidationError) before ticket_draft is ever called.
    Previously the freeform str bypassed _BIAS_MAP and silently produced "".
    """
    from ai_analyst.models.arbiter_output import FinalVerdict

    bad_values = ["BULLISH", "Bull", "risk_on", "long", ""]
    for bad in bad_values:
        with pytest.raises(ValidationError):
            FinalVerdict(**_make_verdict_payload(final_bias=bad))


def test_final_bias_maps_correctly_in_ticket_draft():
    """
    Valid final_bias values must map to the correct rawAIReadBias strings in
    the ticket draft via build_ticket_draft().
    """
    from ai_analyst.models.arbiter_output import FinalVerdict
    from ai_analyst.models.ground_truth import (
        GroundTruthPacket,
        RiskConstraints,
        MarketContext,
        ScreenshotMetadata,
    )
    from ai_analyst.output.ticket_draft import build_ticket_draft

    packet = GroundTruthPacket(
        instrument="XAUUSD",
        session="NY",
        timeframes=["H4"],
        charts={"H4": "base64h4"},
        screenshot_metadata=[ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only")],
        risk_constraints=RiskConstraints(),
        context=MarketContext(account_balance=10000.0),
    )

    expected_map = {
        "bullish": "Bullish",
        "bearish": "Bearish",
        "neutral": "Neutral",
        "ranging": "Range",
    }
    for bias, expected_draft_value in expected_map.items():
        verdict = FinalVerdict(**_make_verdict_payload(final_bias=bias))
        draft = build_ticket_draft(verdict, packet)
        assert draft["rawAIReadBias"] == expected_draft_value, (
            f"final_bias={bias!r} should map to rawAIReadBias={expected_draft_value!r}; "
            f"got {draft['rawAIReadBias']!r}"
        )


# ── TEST-9: HIGH-4 — MacroScheduler thundering herd guard ───────────────────


def test_macro_scheduler_concurrent_cache_miss_calls_refresh_once():
    """
    When the cache is cold and multiple threads call get_context() simultaneously,
    _refresh() must be invoked exactly once (not once per thread).
    """
    from macro_risk_officer.ingestion.scheduler import MacroScheduler

    refresh_count = {"n": 0}
    mock_context = MagicMock()

    original_refresh = MacroScheduler._refresh

    def counted_refresh(self, instrument):
        refresh_count["n"] += 1
        # Simulate slow network call to expose race conditions
        import time
        time.sleep(0.02)
        return mock_context, "mock_source", 1

    scheduler = MacroScheduler(ttl_seconds=60, enable_fetch_log=False)

    with patch.object(MacroScheduler, "_refresh", counted_refresh):
        errors = []
        results = []

        def call_get_context():
            try:
                ctx = scheduler.get_context("XAUUSD")
                results.append(ctx)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_get_context) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert not errors, f"Unexpected errors: {errors}"
    assert refresh_count["n"] == 1, (
        f"Expected _refresh() to be called exactly once for concurrent cache misses; "
        f"got {refresh_count['n']} calls (thundering herd not guarded)"
    )
    assert all(r is mock_context for r in results), "All threads should receive the same context"


def test_macro_scheduler_cache_hit_does_not_call_refresh():
    """After a successful refresh, subsequent calls within TTL must read from cache."""
    from macro_risk_officer.ingestion.scheduler import MacroScheduler

    refresh_count = {"n": 0}
    mock_context = MagicMock()

    def counted_refresh(self, instrument):
        refresh_count["n"] += 1
        return mock_context, "mock_source", 1

    scheduler = MacroScheduler(ttl_seconds=60, enable_fetch_log=False)

    with patch.object(MacroScheduler, "_refresh", counted_refresh):
        for _ in range(5):
            scheduler.get_context("XAUUSD")

    assert refresh_count["n"] == 1, (
        f"Cache hit path must not call _refresh(); called {refresh_count['n']} times"
    )


# ── HIGH-2: datetime.utcnow() deprecation ───────────────────────────────────


def test_ground_truth_packet_timestamp_is_timezone_aware():
    """timestamp_utc must be a timezone-aware UTC datetime (not naive)."""
    from ai_analyst.models.ground_truth import (
        GroundTruthPacket,
        RiskConstraints,
        MarketContext,
        ScreenshotMetadata,
    )

    packet = GroundTruthPacket(
        instrument="XAUUSD",
        session="NY",
        timeframes=["H4"],
        charts={"H4": "base64h4"},
        screenshot_metadata=[ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only")],
        risk_constraints=RiskConstraints(),
        context=MarketContext(account_balance=10000.0),
    )

    assert packet.timestamp_utc.tzinfo is not None, (
        "GroundTruthPacket.timestamp_utc must be timezone-aware (not naive). "
        "datetime.utcnow() returns a naive datetime — use datetime.now(timezone.utc)."
    )
    assert packet.timestamp_utc.tzinfo == timezone.utc


def test_run_state_created_at_is_timezone_aware():
    """RunState.created_at and updated_at must be timezone-aware UTC datetimes."""
    from ai_analyst.models.execution_config import RunState, RunStatus

    state = RunState(
        run_id="r1",
        status=RunStatus.CREATED,
        mode="manual",
        instrument="XAUUSD",
        session="NY",
    )
    assert state.created_at.tzinfo is not None, "created_at must be timezone-aware"
    assert state.updated_at.tzinfo is not None, "updated_at must be timezone-aware"


def test_transition_updated_at_is_timezone_aware(tmp_path, monkeypatch):
    """transition() must set updated_at to a timezone-aware datetime."""
    import ai_analyst.core.run_state_manager as rsm

    # Redirect save path to tmp_path so we don't write to real output dir
    monkeypatch.setattr(rsm, "OUTPUT_BASE", tmp_path)

    from ai_analyst.models.execution_config import RunState, RunStatus

    state = RunState(
        run_id="r-test-tz",
        status=RunStatus.CREATED,
        mode="manual",
        instrument="XAUUSD",
        session="NY",
    )
    new_state = rsm.transition(state, RunStatus.PROMPTS_GENERATED)
    assert new_state.updated_at.tzinfo is not None, (
        "transition() must produce a timezone-aware updated_at datetime"
    )


# ── MED-7: is_text_only list-format content blocks ───────────────────────────


def test_is_text_only_plain_string_content():
    """Standard messages with plain string content are text-only."""
    from ai_analyst.core.is_text_only import is_text_only

    messages = [
        {"role": "system", "content": "You are an analyst."},
        {"role": "user", "content": "Analyse this setup."},
    ]
    assert is_text_only(messages) is True


def test_is_text_only_list_content_with_text_blocks_only():
    """
    MED-7: list-format content where every block has type='text' must be
    detected as text-only (previously returned False, blocking claude_code_api routing).
    """
    from ai_analyst.core.is_text_only import is_text_only

    messages = [
        {"role": "system", "content": [{"type": "text", "text": "You are an analyst."}]},
        {"role": "user", "content": [{"type": "text", "text": "Analyse this setup."}]},
    ]
    assert is_text_only(messages) is True


def test_is_text_only_list_content_with_image_block_is_multimodal():
    """List-format content containing an image block must NOT be text-only."""
    from ai_analyst.core.is_text_only import is_text_only

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyse this chart."},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ],
        }
    ]
    assert is_text_only(messages) is False


def test_is_text_only_mixed_str_and_list_content():
    """Messages mixing string and list content blocks: text-only only if all blocks are text."""
    from ai_analyst.core.is_text_only import is_text_only

    # system has string content, user has list with text block — should be text-only
    messages_ok = [
        {"role": "system", "content": "You are an analyst."},
        {"role": "user", "content": [{"type": "text", "text": "Analyse this."}]},
    ]
    assert is_text_only(messages_ok) is True

    # user has image block — not text-only
    messages_bad = [
        {"role": "system", "content": "System prompt."},
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}],
        },
    ]
    assert is_text_only(messages_bad) is False


# ── LOW-5: ExecutionConfig.mode Literal validation ────────────────────────────


def test_execution_config_mode_valid_values():
    """Valid mode strings must be accepted by ExecutionConfig."""
    from ai_analyst.models.execution_config import ExecutionConfig

    for mode in ("manual", "hybrid", "automated"):
        cfg = ExecutionConfig(mode=mode, analysts=[])
        assert cfg.mode == mode


def test_execution_config_mode_invalid_value_rejected():
    """Invalid mode strings must raise ValidationError (was previously accepted as plain str)."""
    from ai_analyst.models.execution_config import ExecutionConfig

    with pytest.raises(ValidationError):
        ExecutionConfig(mode="auto", analysts=[])

    with pytest.raises(ValidationError):
        ExecutionConfig(mode="MANUAL", analysts=[])
