"""
Journey router — Trade Ideation Journey V1.1

Endpoints for triage, bootstrap, draft/decision/result persistence,
journal listing, and review listing.

All reads come from analyst/output/ JSON files.
All writes go to app/data/journeys/{drafts,decisions,results}/.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Path configuration ────────────────────────────────────────────────────────

# Project root is 3 levels up from this file:
#   ai_analyst/api/routers/journey.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ANALYST_OUTPUT = _PROJECT_ROOT / "analyst" / "output"
_JOURNEYS_ROOT = _PROJECT_ROOT / "app" / "data" / "journeys"
_DRAFTS_DIR = _JOURNEYS_ROOT / "drafts"
_DECISIONS_DIR = _JOURNEYS_ROOT / "decisions"
_RESULTS_DIR = _JOURNEYS_ROOT / "results"

# Staleness threshold: 24 hours
_STALE_SECONDS = 24 * 60 * 60


def _is_stale(generated_at: str | None) -> bool:
    """Check if a timestamp is older than the staleness threshold."""
    if not generated_at:
        return False
    try:
        ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return age > _STALE_SECONDS
    except (ValueError, TypeError):
        return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict | None:
    """Load a JSON file, returning None if it doesn't exist or is invalid."""
    try:
        if not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load %s: %s", path, e)
        return None


