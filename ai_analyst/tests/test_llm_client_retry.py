from types import SimpleNamespace

import pytest

from ai_analyst.core.llm_client import acompletion_with_retry


@pytest.mark.asyncio
async def test_acompletion_with_retry_succeeds_after_transient_failure():
    calls = {"count": 0}

    async def flaky_completion(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    result = await acompletion_with_retry(
        flaky_completion,
        max_retries=2,
        retry_backoff_s=0,
        timeout_s=0.5,
        model="dummy",
    )

    assert result.choices[0].message.content == "{}"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_acompletion_with_retry_raises_after_exhausting_retries():
    async def always_fail(**_kwargs):
        raise ValueError("permanent")

    with pytest.raises(RuntimeError, match=r"failed after 2 attempt\(s\)"):
        await acompletion_with_retry(
            always_fail,
            max_retries=1,
            retry_backoff_s=0,
            timeout_s=0.5,
            model="dummy",
        )
