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
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _emit_obs_event(event: str, **fields: Any) -> None:
    """Emit a structured JSON observability event (Obs P2)."""
    fields["event"] = event
    if "ts" not in fields:
        fields["ts"] = datetime.now(timezone.utc).isoformat()
    try:
        logger.info(json.dumps(fields, default=str))
    except Exception:
        pass


router = APIRouter()

# ── Triage debug flag ────────────────────────────────────────────────────────
_TRIAGE_DEBUG = os.getenv("TRIAGE_DEBUG", "").lower() == "true"


def _debug(msg: str, *args: object) -> None:
    """Emit a log line only when TRIAGE_DEBUG=true."""
    if _TRIAGE_DEBUG:
        logger.info(msg, *args)


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


def _current_session() -> str:
    """Return the active trading session based on current UTC hour."""
    hour = datetime.now(timezone.utc).hour
    if 0 <= hour < 7:
        return "Asia"
    if 7 <= hour < 12:
        return "London"
    if 12 <= hour < 21:
        return "NY"
    return "Asia"  # off-hours default — Sydney/Tokyo overlap


def _get_loopback_analyse_url() -> str:
    return os.getenv("AI_ANALYST_LOOPBACK_ANALYSE_URL", "http://127.0.0.1:8000/analyse")


def _build_loopback_auth_headers() -> dict[str, str]:
    """Build headers for backend loopback calls mirroring /analyse auth source."""
    api_key = os.getenv("AI_ANALYST_API_KEY", "").strip()
    if not api_key:
        return {}
    return {"X-API-Key": api_key}


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


def _build_triage_analyse_form_fields(
    symbol: str,
    session: str,
    *,
    smoke_mode: bool = False,
) -> list[tuple[str, tuple[None, str]]]:
    """Build deterministic multipart form fields for loopback /analyse calls."""
    form_fields: list[tuple[str, tuple[None, str]]] = [
        ("instrument", (None, symbol)),
        ("session", (None, session)),
        ("timeframes", (None, json.dumps(["H4", "H1", "M15"]))),
        ("account_balance", (None, "10000")),
        ("min_rr", (None, "2.0")),
        ("max_risk_per_trade", (None, "0.5")),
        ("max_daily_risk", (None, "1.5")),
        ("triage_mode", (None, "true")),
    ]
    if smoke_mode:
        form_fields.append(("smoke_mode", (None, "true")))
    return form_fields


