import json
from types import SimpleNamespace

import pytest

from ai_analyst.core.is_text_only import is_text_only
from ai_analyst.core.run_paths import get_run_dir
from ai_analyst.core.usage_meter import acompletion_metered


@pytest.mark.asyncio
async def test_text_only_routes_to_wrapper(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_ANALYST_LLM_BACKEND", "claude_code_api")

    async def fake_wrapper(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
            usage=None,
            _hidden_params={"llm_provider": "claude_code_api"},
        )

    monkeypatch.setattr("ai_analyst.core.usage_meter.chat_completions", fake_wrapper)

    run_id = "route-text"
    run_dir = tmp_path / get_run_dir(run_id)
    await acompletion_metered(
        run_dir=run_dir,
        run_id=run_id,
        stage="arbiter",
        node="test",
        model="claude",
        messages=[{"role": "user", "content": "hello"}],
    )

    usage_lines = (run_dir / "usage.jsonl").read_text().splitlines()
    row = json.loads(usage_lines[0])
    assert row["backend"] == "claude_code_api"


@pytest.mark.asyncio
async def test_multimodal_does_not_route_to_wrapper(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_ANALYST_LLM_BACKEND", "claude_code_api")

    async def fake_litellm(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
            usage=None,
            _hidden_params={"llm_provider": "litellm"},
        )

    monkeypatch.setattr("litellm.acompletion", fake_litellm)

    run_id = "route-mm"
    run_dir = tmp_path / get_run_dir(run_id)
    await acompletion_metered(
        run_dir=run_dir,
        run_id=run_id,
        stage="phase1_analyst",
        node="test",
        model="gpt-4o",
        messages=[{"role": "user", "content": [{"type": "image_url", "image_url": "x"}]}],
    )

    usage_lines = (run_dir / "usage.jsonl").read_text().splitlines()
    row = json.loads(usage_lines[0])
    assert row["backend"] == "litellm"


def test_is_text_only():
    assert is_text_only([{"role": "user", "content": "hello"}])
    # MED-7 fix: list-format content with only text blocks is now correctly treated
    # as text-only so it can be routed to the claude_code_api backend.
    assert is_text_only([{"role": "user", "content": [{"type": "text", "text": "x"}]}])
    # Images still block text-only routing
    assert not is_text_only([
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]}
    ])