def _write_json(path: Path, data: dict) -> bool:
    """Write a dict to a JSON file, creating parent directories as needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except OSError as e:
        logger.error("Failed to write %s: %s", path, e)
        return False


# ── GET /watchlist/triage ─────────────────────────────────────────────────────


@router.get("/watchlist/triage")
async def watchlist_triage():
    """Read triage items from analyst/output/ multi_analyst_output files."""
    if not _ANALYST_OUTPUT.exists():
        return {"data_state": "unavailable", "generated_at": None, "items": []}

    all_files = sorted(_ANALYST_OUTPUT.glob("multi_analyst_output_*.json"), reverse=True)
    if not all_files:
        return {"data_state": "unavailable", "generated_at": None, "items": []}

    # Deduplicate: keep only the latest file per symbol.
    # Filename format: multi_analyst_output_{SYMBOL}_{TIMESTAMP}Z.json
    # Reverse-sorted so the latest timestamp comes first per symbol.
    seen_symbols: set[str] = set()
    output_files: list[Path] = []
    for fpath in all_files:
        # Extract symbol: strip prefix and suffix, then drop the trailing timestamp
        stem = fpath.stem  # e.g. "multi_analyst_output_NAS100_20260308T001045Z"
        after_prefix = stem[len("multi_analyst_output_"):]  # "NAS100_20260308T001045Z"
        # Timestamp is always the last _-separated segment (e.g. "20260308T001045Z")
        parts = after_prefix.rsplit("_", 1)
        sym = parts[0] if len(parts) == 2 else after_prefix
        if sym not in seen_symbols:
            seen_symbols.add(sym)
            output_files.append(fpath)

    items = []
    latest_ts = None

    for fpath in output_files:
        raw = _load_json(fpath)
        if raw is None:
            continue

        arbiter = raw.get("arbiter_decision") or {}
        digest = raw.get("digest") or {}
        generated_at = raw.get("as_of_utc") or raw.get("generated_at")

        if generated_at and (latest_ts is None or generated_at > latest_ts):
            latest_ts = generated_at

        # Derive triage_status — prefer flat key, fall back to arbiter derivation
        triage_status = raw.get("triage_status")
        if not triage_status:
            triage_status = "no_data"
            if arbiter.get("no_trade_enforced") or raw.get("no_trade_enforced"):
                triage_status = "blocked"
            else:
                v = arbiter.get("final_verdict", "")
                c = arbiter.get("final_confidence", "")
                if v in ("long_bias", "short_bias") and c in ("high", "moderate"):
                    triage_status = "active"
                elif v == "conditional":
                    triage_status = "watch"
                elif v in ("no_trade", "no_data"):
                    triage_status = "blocked"
                else:
                    triage_status = "watch"

        # Derive bias — prefer flat key, fall back to arbiter
        bias = raw.get("bias") or arbiter.get("final_directional_bias", "no_data")
        if bias == "none":
            bias = "neutral"

        # Derive confidence — prefer flat key, fall back to arbiter
        confidence = raw.get("confidence") or arbiter.get("final_confidence", "none")

        # Derive why_interesting — prefer flat key, fall back to digest
        why_interesting = raw.get("why_interesting_tags")
        if why_interesting is None:
            why_interesting = []
            supports = digest.get("structure_supports") or []
            why_interesting.extend(supports[:3])
            caution = digest.get("caution_flags") or []
            why_interesting.extend([f"caution: {f}" for f in caution[:2]])

        # Symbol — prefer flat key, fall back to instrument
        symbol = raw.get("symbol") or raw.get("instrument", "UNKNOWN")

        # Rationale — prefer flat key, fall back to arbiter
        rationale = raw.get("rationale_summary") or arbiter.get("winning_rationale_summary")

        items.append({
            "symbol": symbol,
            "triage_status": triage_status,
            "bias": bias,
            "confidence": confidence,
            "why_interesting": why_interesting,
            "rationale": rationale,
            "verdict_at": generated_at,
        })

    data_state = "live"
    if _is_stale(latest_ts):
        data_state = "stale"

    return {
        "data_state": data_state,
        "generated_at": latest_ts,
        "items": items,
    }


# ── POST /triage ─────────────────────────────────────────────────────────────


def _current_session() -> str:
    """Return the active trading session based on current UTC hour."""
    hour = datetime.now(timezone.utc).hour
    if 0 <= hour < 7:
        return "Asia"
    if 7 <= hour < 12:
        return "London"
    if 12 <= hour < 21:
        return "NY"
    return "Off"


async def run_real_triage_for_symbol(symbol: str) -> dict:
    """Call the /analyse endpoint for a single symbol and normalise the result."""
    session = _current_session()
    files = [
        ("instrument", (None, symbol)),
        ("session", (None, session)),
        ("timeframes", (None, '["H4","H1","M15"]')),
        ("account_balance", (None, "10000")),
        ("min_rr", (None, "2.0")),
        ("max_risk_per_trade", (None, "0.5")),
        ("triage_mode", (None, "true")),
    ]
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "http://127.0.0.1:8000/analyse",
                files=files,
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(
            "Triage /analyse call failed for %s: %s %s",
            symbol, e.response.status_code, e.response.text,
        )
        raise

    verdict = result.get("verdict", {})
    decision = verdict.get("decision", "WAIT_FOR_CONFIRMATION")
    confidence_raw = verdict.get("overall_confidence", 0.5)

    return {
        "symbol": symbol,
        "bias": verdict.get("final_bias", "neutral"),
        "triage_status": (
            "no_trade" if decision == "NO_TRADE"
            else "conditional" if decision == "WAIT_FOR_CONFIRMATION"
            else "watch"
        ),
        "confidence": (
            "high" if confidence_raw >= 0.7
            else "moderate" if confidence_raw >= 0.4
            else "low"
        ),
        "rationale_summary": verdict.get("arbiter_notes") or (
            verdict.get("no_trade_conditions", [""])[0] if decision == "NO_TRADE" else ""
        ),
        "why_interesting_tags": [decision] + verdict.get("no_trade_conditions", [])[:2],
        "no_trade_enforced": decision == "NO_TRADE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": result.get("run_id"),
    }


@router.post("/triage")
async def run_triage(request: Request):
    """
    POST /triage — Trigger triage artifact production.

    Calls the /analyse endpoint for each symbol and writes the normalised
    result as a multi_analyst_output JSON file.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    output_dir = str(_ANALYST_OUTPUT)
    os.makedirs(output_dir, exist_ok=True)

    symbols = body.get("symbols") or ["XAUUSD", "NAS100", "US30"]
    written = []
    failed = []

    for symbol in symbols:
        try:
            result = await run_real_triage_for_symbol(symbol)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            filename = f"multi_analyst_output_{symbol}_{ts}.json"
            path = os.path.join(output_dir, filename)
            with open(path, "w") as f:
                json.dump(result, f, indent=2)
            written.append(symbol)
        except Exception as e:
            failed.append(symbol)
            logger.error("[triage] %s failed: %s", symbol, e)

    if not written:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail={
            "message": "All symbols failed to produce artifacts",
            "partial": failed,
        })

    return {
        "status": "complete",
        "artifacts_written": len(written),
        "symbols_processed": written,
        "output_dir": output_dir,
    }


# ── GET /journey/{asset}/bootstrap ────────────────────────────────────────────


@router.get("/journey/{asset}/bootstrap")
async def journey_bootstrap(asset: str):
    """Read bootstrap payload for a journey entry screen."""
    output_path = _ANALYST_OUTPUT / f"{asset}_multi_analyst_output.json"
    explain_path = _ANALYST_OUTPUT / f"{asset}_multi_analyst_explainability.json"

    multi_output = _load_json(output_path)
    if multi_output is None:
        return {"data_state": "unavailable", "instrument": asset}

    explain_block = _load_json(explain_path)

    # Determine data_state
    generated_at = multi_output.get("as_of_utc")
    if explain_block is None:
        data_state = "partial"
    elif _is_stale(generated_at):
        data_state = "stale"
    else:
        data_state = "live"

    arbiter = multi_output.get("arbiter_decision") or {}
    digest = multi_output.get("digest") or {}

    response = {
        "data_state": data_state,
        "instrument": asset,
        "generated_at": generated_at,
        "structure_digest": digest,
        "analyst_verdict": {
            "verdict": arbiter.get("final_verdict", "no_data"),
            "confidence": arbiter.get("final_confidence", "none"),
        },
        "arbiter_decision": arbiter,
        "explanation": explain_block if explain_block else {},
        "reasoning_summary": arbiter.get("winning_rationale_summary"),
    }

    return response


