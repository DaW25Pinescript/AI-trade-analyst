"""API key authentication dependency for /analyse endpoints.

Reuses the X-API-Key pattern from services/claude_code_api/app.py.
Env var: AI_ANALYST_API_KEY — must be set; if unset all requests are rejected 401.
"""

import logging
import os

from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)


def _dev_diagnostics_enabled() -> bool:
    return (
        os.getenv("AI_ANALYST_DEV_DIAGNOSTICS", "").lower() == "true"
        or os.getenv("DEBUG", "").lower() == "true"
    )


async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """FastAPI dependency — reject requests without a valid API key.

    Raises HTTPException 401 if:
    - AI_ANALYST_API_KEY env var is not set or empty
    - X-API-Key header is missing or does not match
    """
    expected = os.getenv("AI_ANALYST_API_KEY", "")
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Run-ID") or "n/a"
    if not expected or x_api_key != expected:
        if _dev_diagnostics_enabled():
            logger.warning("[dev-stage] request_id=%s stage=auth_failed payload=%s", request_id, {"path": request.url.path})
        raise HTTPException(status_code=401, detail="unauthorized")

    if _dev_diagnostics_enabled() and request.url.path in {"/analyse", "/analyse/stream"}:
        logger.info("[dev-stage] request_id=%s stage=auth_passed payload=%s", request_id, {"path": request.url.path})
    return x_api_key
