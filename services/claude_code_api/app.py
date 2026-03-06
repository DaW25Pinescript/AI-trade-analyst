import asyncio
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MAX_PROMPT_LENGTH = 65536
MAX_LOG_BYTES = 2048


_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bkey-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-+/=]{8,}\b", re.IGNORECASE),
    re.compile(r"\bOPENAI_API_KEY\s*[=:]\s*[^\s'\"]+\b", re.IGNORECASE),
    re.compile(r"\bANTHROPIC_API_KEY\s*[=:]\s*[^\s'\"]+\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_]*API_KEY\s*[=:]\s*[^\s'\"]+\b", re.IGNORECASE),
]


def _sanitize_stderr_for_log(err_text: str) -> str:
    sanitized = err_text or ""
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)

    raw_bytes = sanitized.encode("utf-8", errors="replace")
    if len(raw_bytes) > MAX_LOG_BYTES:
        clipped = raw_bytes[:MAX_LOG_BYTES].decode("utf-8", errors="ignore")
        return f"{clipped}… [truncated]"
    return sanitized

app = FastAPI(title="Claude Code API Wrapper", version="0.1.0")


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict]
    temperature: float | None = None
    max_tokens: int | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "ts_utc": datetime.now(timezone.utc).isoformat()}


@app.post("/v1/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    expected = os.getenv("CLAUDE_CODE_API_KEY")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="unauthorized")

    prompt = "\n".join(
        f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in req.messages
    )
    prompt_bytes = len(prompt.encode("utf-8", errors="replace"))
    if prompt_bytes > MAX_PROMPT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail={
                "message": "prompt exceeds maximum allowed length",
                "code": "PROMPT_TOO_LONG",
                "max_prompt_length_bytes": MAX_PROMPT_LENGTH,
            },
        )

    started = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(
        "claude",
        "-p",
        prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    timeout_s = float(os.getenv("CLAUDE_CODE_API_TIMEOUT_S", "60"))
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise HTTPException(status_code=504, detail="claude subprocess timeout")

    latency_ms = int((time.perf_counter() - started) * 1000)
    out_text = stdout.decode("utf-8", errors="replace").strip()
    err_text = stderr.decode("utf-8", errors="replace").strip()
    safe_err_text = _sanitize_stderr_for_log(err_text)

    if proc.returncode != 0:
        logger.error(
            "claude subprocess failed (exit=%d): %s",
            proc.returncode,
            safe_err_text,
        )
        raise HTTPException(
            status_code=502,
            detail={"message": "claude subprocess failed", "exit_code": proc.returncode},
        )

    if err_text:
        logger.warning("claude subprocess stderr: %s", safe_err_text)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": out_text},
                "finish_reason": "stop",
            }
        ],
        "usage": None,
        "meta": {
            "backend": "claude_code_api",
            "latency_ms": latency_ms,
            "exit_code": proc.returncode,
        },
    }
