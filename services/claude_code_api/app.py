import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

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

    if proc.returncode != 0:
        logger.error(
            "claude subprocess failed (exit=%d): %s",
            proc.returncode,
            err_text,
        )
        raise HTTPException(
            status_code=502,
            detail={"message": "claude subprocess failed", "exit_code": proc.returncode},
        )

    if err_text:
        logger.warning("claude subprocess stderr: %s", err_text)

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