async def run_real_triage_for_symbol(symbol: str) -> dict:
    """Call the /analyse endpoint for a single symbol and normalise the result."""
    session = _current_session()
    files = _build_triage_analyse_form_fields(symbol, session, smoke_mode=False)
    loopback_url = _get_loopback_analyse_url()
    headers = _build_loopback_auth_headers()
    payload_fields = [name for name, _ in files]
    _debug(
        "[triage] PRE-loopback  symbol=%s url=%s payload_fields=%s auth_header=%s",
        symbol,
        loopback_url,
        payload_fields,
        "X-API-Key" in headers,
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                loopback_url,
                files=files,
                headers=headers,
            )
            _debug(
                "[triage] POST-loopback symbol=%s url=%s status=%s body=%.500s",
                symbol, loopback_url, resp.status_code, resp.text,
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


@router.post("/triage/smoke")
async def triage_smoke():
    """
    Diagnostic endpoint — single-symbol (XAUUSD) probe through the triage→analyse chain.

    Returns JSON showing exactly how far execution got: loopback hop status,
    LLM env key presence, validate_input_node reached, and artifact written.
    Not wired to the frontend.
    """
    symbol = "XAUUSD"
    loopback_url = _get_loopback_analyse_url()
    headers = _build_loopback_auth_headers()
    ts_start = datetime.now(timezone.utc).isoformat()
    diag: dict[str, Any] = {
        "symbol": symbol,
        "started_at": ts_start,
        "loopback_url": loopback_url,
        "loopback_auth_configured": "X-API-Key" in headers,
        "loopback_hop_succeeded": False,
        "loopback_status_code": None,
        "loopback_response_truncated": None,
        "llm_env_key_present": False,
        "validate_input_node_reached": False,
        "llm_call_result": None,
        "artifact_written": False,
        "error": None,
    }

    # Check LLM env key presence (from llm_routing config, not a specific env var)
    try:
        from ...llm_router import router as llm_router
        route = llm_router.resolve("analyst_reasoning")
        _key = route.get("api_key") or ""
        diag["llm_env_key_present"] = bool(_key and len(str(_key)) > 0)
        diag["llm_base_url_configured"] = route.get("base_url")
        diag["llm_model_configured"] = route.get("model")
    except Exception as e:
        diag["llm_config_error"] = f"{type(e).__name__}: {str(e)[:300]}"

    # Perform the loopback call — deterministic payload, no auto-detection
    files = _build_triage_analyse_form_fields(symbol, "London", smoke_mode=True)

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(loopback_url, files=files, headers=headers)
            diag["loopback_status_code"] = resp.status_code
            diag["loopback_response_truncated"] = resp.text[:500]
            diag["loopback_hop_succeeded"] = 200 <= resp.status_code < 400

            if diag["loopback_hop_succeeded"]:
                result = resp.json()
                diag["llm_call_result"] = result.get("smoke_error") or "success"
                diag["run_id"] = result.get("run_id")
                diag["debug_analyst_counts"] = result.get("debug_analyst_counts")

                # Check if validate_input_node was reached (it always runs if we got 200)
                diag["validate_input_node_reached"] = True

                # Write minimal artifact
                output_dir = str(_ANALYST_OUTPUT)
                os.makedirs(output_dir, exist_ok=True)
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                filename = f"multi_analyst_output_{symbol}_{ts}.json"
                artifact_path = os.path.join(output_dir, filename)

                artifact = {
                    "symbol": symbol,
                    "triage_status": "smoke_test",
                    "bias": "neutral",
                    "confidence": "none",
                    "rationale_summary": "smoke test probe",
                    "why_interesting_tags": ["smoke_test"],
                    "no_trade_enforced": False,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "run_id": result.get("run_id"),
                    "smoke_result": result,
                }
                with open(artifact_path, "w") as f:
                    json.dump(artifact, f, indent=2)
                diag["artifact_written"] = True
                diag["artifact_path"] = artifact_path
    except Exception as e:
        diag["error"] = f"{type(e).__name__}: {str(e)[:500]}"

    diag["finished_at"] = datetime.now(timezone.utc).isoformat()
    return JSONResponse(content=diag)


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
    logger.info("[triage] POST /triage received — symbols=%s ts=%s",
                symbols, datetime.now(timezone.utc).isoformat())
    written = []
    failed = []
    symbol_outcomes: list[dict] = []
    batch_t0 = time.monotonic()

    for symbol in symbols:
        sym_t0 = time.monotonic()
        try:
            result = await run_real_triage_for_symbol(symbol)
            sym_dur = round((time.monotonic() - sym_t0) * 1000)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            filename = f"multi_analyst_output_{symbol}_{ts}.json"
            path = os.path.join(output_dir, filename)
            with open(path, "w") as f:
                json.dump(result, f, indent=2)
            written.append(symbol)
            symbol_outcomes.append({
                "symbol": symbol, "outcome": "success", "duration_ms": sym_dur,
            })
        except httpx.TimeoutException as e:
            sym_dur = round((time.monotonic() - sym_t0) * 1000)
            failed.append(symbol)
            logger.error("[triage] %s failed: %s", symbol, e)
            symbol_outcomes.append({
                "symbol": symbol, "outcome": "failed",
                "error_class": "triage_symbol_timeout",
                "error_type": type(e).__name__, "duration_ms": sym_dur,
            })
        except httpx.HTTPStatusError as e:
            sym_dur = round((time.monotonic() - sym_t0) * 1000)
            failed.append(symbol)
            logger.error("[triage] %s failed: %s", symbol, e)
            symbol_outcomes.append({
                "symbol": symbol, "outcome": "failed",
                "error_class": "triage_symbol_http_error",
                "error_type": type(e).__name__,
                "status_code": e.response.status_code, "duration_ms": sym_dur,
            })
        except Exception as e:
            sym_dur = round((time.monotonic() - sym_t0) * 1000)
            failed.append(symbol)
            logger.error("[triage] %s failed: %s", symbol, e)
            symbol_outcomes.append({
                "symbol": symbol, "outcome": "failed",
                "error_class": "triage_symbol_runtime_error",
                "error_type": type(e).__name__, "duration_ms": sym_dur,
            })

    # Obs P2: structured batch summary — Guardrail B: log event only, no response shape change
    batch_dur = round((time.monotonic() - batch_t0) * 1000)
    if not written:
        batch_status = "all_failed"
        top_cat = "runtime_execution_failure"
        evt_code = "triage_batch_all_failed"
    elif failed:
        batch_status = "partial_failure"
        top_cat = "runtime_execution_failure"
        evt_code = "triage_batch_partial_failure"
    else:
        batch_status = "success"
        top_cat = "runtime_execution_failure"
        evt_code = "triage_batch_success"

    _emit_obs_event(
        "triage.batch.summary",
        top_level_category=top_cat,
        event_code=evt_code,
        batch_status=batch_status,
        symbols_attempted=len(symbols),
        symbols_succeeded=len(written),
        symbols_failed=len(failed),
        succeeded=written,
        failed_symbols=failed,
        duration_ms=batch_dur,
        symbol_outcomes=symbol_outcomes,
    )

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

    return {
        "data_state": data_state,
        "instrument": asset,
        "multi_output": multi_output,
        "explainability": explain_block,
    }


@router.post("/journey/draft")
async def save_journey_draft(payload: dict):
    """Save journey draft payload to app/data/journeys/drafts/."""
    journey_id = payload.get("journey_id")
    if not journey_id:
        return {"success": False, "error": "Missing journey_id"}

    payload["updated_at"] = _now_iso()
    if "created_at" not in payload:
        payload["created_at"] = payload["updated_at"]

    path = _DRAFTS_DIR / f"{journey_id}.json"
    ok = _write_json(path, payload)
    if not ok:
        return {"success": False, "error": "Failed to save draft"}

    return {
        "success": True,
        "journey_id": journey_id,
        "saved_at": payload["updated_at"],
    }


@router.post("/journey/decision")
async def save_journey_decision(payload: dict):
    """Save final journey decision payload to app/data/journeys/decisions/."""
    journey_id = payload.get("journey_id")
    if not journey_id:
        return {"success": False, "error": "Missing journey_id"}

    payload["decided_at"] = payload.get("decided_at") or _now_iso()

    path = _DECISIONS_DIR / f"{journey_id}.json"
    ok = _write_json(path, payload)
    if not ok:
        return {"success": False, "error": "Failed to save decision"}

    return {
        "success": True,
        "journey_id": journey_id,
        "saved_at": payload["decided_at"],
    }


@router.post("/journey/result")
async def save_journey_result(payload: dict):
    """Save realised journey result payload to app/data/journeys/results/."""
    journey_id = payload.get("journey_id")
    if not journey_id:
        return {"success": False, "error": "Missing journey_id"}

    payload["logged_at"] = payload.get("logged_at") or _now_iso()

    path = _RESULTS_DIR / f"{journey_id}.json"
    ok = _write_json(path, payload)
    if not ok:
        return {"success": False, "error": "Failed to save result"}

    return {
        "success": True,
        "journey_id": journey_id,
        "saved_at": payload["logged_at"],
    }


@router.get("/journey/journal")
async def list_journal_entries():
    """List all draft journey entries sorted by updated_at descending."""
    if not _DRAFTS_DIR.exists():
        return []

    entries = []
    for path in _DRAFTS_DIR.glob("*.json"):
        data = _load_json(path)
        if data:
            entries.append(data)

    entries.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return entries


@router.get("/journey/review")
async def list_review_entries():
    """List all realised journey result entries sorted by logged_at descending."""
    if not _RESULTS_DIR.exists():
        return []

    entries = []
    for path in _RESULTS_DIR.glob("*.json"):
        data = _load_json(path)
        if data:
            entries.append(data)

    entries.sort(key=lambda x: x.get("logged_at", ""), reverse=True)
    return entries
