import asyncio
from typing import Any, Callable

DEFAULT_LLM_TIMEOUT_S = 45.0
DEFAULT_LLM_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_S = 0.4


async def acompletion_with_retry(
    acompletion_func: Callable[..., Any],
    *,
    timeout_s: float = DEFAULT_LLM_TIMEOUT_S,
    max_retries: int = DEFAULT_LLM_MAX_RETRIES,
    retry_backoff_s: float = DEFAULT_RETRY_BACKOFF_S,
    **kwargs,
) -> Any:
    """
    Execute an async LiteLLM completion call with timeout + bounded retries.

    Retries happen for any exception (including timeout), using linear backoff:
    retry_backoff_s * attempt_number.
    """
    attempts = max(1, max_retries + 1)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return await asyncio.wait_for(acompletion_func(**kwargs), timeout=timeout_s)
        except Exception as exc:  # noqa: BLE001 - surface original provider/runtime failures
            last_error = exc
            if attempt >= attempts:
                break
            await asyncio.sleep(retry_backoff_s * attempt)

    raise RuntimeError(
        f"LLM call failed after {attempts} attempt(s): {last_error}"
    ) from last_error