# ── POST /journey/draft ───────────────────────────────────────────────────────


@router.post("/journey/draft")
async def save_draft(request: Request):
    """Save a journey draft to disk."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Invalid JSON body"},
        )

    journey_id = body.get("journey_id") or f"j_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{id(body) % 10000:04d}"
    filename = f"journey_{journey_id}.json"
    filepath = _DRAFTS_DIR / filename

    payload = {**body, "journey_id": journey_id, "saved_at": _now_iso()}

    if not _write_json(filepath, payload):
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to write draft to disk"},
        )

    return {
        "success": True,
        "journey_id": journey_id,
        "saved_at": payload["saved_at"],
        "path": str(filepath.relative_to(_PROJECT_ROOT)),
    }


# ── POST /journey/decision ───────────────────────────────────────────────────


@router.post("/journey/decision")
async def save_decision(request: Request):
    """Save a frozen decision snapshot to disk. Immutable — rejects duplicate IDs."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Invalid JSON body"},
        )

    snapshot_id = body.get("snapshot_id")
    if not snapshot_id:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Missing snapshot_id"},
        )

    filename = f"decision_{snapshot_id}.json"
    filepath = _DECISIONS_DIR / filename

    # Immutability check
    if filepath.exists():
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": f"Decision snapshot '{snapshot_id}' already exists. Snapshots are immutable.",
            },
        )

    payload = {**body, "saved_at": _now_iso()}

    if not _write_json(filepath, payload):
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to write decision to disk"},
        )

    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "saved_at": payload["saved_at"],
        "path": str(filepath.relative_to(_PROJECT_ROOT)),
    }


# ── POST /journey/result ─────────────────────────────────────────────────────


@router.post("/journey/result")
async def save_result(request: Request):
    """Save a result snapshot to disk."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Invalid JSON body"},
        )

    snapshot_id = body.get("snapshot_id")
    if not snapshot_id:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Missing snapshot_id"},
        )

    filename = f"result_{snapshot_id}.json"
    filepath = _RESULTS_DIR / filename

    payload = {**body, "saved_at": _now_iso()}

    if not _write_json(filepath, payload):
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to write result to disk"},
        )

    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "saved_at": payload["saved_at"],
        "path": str(filepath.relative_to(_PROJECT_ROOT)),
    }


# ── GET /journal/decisions ───────────────────────────────────────────────────


@router.get("/journal/decisions")
async def journal_decisions():
    """List saved decision snapshots (summary only)."""
    if not _DECISIONS_DIR.exists():
        return {"records": []}

    records = []
    for fpath in sorted(_DECISIONS_DIR.glob("decision_*.json")):
        raw = _load_json(fpath)
        if raw is None:
            continue
        records.append({
            "snapshot_id": raw.get("snapshot_id", ""),
            "instrument": raw.get("instrument", ""),
            "saved_at": raw.get("saved_at", ""),
            "journey_status": raw.get("journey_status", ""),
            "verdict": raw.get("system_verdict", {}).get("verdict", "") if isinstance(raw.get("system_verdict"), dict) else "",
            "user_decision": raw.get("user_decision", {}).get("action", "") if isinstance(raw.get("user_decision"), dict) else None,
        })

    return {"records": records}


# ── GET /review/records ──────────────────────────────────────────────────────


@router.get("/review/records")
async def review_records():
    """List saved decision + result records for review surface."""
    if not _DECISIONS_DIR.exists():
        return {"records": []}

    # Build set of result snapshot IDs
    result_ids: set[str] = set()
    if _RESULTS_DIR.exists():
        for fpath in _RESULTS_DIR.glob("result_*.json"):
            raw = _load_json(fpath)
            if raw and raw.get("snapshot_id"):
                result_ids.add(raw["snapshot_id"])

    records = []
    for fpath in sorted(_DECISIONS_DIR.glob("decision_*.json")):
        raw = _load_json(fpath)
        if raw is None:
            continue
        sid = raw.get("snapshot_id", "")
        records.append({
            "snapshot_id": sid,
            "instrument": raw.get("instrument", ""),
            "saved_at": raw.get("saved_at", ""),
            "journey_status": raw.get("journey_status", ""),
            "verdict": raw.get("system_verdict", {}).get("verdict", "") if isinstance(raw.get("system_verdict"), dict) else "",
            "user_decision": raw.get("user_decision", {}).get("action", "") if isinstance(raw.get("user_decision"), dict) else None,
            "has_result": sid in result_ids,
        })

    return {"records": records}
