"""API key authentication dependency for /analyse endpoints.

Reuses the X-API-Key pattern from services/claude_code_api/app.py.
Env var: AI_ANALYST_API_KEY — must be set; if unset all requests are rejected 401.
"""

import os

from fastapi import Header, HTTPException


async def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """FastAPI dependency — reject requests without a valid API key.

    Raises HTTPException 401 if:
    - AI_ANALYST_API_KEY env var is not set or empty
    - X-API-Key header is missing or does not match
    """
    expected = os.getenv("AI_ANALYST_API_KEY", "")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="unauthorized")
    return x_api_key
