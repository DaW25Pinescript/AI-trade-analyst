import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

logger = logging.getLogger(__name__)

from ..models.llm_usage import LLMUsageEntry
from .claude_code_api_client import chat_completions
from .is_text_only import is_text_only
from .llm_client import acompletion_with_retry


def append_usage(run_dir: Path, entry: LLMUsageEntry) -> None:
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "usage.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
    except Exception as exc:
        # MED-4: log a warning so metering failures are visible in server logs
        # without blocking the analysis result.
        logger.warning("append_usage failed for run %s: %s", entry.run_id, exc)


def extract_usage_tokens(resp: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(resp, "usage", None)
    if usage is None and isinstance(resp, dict):
        usage = resp.get("usage")
    if usage is None:
        return None, None, None

    if isinstance(usage, dict):
        return (
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
        )

    return (
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
        getattr(usage, "total_tokens", None),
    )


def _extract_provider(resp: Any) -> str | None:
    hidden = getattr(resp, "_hidden_params", None)
    if isinstance(hidden, dict):
        return hidden.get("custom_llm_provider") or hidden.get("llm_provider")
    return None


def _extract_cost(resp: Any, model: str) -> float | None:
    try:
        from litellm import completion_cost

        return float(completion_cost(completion_response=resp, model=model))
    except Exception:
        return None


async def acompletion_metered(
    *,
    run_dir: Path,
    run_id: str,
    stage: str,
    node: str | None,
    model: str,
    messages: list[dict],
    **kwargs,
):
    """
    Metered async completion wrapper.

    Default backend is LiteLLM. When using the local Claude proxy (which exposes
    an OpenAI-compatible /v1 endpoint), we must force LiteLLM to use the
    OpenAI provider path even for claude-* model names, otherwise LiteLLM may
    infer Anthropic and hit the wrong API route.
    """
    backend_pref = os.getenv("AI_ANALYST_LLM_BACKEND", "litellm").strip().lower()
    use_claude_wrapper = backend_pref == "claude_code_api" and is_text_only(messages)

    if use_claude_wrapper:
        logger.warning(
            "Using experimental claude_code_api backend (AI_ANALYST_LLM_BACKEND=claude_code_api). "
            "This backend does not support images and provides no token usage. "
            "Prefer the default litellm backend with local Claude proxy."
        )

    backend = "claude_code_api" if use_claude_wrapper else "litellm"
    acompletion_func = chat_completions if use_claude_wrapper else None

    started = perf_counter()
    ts_utc = datetime.now(timezone.utc).isoformat()

    # Copy kwargs so we can safely inject provider/base settings.
    call_kwargs = dict(kwargs)

    # Force LiteLLM to use the OpenAI-compatible path for the local Claude proxy.
    # This is critical for claude-* model names when api_base points at the local proxy.
    if backend == "litellm":
        call_kwargs.setdefault("custom_llm_provider", "openai")

    try:
        if acompletion_func is None:
            from litellm import acompletion

            acompletion_func = acompletion

        logger.info(
            "[llm-call] run_id=%s stage=%s node=%s model=%s provider=%s api_base=%s",
            run_id,
            stage,
            node,
            model,
            call_kwargs.get("custom_llm_provider", "auto"),
            call_kwargs.get("api_base"),
        )

        # Unified fallback: acompletion_with_retry handles retries here.
        # Task-level fallback (primary → fallback model) is handled upstream.
        response, attempts = await acompletion_with_retry(
            acompletion_func,
            model=model,
            messages=messages,
            **call_kwargs,
        )
        actual_model = model

        latency_ms = int((perf_counter() - started) * 1000)
        prompt_tokens, completion_tokens, total_tokens = extract_usage_tokens(response)

        append_usage(
            run_dir,
            LLMUsageEntry(
                run_id=run_id,
                ts_utc=ts_utc,
                stage=stage,
                node=node,
                backend=backend,
                model=actual_model,
                provider=_extract_provider(response) or call_kwargs.get("custom_llm_provider"),
                success=True,
                attempts=attempts,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=_extract_cost(response, actual_model),
                error=None,
            ),
        )
        return response

    except Exception as exc:
        latency_ms = int((perf_counter() - started) * 1000)
        append_usage(
            run_dir,
            LLMUsageEntry(
                run_id=run_id,
                ts_utc=ts_utc,
                stage=stage,
                node=node,
                backend=backend,
                model=model,
                provider=call_kwargs.get("custom_llm_provider"),
                success=False,
                attempts=max(1, int(call_kwargs.get("max_retries", 2)) + 1),
                latency_ms=latency_ms,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                cost_usd=None,
                error=str(exc),
            ),
        )
        raise


def check_run_cost_ceiling(run_dir: Path, max_cost_usd: float) -> None:
    """
    Raise ValueError if the total cost for a completed run exceeds max_cost_usd.

    Fail-soft: if the usage file is missing or cost data is unavailable (e.g.
    provider does not return pricing), the check is skipped — it never blocks
    a successful analysis result.
    """
    try:
        summary = summarize_usage(run_dir)
        total = summary.get("total_cost_usd", 0.0)
        if isinstance(total, (int, float)) and total > max_cost_usd:
            raise ValueError(
                f"Run cost ${total:.4f} USD exceeded the configured ceiling of "
                f"${max_cost_usd:.2f} USD. Set MAX_COST_PER_RUN_USD to a higher value "
                "or review chart sizes and lens configuration."
            )
    except ValueError:
        raise
    except Exception:
        # Missing file, parse error, etc. — do not block the response.
        return


def summarize_usage(run_dir: Path) -> dict:
    path = run_dir / "usage.jsonl"
    summary = {
        "total_calls": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "calls_by_stage": {},
        "calls_by_node": {},
        "calls_by_model": {},
        "calls_by_provider": {},
        "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "calls_with_token_usage": 0,
        "calls_without_token_usage": 0,
        "total_cost_usd": 0.0,
    }
    if not path.exists():
        return summary

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            summary["total_calls"] += 1
            if row.get("success") is False:
                summary["failed_calls"] += 1
            else:
                summary["successful_calls"] += 1

            stage = row.get("stage")
            node = row.get("node")
            model = row.get("model")
            provider = row.get("provider")
            summary["calls_by_stage"][stage] = summary["calls_by_stage"].get(stage, 0) + 1
            summary["calls_by_node"][node] = summary["calls_by_node"].get(node, 0) + 1
            summary["calls_by_model"][model] = summary["calls_by_model"].get(model, 0) + 1
            summary["calls_by_provider"][provider] = summary["calls_by_provider"].get(provider, 0) + 1

            has_usage = False

            for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = row.get(k)
                if isinstance(value, int):
                    summary["tokens"][k] += value
                    has_usage = True

            if has_usage:
                summary["calls_with_token_usage"] += 1
            else:
                summary["calls_without_token_usage"] += 1

            cost = row.get("cost_usd")
            if isinstance(cost, (float, int)):
                summary["total_cost_usd"] += float(cost)

    return summary