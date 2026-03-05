import asyncio
import logging
import os
import random
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_LLM_TIMEOUT_S = 45.0
DEFAULT_LLM_MAX_RETRIES = 2
DEFAULT_BASE_BACKOFF_S = 1.0
DEFAULT_MAX_BACKOFF_S = 60.0

# Phase 7 — Fallback model routing.
# Maps primary models to fallback alternatives tried when the primary exhausts retries.
# Configurable via FALLBACK_MODEL_MAP env var (JSON), otherwise uses sensible defaults.
_DEFAULT_FALLBACK_MAP: dict[str, list[str]] = {
    "claude-sonnet-4-20250514": ["claude-haiku-4-5-20251001", "gpt-4o-mini"],
    "claude-opus-4-20250514": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
    "gpt-4o": ["gpt-4o-mini", "claude-haiku-4-5-20251001"],
    "gpt-4o-mini": ["claude-haiku-4-5-20251001"],
    "claude-haiku-4-5-20251001": ["gpt-4o-mini"],
}


def get_fallback_models(primary_model: str) -> list[str]:
    """
    Return the ordered list of fallback models for a given primary model.

    Reads from FALLBACK_MODEL_MAP env var (JSON dict) if set, otherwise
    uses _DEFAULT_FALLBACK_MAP. Returns empty list if no fallbacks defined.
    """
    env_map = os.getenv("FALLBACK_MODEL_MAP")
    if env_map:
        try:
            import json
            custom_map = json.loads(env_map)
            if isinstance(custom_map, dict):
                return list(custom_map.get(primary_model, []))
        except (ValueError, TypeError):
            logger.warning("FALLBACK_MODEL_MAP env var is not valid JSON — using defaults.")
    return list(_DEFAULT_FALLBACK_MAP.get(primary_model, []))

# Exception class names that should never be retried — the same request will
# always fail, and retrying only wastes quota or compounds authentication debt.
_NON_RETRIABLE_EXCEPTION_NAMES = frozenset({
    "AuthenticationError",
    "BadRequestError",
    "InvalidRequestError",
    "PermissionDeniedError",
    "NotFoundError",
    "ContextWindowExceededError",
    "ContentPolicyViolationError",
    "UnprocessableEntityError",
})


def _is_retriable(exc: Exception) -> bool:
    """
    Return True if the exception is transient and worth retrying.

    Non-retriable exceptions (auth failures, bad requests, validation errors)
    will always produce the same result — retrying them is wasteful and can
    mask root-cause issues. Everything else (rate limits, connection errors,
    timeouts, provider 5xx) is worth retrying.
    """
    # asyncio.TimeoutError (from wait_for) is always retriable
    if isinstance(exc, asyncio.TimeoutError):
        return True
    exc_name = type(exc).__name__
    return exc_name not in _NON_RETRIABLE_EXCEPTION_NAMES


def _backoff_seconds(attempt: int, base: float, maximum: float) -> float:
    """Exponential backoff with full jitter: uniform(0, min(max, base * 2^attempt))."""
    ceiling = min(maximum, base * (2 ** attempt))
    return random.uniform(0, ceiling)


