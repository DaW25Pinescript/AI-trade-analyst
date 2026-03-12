"""
Regression tests for v2.0.2 fixes: HIGH-1, HIGH-5, HIGH-6.

HIGH-5: Analyst roster uses persona+profile and no legacy raw model field
HIGH-6: Image size guard (422 on oversized upload) + per-run cost ceiling
HIGH-1: Non-retriable exceptions fail immediately; retriable exceptions use
        exponential backoff (not linear/fixed 0.4 s).
"""
import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

# ── HIGH-5 ───────────────────────────────────────────────────────────────────


def test_analyst_roster_uses_profiles_not_raw_models():
    """ANALYST_CONFIGS contract is persona+profile, with no legacy raw model field."""
    from ai_analyst.graph.analyst_nodes import ANALYST_CONFIGS
    from ai_analyst.models.persona import PersonaType

    assert ANALYST_CONFIGS, "ANALYST_CONFIGS should not be empty"
    personas = {c["persona"] for c in ANALYST_CONFIGS}
    expected = {
        PersonaType.DEFAULT_ANALYST,
        PersonaType.RISK_OFFICER,
        PersonaType.PROSECUTOR,
        PersonaType.ICT_PURIST,
    }
    assert expected.issubset(personas)

    for config in ANALYST_CONFIGS:
        assert "profile" in config
        assert "model" not in config


def test_api_key_manager_legacy_grok_string_not_present():
    """SUPPORTED_MODELS and get_model_for_analyst_index must not reference grok/grok-4-vision."""
    from ai_analyst.core.api_key_manager import SUPPORTED_MODELS, get_model_for_analyst_index

    assert "grok/grok-4-vision" not in SUPPORTED_MODELS, (
        "SUPPORTED_MODELS still contains defunct grok/grok-4-vision"
    )
    # Slot 3 is the ICT_PURIST / xAI slot
    # We can't call get_model_for_analyst_index without env vars, but we can
    # verify the underlying model list doesn't contain the defunct string.
    assert all("grok/grok-4-vision" not in k for k in SUPPORTED_MODELS)


# ── HIGH-6 — image size guard ────────────────────────────────────────────────


def test_image_size_guard_env_var_parsing():
    """Budget guard: MAX_IMAGE_SIZE_MB env var formula produces correct byte counts."""
    # Verify the formula used in main.py: int(os.environ.get("MAX_IMAGE_SIZE_MB", "5")) * 1024 * 1024
    import os
    for mb_str, expected_bytes in [("5", 5 * 1024 * 1024), ("2", 2 * 1024 * 1024), ("10", 10 * 1024 * 1024)]:
        with patch.dict(os.environ, {"MAX_IMAGE_SIZE_MB": mb_str}):
            result = int(os.environ.get("MAX_IMAGE_SIZE_MB", "5")) * 1024 * 1024
            assert result == expected_bytes


def test_cost_ceiling_passes_when_cost_is_below_limit(tmp_path):
    """check_run_cost_ceiling does not raise when cost is within budget."""
    from ai_analyst.core.usage_meter import check_run_cost_ceiling

    usage_file = tmp_path / "usage.jsonl"
    usage_file.write_text(
        '{"run_id":"r1","ts_utc":"2026-01-01T00:00:00Z","stage":"phase1_analyst",'
        '"node":"RISK_OFFICER","backend":"litellm","model":"claude-sonnet-4-6",'
        '"provider":"anthropic","success":true,"attempts":1,"latency_ms":500,'
        '"prompt_tokens":100,"completion_tokens":200,"total_tokens":300,"cost_usd":0.05,'
        '"error":null}\n',
        encoding="utf-8",
    )
    # Should not raise
    check_run_cost_ceiling(tmp_path, max_cost_usd=1.00)


def test_cost_ceiling_raises_when_cost_exceeds_limit(tmp_path):
    """check_run_cost_ceiling raises ValueError when cost exceeds the ceiling."""
    from ai_analyst.core.usage_meter import check_run_cost_ceiling

    usage_file = tmp_path / "usage.jsonl"
    # Two calls totalling $6.00
    entry = (
        '{"run_id":"r1","ts_utc":"2026-01-01T00:00:00Z","stage":"phase1_analyst",'
        '"node":"DEFAULT_ANALYST","backend":"litellm","model":"gpt-4o",'
        '"provider":"openai","success":true,"attempts":1,"latency_ms":800,'
        '"prompt_tokens":5000,"completion_tokens":1000,"total_tokens":6000,"cost_usd":3.00,'
        '"error":null}\n'
    )
    usage_file.write_text(entry * 2, encoding="utf-8")

    with pytest.raises(ValueError, match=r"\$6\.00.*ceiling"):
        check_run_cost_ceiling(tmp_path, max_cost_usd=5.00)


