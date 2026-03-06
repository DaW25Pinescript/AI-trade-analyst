import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from services.claude_code_api.app import app


def test_prompt_over_64kb_is_rejected(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_API_KEY", "test-key")

    called = {"value": False}

    async def _fake_subprocess(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("subprocess should not be called for oversized prompts")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subprocess)

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": "test-key"},
            json={
                "model": "claude",
                "messages": [{"role": "user", "content": "A" * 70000}],
            },
        )

    assert response.status_code == 413
    body = response.json()["detail"]
    assert body["code"] == "PROMPT_TOO_LONG"
    assert body["max_prompt_length_bytes"] == 65536
    assert called["value"] is False


def test_stderr_is_sanitized_and_truncated(monkeypatch, caplog):
    monkeypatch.setenv("CLAUDE_CODE_API_KEY", "test-key")

    long_stderr = (
        "Bearer secret-token-123 sk-abcdef123456 key-abcdef123456 "
        "OPENAI_API_KEY=supersecretvalue "
        + ("x" * 3000)
    )

    class _Proc:
        returncode = 0

        async def communicate(self):
            return b"ok", long_stderr.encode("utf-8")

    async def _fake_subprocess(*_args, **_kwargs):
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subprocess)

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": "test-key"},
            json={
                "model": "claude",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 200
    warning_records = [r for r in caplog.records if "claude subprocess stderr" in r.getMessage()]
    assert warning_records
    message = warning_records[-1].getMessage()
    assert "secret-token-123" not in message
    assert "sk-abcdef123456" not in message
    assert "key-abcdef123456" not in message
    assert "OPENAI_API_KEY=supersecretvalue" not in message
    assert "[REDACTED]" in message
    assert "[truncated]" in message
