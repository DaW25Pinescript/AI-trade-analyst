"""Run Browser — projection service (PR-RUN-1).

Scans ai_analyst/output/runs/, reads run_record.json from each directory,
and projects compact RunBrowserItem summaries.

Read-only projection. No writes, no mutations, no new storage.

Spec: docs/specs/PR_RUN_1_SPEC.md §6
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ai_analyst.api.models.ops_run_browser import (
    RunBrowserItem,
    RunBrowserResponse,
)

logger = logging.getLogger(__name__)

_CONTRACT_VERSION = "2026.03"
_RUNS_DIR = Path("ai_analyst/output/runs")
_DEFAULT_MAX_SCAN = 200
_HARD_CEILING_SCAN = 500


class RunScanError(Exception):
    """Raised when the runs directory cannot be scanned."""

    pass


def _project_one(run_dir: Path) -> Optional[RunBrowserItem]:
    """Project a single run_record.json into a RunBrowserItem.

    Returns None if the record is missing or lacks required fields.
    """
    record_path = run_dir / "run_record.json"
    if not record_path.exists():
        return None

    try:
        raw = json.loads(record_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        logger.warning("Malformed run_record.json in %s: %s", run_dir.name, exc)
        return None

    # Required fields — skip if missing
    run_id = raw.get("run_id")
    timestamp = raw.get("timestamp")
    if not run_id or not timestamp:
        return None

    # trace_available: JSON parseable + run_id present + timestamp present
    trace_available = True

    # Extract optional fields
    request = raw.get("request", {})
    instrument = request.get("instrument") if isinstance(request, dict) else None
    session = request.get("session") if isinstance(request, dict) else None

    # final_decision gated on arbiter.ran == true
    arbiter = raw.get("arbiter", {})
    final_decision = None
    if isinstance(arbiter, dict) and arbiter.get("ran") is True:
        verdict = arbiter.get("verdict")
        if isinstance(verdict, str):
            final_decision = verdict

    # Derive run_status per §6.2
    run_status = _derive_run_status(raw, arbiter)

    return RunBrowserItem(
        run_id=run_id,
        timestamp=timestamp,
        instrument=instrument,
        session=session,
        final_decision=final_decision,
        run_status=run_status,
        trace_available=trace_available,
    )


def _derive_run_status(raw: dict, arbiter: dict) -> str:
    """Derive run_status per §6.2 three-value policy aligned with trace."""
    errors = raw.get("errors", [])
    stages = raw.get("stages", [])
    analysts_failed = raw.get("analysts_failed", [])

    # failed: errors non-empty, stage failure, or analysts_failed with no arbiter verdict
    if errors:
        return "failed"

    has_stage_failure = any(
        isinstance(s, dict) and s.get("status") == "failed"
        for s in stages
        if isinstance(s, dict)
    )
    if has_stage_failure:
        return "failed"

    arbiter_ran = isinstance(arbiter, dict) and arbiter.get("ran") is True
    arbiter_verdict = isinstance(arbiter, dict) and isinstance(
        arbiter.get("verdict"), str
    )

    if analysts_failed and not (arbiter_ran and arbiter_verdict):
        return "failed"

    # completed: no errors, arbiter ran with verdict, all stages ok
    if arbiter_ran and arbiter_verdict:
        all_stages_ok = all(
            not isinstance(s, dict) or s.get("status", "ok") == "ok"
            for s in stages
        )
        if all_stages_ok:
            return "completed"

    # partial: meaningful execution evidence but not completed
    has_evidence = bool(stages) or bool(raw.get("analysts")) or isinstance(arbiter, dict) and "ran" in arbiter
    if has_evidence:
        return "partial"

    return "partial"


def project_run_browser(
    *,
    page: int = 1,
    page_size: int = 20,
    instrument: Optional[str] = None,
    session: Optional[str] = None,
    runs_dir: Optional[Path] = None,
    max_scan: int = _DEFAULT_MAX_SCAN,
) -> RunBrowserResponse:
    """Project paginated, filtered run browser response.

    Args:
        page: 1-based page number.
        page_size: Results per page (1–50).
        instrument: Optional exact-match filter.
        session: Optional exact-match filter.
        runs_dir: Override runs directory (for testing).
        max_scan: Max directories to scan.

    Raises:
        RunScanError: If the runs directory cannot be accessed.
    """
    scan_dir = runs_dir if runs_dir is not None else _RUNS_DIR
    max_scan = min(max_scan, _HARD_CEILING_SCAN)

    # Enumerate candidate directories
    try:
        if not scan_dir.exists():
            # Empty — not an error, just no runs
            return _empty_response(page, page_size)

        candidates = [
            entry
            for entry in scan_dir.iterdir()
            if entry.is_dir()
        ]
    except OSError as exc:
        raise RunScanError(f"Cannot scan runs directory: {exc}")

    # Bound: take most recent N by mtime if exceeding max
    if len(candidates) > max_scan:
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        candidates = candidates[:max_scan]

    # Project each candidate
    items: list[RunBrowserItem] = []
    skipped = 0
    for candidate in candidates:
        item = _project_one(candidate)
        if item is not None:
            items.append(item)
        else:
            skipped += 1

    # Apply filters
    if instrument is not None:
        items = [i for i in items if i.instrument == instrument]
    if session is not None:
        items = [i for i in items if i.session == session]

    # Sort newest-first by timestamp
    items.sort(key=lambda i: i.timestamp, reverse=True)

    # Paginate
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    has_next = end < total

    # data_state
    data_state = "live" if skipped == 0 else "stale"

    return RunBrowserResponse(
        version=_CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_state=data_state,
        items=page_items,
        page=page,
        page_size=page_size,
        total=total,
        has_next=has_next,
    )


def _empty_response(page: int, page_size: int) -> RunBrowserResponse:
    return RunBrowserResponse(
        version=_CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_state="live",
        items=[],
        page=page,
        page_size=page_size,
        total=0,
        has_next=False,
    )
