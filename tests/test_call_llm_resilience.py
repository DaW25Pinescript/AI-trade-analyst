"""Deterministic resilience tests for analyst/analyst.py call_llm().

Covers AC-6 (timeout), AC-7 (retry), AC-8 (failure mapping), AC-9 (resilience).
All tests are deterministic — no live LLM calls or provider dependency.
"""

import json
import types
from unittest.mock import MagicMock, patch

import pytest

from analyst.analyst import (
    LLM_CALL_MAX_RETRIES,
    LLM_CALL_TIMEOUT_S,
    _call_provider,
    _is_retriable,
    call_llm,
    parse_llm_response,
)


# ── AC-6: call_llm timeout tests ────────────────────────────────────────────

class TestCallLlmTimeout:
    """AC-6: call_llm() has an explicit timeout boundary."""

    def test_timeout_param_passed_to_litellm(self):
        """Verify litellm.completion is called with timeout parameter."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"verdict":{}, "reasoning":{}}'))]

        mock_litellm = types.ModuleType("litellm")
        mock_litellm.completion = MagicMock(return_value=mock_response)

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            result = _call_provider("gpt-4o-mini", [{"role": "user", "content": "test"}])

        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs.get("timeout") == LLM_CALL_TIMEOUT_S or \
               (call_kwargs[1].get("timeout") == LLM_CALL_TIMEOUT_S)

    def test_timeout_produces_runtime_error(self):
        """AC-6: Timeout produces deterministic RuntimeError."""
        class FakeTimeoutError(Exception):
            pass

        # Make _is_retriable return True for this (it's a timeout)
        mock_litellm = types.ModuleType("litellm")

        class APITimeoutError(Exception):
            pass

        mock_litellm.completion = MagicMock(side_effect=APITimeoutError("timed out"))

        with patch.dict("sys.modules", {"litellm": mock_litellm}), \
             patch("analyst.analyst.LLM_CALL_MAX_RETRIES", 0):
            with pytest.raises(RuntimeError, match="LLM call failed"):
                call_llm("system", "user")


# ── AC-7: call_llm retry tests ──────────────────────────────────────────────

class TestCallLlmRetry:
    """AC-7: call_llm() retries only bounded transient failures."""

    def test_retries_transient_then_succeeds(self):
        """Transient failure followed by success returns result."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

        call_count = 0

        class TransientError(Exception):
            status_code = 503

        def _mock_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TransientError("service unavailable")
            return mock_response

        mock_litellm = types.ModuleType("litellm")
        mock_litellm.completion = _mock_completion

        with patch.dict("sys.modules", {"litellm": mock_litellm}), \
             patch("analyst.analyst.time") as mock_time:
            mock_time.sleep = MagicMock()  # Don't actually sleep
            result = call_llm("system", "user")

        assert result == "ok"
        assert call_count == 2
        mock_time.sleep.assert_called_once()

    def test_no_retry_on_non_retriable_error(self):
        """Non-retriable errors fail immediately without retry."""
        call_count = 0

        class AuthError(Exception):
            """Simulates a 401 auth error — should not be retried."""
            pass

        def _mock_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            raise AuthError("invalid API key")

        mock_litellm = types.ModuleType("litellm")
        mock_litellm.completion = _mock_completion

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            with pytest.raises(RuntimeError, match="LLM call failed"):
                call_llm("system", "user")

        # Should have tried only once (no retries for non-retriable errors)
        assert call_count == 1

    def test_max_retries_bounded(self):
        """After max retries, raises RuntimeError with attempt count."""
        call_count = 0

        class ServiceUnavailableError(Exception):
            status_code = 503

        def _mock_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            raise ServiceUnavailableError("down")

        mock_litellm = types.ModuleType("litellm")
        mock_litellm.completion = _mock_completion

        with patch.dict("sys.modules", {"litellm": mock_litellm}), \
             patch("analyst.analyst.time") as mock_time:
            mock_time.sleep = MagicMock()
            with pytest.raises(RuntimeError, match="LLM call failed after"):
                call_llm("system", "user")

        # Should have tried 1 + LLM_CALL_MAX_RETRIES times
        assert call_count == 1 + LLM_CALL_MAX_RETRIES


# ── AC-8: Failure mapping tests ─────────────────────────────────────────────

class TestFailureMapping:
    """AC-8: Repeated provider failure becomes deterministic RuntimeError."""

    def test_provider_error_mapped_to_runtime_error(self):
        """Provider-specific exception is mapped to RuntimeError."""
        class ProviderSpecificError(Exception):
            status_code = 500

        mock_litellm = types.ModuleType("litellm")
        mock_litellm.completion = MagicMock(side_effect=ProviderSpecificError("internal"))

        with patch.dict("sys.modules", {"litellm": mock_litellm}), \
             patch("analyst.analyst.time") as mock_time:
            mock_time.sleep = MagicMock()
            with pytest.raises(RuntimeError) as exc_info:
                call_llm("system", "user")

        # RuntimeError message should include type name but not raw provider detail
        assert "ProviderSpecificError" in str(exc_info.value)
        # Should NOT contain the raw "internal" message (internal detail)
        assert "internal" not in str(exc_info.value).lower().replace("internalservererror", "")

    def test_import_error_still_produces_runtime_error(self):
        """If no LLM client is available, RuntimeError is raised."""
        with patch.dict("sys.modules", {"litellm": None, "openai": None}):
            with pytest.raises(RuntimeError, match="No LLM client available"):
                _call_provider("gpt-4o-mini", [{"role": "user", "content": "test"}])


# ── AC-9: Resilience — malformed response tests ─────────────────────────────

class TestMalformedResponse:
    """AC-9: Malformed / non-JSON LLM response is handled deterministically."""

    def test_non_json_response_raises_value_error(self):
        with pytest.raises((json.JSONDecodeError, ValueError)):
            parse_llm_response("This is not JSON at all")

    def test_missing_verdict_key_raises_value_error(self):
        with pytest.raises(ValueError, match="missing 'verdict' key"):
            parse_llm_response('{"reasoning": {}}')

    def test_missing_reasoning_key_raises_value_error(self):
        with pytest.raises(ValueError, match="missing 'reasoning' key"):
            parse_llm_response('{"verdict": {}}')

    def test_markdown_fenced_json_parsed_correctly(self):
        raw = '```json\n{"verdict": {"v": 1}, "reasoning": {"r": 1}}\n```'
        verdict, reasoning = parse_llm_response(raw)
        assert verdict == {"v": 1}
        assert reasoning == {"r": 1}


# ── _is_retriable unit tests ────────────────────────────────────────────────

class TestIsRetriable:

    def test_timeout_error_is_retriable(self):
        class TimeoutError(Exception):
            pass
        assert _is_retriable(TimeoutError())

    def test_connection_error_is_retriable(self):
        class ConnectionError(Exception):
            pass
        assert _is_retriable(ConnectionError())

    def test_status_429_is_retriable(self):
        exc = Exception("rate limited")
        exc.status_code = 429
        assert _is_retriable(exc)

    def test_status_503_is_retriable(self):
        exc = Exception("unavailable")
        exc.status_code = 503
        assert _is_retriable(exc)

    def test_status_400_not_retriable(self):
        exc = Exception("bad request")
        exc.status_code = 400
        assert not _is_retriable(exc)

    def test_generic_exception_not_retriable(self):
        assert not _is_retriable(ValueError("bad"))
