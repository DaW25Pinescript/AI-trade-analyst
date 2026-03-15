"""Run Browser — Pydantic response models (PR-RUN-1).

Implements the contract shapes from docs/specs/PR_RUN_1_SPEC.md §6.1.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from ai_analyst.api.models.ops import ResponseMeta


RunBrowserStatus = Literal["completed", "partial", "failed"]


class RunBrowserItem(BaseModel):
    """Single projected run in the browser index (§6.3)."""

    run_id: str
    timestamp: str
    instrument: Optional[str] = None
    session: Optional[str] = None
    final_decision: Optional[str] = None
    run_status: RunBrowserStatus
    trace_available: bool


class RunBrowserResponse(ResponseMeta):
    """GET /runs/ response (§6.1)."""

    items: list[RunBrowserItem]
    page: int
    page_size: int
    total: int
    has_next: bool
