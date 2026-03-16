"""Reflect run bundle loader (PR-REFLECT-1)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ai_analyst.api.models.reflect import ArtifactStatus, RunBundleResponse

_CONTRACT_VERSION = "2026.03"
_RUNS_DIR = Path("ai_analyst/output/runs")


class RunBundleNotFound(Exception):
    pass


def _read_json(path: Path) -> tuple[Optional[dict], str]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), "present"
    except Exception:
        return None, "malformed"


def _read_jsonl(path: Path) -> tuple[list[dict], str]:
    if not path.exists():
        return [], "missing"
    out: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                out.append(json.loads(line))
        return out, "present"
    except Exception:
        return [], "malformed"


def get_run_bundle(run_id: str, *, runs_dir: Optional[Path] = None) -> RunBundleResponse:
    base = (runs_dir or _RUNS_DIR) / run_id
    run_record, rr_state = _read_json(base / "run_record.json")
    if rr_state != "present" or not isinstance(run_record, dict):
        raise RunBundleNotFound(f"No valid run_record.json for run_id={run_id}")

    usage_json, usage_json_state = _read_json(base / "usage.json")
    usage_jsonl, usage_jsonl_state = _read_jsonl(base / "usage.jsonl")

    usage_summary = None
    if isinstance(usage_json, dict):
        usage_summary = usage_json
    elif isinstance(run_record.get("usage_summary"), dict):
        usage_summary = run_record.get("usage_summary")

    data_state = "live"
    if usage_json_state != "present" or usage_jsonl_state != "present":
        data_state = "stale"

    return RunBundleResponse(
        version=_CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_state=data_state,
        source_of_truth="run_record.json",
        run_id=run_id,
        artifact_status=ArtifactStatus(
            run_record=rr_state,
            usage_json=usage_json_state,
            usage_jsonl=usage_jsonl_state,
        ),
        run_record=run_record,
        usage_summary=usage_summary,
        usage_jsonl=usage_jsonl,
    )