async def acompletion_with_retry(
    acompletion_func: Callable[..., Any],
    *,
    timeout_s: float = DEFAULT_LLM_TIMEOUT_S,
    max_retries: int = DEFAULT_LLM_MAX_RETRIES,
    # Legacy parameter kept for backwards-compatibility with existing tests.
    # When provided, overrides base_backoff_s so old callers see no change.
    retry_backoff_s: float | None = None,
    base_backoff_s: float = DEFAULT_BASE_BACKOFF_S,
    max_backoff_s: float = DEFAULT_MAX_BACKOFF_S,
    **kwargs,
) -> tuple[Any, int]:
    """
    Execute an async LiteLLM completion call with timeout + bounded retries.

    Retry policy:
    - Non-retriable exceptions (AuthenticationError, BadRequestError, etc.) fail
      immediately without retrying — the same request will always fail.
    - Retriable exceptions (RateLimitError, ConnectError, TimeoutError, 5xx) are
      retried with exponential backoff and full jitter up to max_backoff_s.

    Returns (response, attempt_count).
    """
    # Backwards-compat: if caller passed the old retry_backoff_s, use it as a
    # fixed base so existing test helpers (retry_backoff_s=0) still work.
    effective_base = retry_backoff_s if retry_backoff_s is not None else base_backoff_s
    effective_max = retry_backoff_s if retry_backoff_s is not None else max_backoff_s

    attempts = max(1, max_retries + 1)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            response = await asyncio.wait_for(acompletion_func(**kwargs), timeout=timeout_s)
            return response, attempt
        except Exception as exc:  # noqa: BLE001
            if not _is_retriable(exc):
                raise RuntimeError(
                    f"LLM call failed with non-retriable error on attempt {attempt}: {exc}"
                ) from exc
            last_error = exc
            if attempt >= attempts:
                break
            sleep_s = _backoff_seconds(attempt, effective_base, effective_max)
            await asyncio.sleep(sleep_s)

    raise RuntimeError(
        f"LLM call failed after {attempts} attempt(s): {last_error}"
    ) from last_error


async def acompletion_with_fallback(
    acompletion_func: Callable[..., Any],
    *,
    timeout_s: float = DEFAULT_LLM_TIMEOUT_S,
    max_retries: int = DEFAULT_LLM_MAX_RETRIES,
    retry_backoff_s: float | None = None,
    base_backoff_s: float = DEFAULT_BASE_BACKOFF_S,
    max_backoff_s: float = DEFAULT_MAX_BACKOFF_S,
    **kwargs,
) -> tuple[Any, int, str]:
    """
    Phase 7 — Execute an LLM call with automatic fallback to secondary models.

    Tries the primary model first via acompletion_with_retry. If all retries
    fail, iterates through fallback models (each with their own retry cycle).

    Returns (response, total_attempts, model_used).
    """
    primary_model = kwargs.get("model", "")
    fallbacks = get_fallback_models(primary_model)
    total_attempts = 0
    last_error: Exception | None = None

    # Try primary model
    try:
        response, attempts = await acompletion_with_retry(
            acompletion_func,
            timeout_s=timeout_s,
            max_retries=max_retries,
            retry_backoff_s=retry_backoff_s,
            base_backoff_s=base_backoff_s,
            max_backoff_s=max_backoff_s,
            **kwargs,
        )
        return response, attempts, primary_model
    except RuntimeError as primary_err:
        last_error = primary_err
        total_attempts += max(1, max_retries + 1)
        if not fallbacks:
            raise
        logger.warning(
            "Primary model '%s' failed after retries: %s. Trying fallbacks: %s",
            primary_model, primary_err, fallbacks,
        )

    # Try each fallback model
    for fb_model in fallbacks:
        fb_kwargs = {**kwargs, "model": fb_model}
        try:
            response, attempts = await acompletion_with_retry(
                acompletion_func,
                timeout_s=timeout_s,
                max_retries=max_retries,
                retry_backoff_s=retry_backoff_s,
                base_backoff_s=base_backoff_s,
                max_backoff_s=max_backoff_s,
                **fb_kwargs,
            )
            total_attempts += attempts
            logger.info(
                "Fallback model '%s' succeeded after %d total attempts.",
                fb_model, total_attempts,
            )
            return response, total_attempts, fb_model
        except RuntimeError as fb_err:
            total_attempts += max(1, max_retries + 1)
            last_error = fb_err
            logger.warning(
                "Fallback model '%s' also failed: %s", fb_model, fb_err,
            )

    raise RuntimeError(
        f"All models failed (primary '{primary_model}' + {len(fallbacks)} fallbacks). "
        f"Total attempts: {total_attempts}. Last error: {last_error}"
    ) from last_error
