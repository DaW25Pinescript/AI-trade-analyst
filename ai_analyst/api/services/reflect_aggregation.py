"""Reflect aggregation service (PR-REFLECT-1)."""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ai_analyst.api.models.reflect import (
    PatternBucket,
    PatternSummaryResponse,
    PersonaPerformanceResponse,
    PersonaStats,
    ScanBounds,
    VerdictCount,
)

logger = logging.getLogger(__name__)

_CONTRACT_VERSION = "2026.03"
_RUNS_DIR = Path("ai_analyst/output/runs")
_AUDIT_DIR = Path("ai_analyst/logs/runs")
_THRESHOLD = 10

_DIRECTIONAL_STANCE_TO_VERDICTS = {
    "bullish": {"BUY", "ENTER_LONG"},
    "bearish": {"SELL", "ENTER_SHORT"},
}


class ReflectScanError(Exception):
    pass


def _parse_ts(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_audit_entry(run_id: str, audit_dir: Path) -> Optional[dict]:
    path = audit_dir / f"{run_id}.jsonl"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if item.get("run_id") == run_id:
                    return item
    except Exception as exc:
        logger.warning("Reflect audit read failed for %s: %s", run_id, exc)
    return None


def _persona_key(analyst: dict) -> Optional[str]:
    # fallback: entity_id -> persona_id -> persona -> normalized name
    for key in ("entity_id", "persona_id", "persona"):
        value = analyst.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    name = analyst.get("name")
    if isinstance(name, str) and name.strip():
        return "_".join(name.lower().split())
    return None


def _ordered_candidate_dirs(runs_dir: Path) -> list[Path]:
    try:
        dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    except OSError as exc:
        raise ReflectScanError(f"Cannot scan runs directory: {exc}")
    dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return dirs


def _load_valid_runs(max_runs: int, runs_dir: Path, audit_dir: Path) -> tuple[list[dict], int, int, int]:
    if not runs_dir.exists():
        return [], 0, 0, 0

    inspected = 0
    skipped = 0
    valid: list[dict] = []
    missing_audit = 0

    for run_dir in _ordered_candidate_dirs(runs_dir)[:max_runs]:
        inspected += 1
        rr_path = run_dir / "run_record.json"
        raw = _read_json(rr_path)
        if not raw:
            skipped += 1
            continue

        run_id = raw.get("run_id")
        timestamp = raw.get("timestamp")
        request = raw.get("request") if isinstance(raw.get("request"), dict) else {}
        instrument = request.get("instrument")
        session = request.get("session")

        if not (run_id and timestamp and instrument and session):
            skipped += 1
            continue

        ts = _parse_ts(timestamp)
        if ts is None:
            skipped += 1
            continue

        audit_entry = _read_audit_entry(run_id, audit_dir)
        if audit_entry is None:
            missing_audit += 1

        valid.append(
            {
                "run_id": run_id,
                "timestamp": timestamp,
                "parsed_ts": ts,
                "instrument": instrument,
                "session": session,
                "analysts": raw.get("analysts") or [],
                "analysts_skipped": raw.get("analysts_skipped") or [],
                "analysts_failed": raw.get("analysts_failed") or [],
                "arbiter": raw.get("arbiter") if isinstance(raw.get("arbiter"), dict) else {},
                "audit": audit_entry,
            }
        )

    valid.sort(key=lambda r: r["parsed_ts"], reverse=True)
    return valid, inspected, skipped, missing_audit


def get_persona_performance(
    *,
    max_runs: int = 50,
    instrument: Optional[str] = None,
    session: Optional[str] = None,
    runs_dir: Optional[Path] = None,
    audit_dir: Optional[Path] = None,
) -> PersonaPerformanceResponse:
    scan_runs_dir = runs_dir or _RUNS_DIR
    scan_audit_dir = audit_dir or _AUDIT_DIR
    runs, inspected, skipped, missing_audit = _load_valid_runs(max_runs, scan_runs_dir, scan_audit_dir)

    if instrument:
        runs = [r for r in runs if r["instrument"] == instrument]
    if session:
        runs = [r for r in runs if r["session"] == session]

    bounds = ScanBounds(
        max_runs=max_runs,
        inspected_dirs=inspected,
        valid_runs=len(runs),
        skipped_runs=skipped,
    )

    if len(runs) < _THRESHOLD:
        return PersonaPerformanceResponse(
            version=_CONTRACT_VERSION,
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_state="stale" if (skipped > 0 or missing_audit > 0) else "live",
            source_of_truth="run_record.json+optional_audit",
            threshold_met=False,
            threshold=_THRESHOLD,
            scan_bounds=bounds,
            stats=[],
        )

    counters: dict[str, dict] = defaultdict(lambda: {
        "participation": 0,
        "skip": 0,
        "fail": 0,
        "override": 0,
        "align_n": 0,
        "align_d": 0,
        "conf": [],
        "override_known": False,
    })

    for run in runs:
        arbiter_verdict = (run["arbiter"].get("verdict") or "").upper()
        audit = run["audit"] if isinstance(run["audit"], dict) else None
        audit_outputs = audit.get("analyst_outputs", []) if audit else []
        final_verdict = audit.get("final_verdict", {}) if audit else {}
        risk_override = bool(final_verdict.get("risk_override_applied", False)) if audit else False
        decision = str(final_verdict.get("decision", "")).upper() if audit else ""

        for idx, analyst in enumerate(run["analysts"]):
            if not isinstance(analyst, dict):
                continue
            key = _persona_key(analyst)
            if not key:
                continue
            c = counters[key]
            c["participation"] += 1

            stance = None
            confidence = None
            if idx < len(audit_outputs) and isinstance(audit_outputs[idx], dict):
                ao = audit_outputs[idx]
                bias = ao.get("htf_bias")
                if isinstance(bias, str):
                    lb = bias.lower()
                    if lb == "ranging":
                        stance = "neutral"
                    elif lb in ("bullish", "bearish", "neutral"):
                        stance = lb
                cv = ao.get("confidence")
                if isinstance(cv, (int, float)):
                    confidence = float(cv)
                    c["conf"].append(confidence)

            if audit:
                c["override_known"] = True
                if risk_override and stance in ("bullish", "bearish") and decision == "NO_TRADE":
                    c["override"] += 1

            if stance in ("bullish", "bearish") and arbiter_verdict not in ("", "NO_TRADE"):
                c["align_d"] += 1
                if arbiter_verdict in _DIRECTIONAL_STANCE_TO_VERDICTS.get(stance, set()):
                    c["align_n"] += 1

        for analyst in run["analysts_skipped"]:
            if isinstance(analyst, dict):
                key = _persona_key(analyst)
                if key:
                    counters[key]["skip"] += 1

        for analyst in run["analysts_failed"]:
            if isinstance(analyst, dict):
                key = _persona_key(analyst)
                if key:
                    counters[key]["fail"] += 1

    stats: list[PersonaStats] = []
    for persona, c in counters.items():
        denom = c["participation"] + c["skip"] + c["fail"]
        participation_rate = (c["participation"] / denom) if denom > 0 else 0.0
        override_rate = None
        if c["participation"] > 0 and c["override_known"]:
            override_rate = c["override"] / c["participation"]
        stance_alignment = None
        if c["align_d"] > 0:
            stance_alignment = c["align_n"] / c["align_d"]
        avg_conf = None
        if c["conf"]:
            avg_conf = sum(c["conf"]) / len(c["conf"])

        flagged = bool((override_rate is not None and override_rate > 0.5))
        stats.append(PersonaStats(
            persona=persona,
            participation_count=c["participation"],
            skip_count=c["skip"],
            fail_count=c["fail"],
            participation_rate=participation_rate,
            override_count=c["override"],
            override_rate=override_rate,
            stance_alignment=stance_alignment,
            avg_confidence=avg_conf,
            flagged=flagged,
        ))

    stats.sort(key=lambda s: s.persona)
    return PersonaPerformanceResponse(
        version=_CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_state="stale" if (skipped > 0 or missing_audit > 0) else "live",
        source_of_truth="run_record.json+optional_audit",
        threshold_met=True,
        threshold=_THRESHOLD,
        scan_bounds=bounds,
        stats=stats,
    )


def get_pattern_summary(
    *,
    max_runs: int = 50,
    runs_dir: Optional[Path] = None,
    audit_dir: Optional[Path] = None,
) -> PatternSummaryResponse:
    scan_runs_dir = runs_dir or _RUNS_DIR
    scan_audit_dir = audit_dir or _AUDIT_DIR
    runs, inspected, skipped, missing_audit = _load_valid_runs(max_runs, scan_runs_dir, scan_audit_dir)

    bounds = ScanBounds(
        max_runs=max_runs,
        inspected_dirs=inspected,
        valid_runs=len(runs),
        skipped_runs=skipped,
    )

    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in runs:
        buckets[(r["instrument"], r["session"])].append(r)

    out: list[PatternBucket] = []
    for (instrument, session), items in sorted(buckets.items()):
        if len(items) < _THRESHOLD:
            out.append(PatternBucket(
                instrument=instrument,
                session=session,
                run_count=len(items),
                threshold_met=False,
                verdict_distribution=[],
                no_trade_rate=None,
                flagged=False,
            ))
            continue

        verdicts: dict[str, int] = defaultdict(int)
        for run in items:
            v = str(run["arbiter"].get("verdict") or "UNKNOWN").upper()
            verdicts[v] += 1

        no_trade = verdicts.get("NO_TRADE", 0)
        no_trade_rate = no_trade / len(items)
        flagged = no_trade_rate > 0.8

        out.append(PatternBucket(
            instrument=instrument,
            session=session,
            run_count=len(items),
            threshold_met=True,
            verdict_distribution=[
                VerdictCount(verdict=v, count=c)
                for v, c in sorted(verdicts.items())
            ],
            no_trade_rate=no_trade_rate,
            flagged=flagged,
        ))

    return PatternSummaryResponse(
        version=_CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_state="stale" if (skipped > 0 or missing_audit > 0) else "live",
        source_of_truth="run_record.json+optional_audit",
        threshold=_THRESHOLD,
        scan_bounds=bounds,
        buckets=out,
    )