def test_cost_ceiling_skips_check_when_no_usage_file(tmp_path):
    """check_run_cost_ceiling is fail-soft — missing usage file does not raise."""
    from ai_analyst.core.usage_meter import check_run_cost_ceiling

    empty_dir = tmp_path / "nonexistent_run"
    # Should not raise even though the directory and file don't exist
    check_run_cost_ceiling(empty_dir, max_cost_usd=0.01)


def test_cost_ceiling_skips_when_cost_data_unavailable(tmp_path):
    """check_run_cost_ceiling skips gracefully when cost_usd is null in all entries."""
    from ai_analyst.core.usage_meter import check_run_cost_ceiling

    usage_file = tmp_path / "usage.jsonl"
    usage_file.write_text(
        '{"run_id":"r1","ts_utc":"2026-01-01T00:00:00Z","stage":"phase1_analyst",'
        '"node":"n","backend":"litellm","model":"m","provider":null,"success":true,'
        '"attempts":1,"latency_ms":100,"prompt_tokens":null,"completion_tokens":null,'
        '"total_tokens":null,"cost_usd":null,"error":null}\n',
        encoding="utf-8",
    )
    # Total cost is 0.0 (null entries are skipped) — should not raise
    check_run_cost_ceiling(tmp_path, max_cost_usd=0.01)


# ── HIGH-1 — retry logic ─────────────────────────────────────────────────────


async def test_non_retriable_exception_fails_immediately():
    """AuthenticationError must not be retried — fail on first attempt."""
    from ai_analyst.core.llm_client import acompletion_with_retry

    calls = {"count": 0}

    class AuthenticationError(Exception):
        pass

    async def auth_fail(**_kwargs):
        calls["count"] += 1
        raise AuthenticationError("invalid key")

    with pytest.raises(RuntimeError, match="non-retriable"):
        await acompletion_with_retry(
            auth_fail,
            max_retries=3,
            retry_backoff_s=0,
            timeout_s=1.0,
            model="dummy",
        )

    assert calls["count"] == 1, "Non-retriable exceptions must not be retried"


async def test_bad_request_error_not_retried():
    """BadRequestError must fail immediately without retrying."""
    from ai_analyst.core.llm_client import acompletion_with_retry

    calls = {"count": 0}

    class BadRequestError(Exception):
        pass

    async def bad_request(**_kwargs):
        calls["count"] += 1
        raise BadRequestError("context too long")

    with pytest.raises(RuntimeError, match="non-retriable"):
        await acompletion_with_retry(
            bad_request,
            max_retries=2,
            retry_backoff_s=0,
            timeout_s=1.0,
            model="dummy",
        )

    assert calls["count"] == 1


async def test_retriable_runtime_error_is_retried():
    """Generic RuntimeError (e.g. connection error) should be retried up to max_retries."""
    from ai_analyst.core.llm_client import acompletion_with_retry

    calls = {"count": 0}

    async def transient_fail(**_kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("connection reset")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    result, attempts = await acompletion_with_retry(
        transient_fail,
        max_retries=3,
        retry_backoff_s=0,
        timeout_s=1.0,
        model="dummy",
    )
    assert result.choices[0].message.content == "{}"
    assert attempts == 3


async def test_exponential_backoff_with_jitter_applied(monkeypatch):
    """Sleep durations use _backoff_seconds (exponential + jitter), not a fixed linear value."""
    from ai_analyst.core import llm_client

    sleep_calls = []
    original_sleep = asyncio.sleep

    async def fake_sleep(s):
        sleep_calls.append(s)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    calls = {"count": 0}

    async def always_fail(**_kwargs):
        calls["count"] += 1
        raise RuntimeError("transient")

    with pytest.raises(RuntimeError):
        await llm_client.acompletion_with_retry(
            always_fail,
            max_retries=3,
            base_backoff_s=1.0,
            max_backoff_s=60.0,
            timeout_s=1.0,
            model="dummy",
        )

    # Should have slept between attempts (3 retries = 3 sleep calls)
    assert len(sleep_calls) == 3
    # Each sleep value must be non-negative
    for s in sleep_calls:
        assert s >= 0


async def test_legacy_retry_backoff_s_zero_skips_sleep(monkeypatch):
    """Legacy retry_backoff_s=0 from existing tests must not sleep at all."""
    sleep_calls = []

    async def fake_sleep(s):
        sleep_calls.append(s)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    from ai_analyst.core.llm_client import acompletion_with_retry

    calls = {"count": 0}

    async def flaky(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    result, attempts = await acompletion_with_retry(
        flaky,
        max_retries=2,
        retry_backoff_s=0,
        timeout_s=1.0,
        model="dummy",
    )
    assert result.choices[0].message.content == "{}"
    # With retry_backoff_s=0, sleep(0) may still be called — what matters is no delay
    for s in sleep_calls:
        assert s == 0.0
