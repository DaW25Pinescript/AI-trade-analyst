import os
from types import SimpleNamespace

import httpx


async def chat_completions(model: str, messages: list[dict], **kwargs):
    base_url = os.getenv("CLAUDE_CODE_API_URL", "http://127.0.0.1:8787").rstrip("/")
    api_key = os.getenv("CLAUDE_CODE_API_KEY", "")
    url = f"{base_url}/v1/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": kwargs.get("temperature"),
        "max_tokens": kwargs.get("max_tokens"),
        "response_format": kwargs.get("response_format"),
    }

    async with httpx.AsyncClient(timeout=kwargs.get("timeout_s", 45.0)) as client:
        response = await client.post(url, json=payload, headers={"X-API-Key": api_key})
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage")
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=usage,
        _hidden_params={"llm_provider": "claude_code_api"},
    )
