import asyncio
import random
from typing import Any, Callable

DEFAULT_LLM_TIMEOUT_S = 45.0
DEFAULT_LLM_MAX_RETRIES = 2
DEFAULT_BASE_BACKOFF_S = 1.0
DEFAULT_MAX_BACKOFF_S = 60.0

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
