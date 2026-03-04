"""
Macro Risk Officer — CLI entry point.

Usage:
    python -m macro_risk_officer status [--instrument XAUUSD] [--json]
    python -m macro_risk_officer audit
    python -m macro_risk_officer kpi
    python -m macro_risk_officer update-outcomes [--dry-run]
    python -m macro_risk_officer feeder-run [--instrument XAUUSD]
    python -m macro_risk_officer feeder-ingest [--instrument XAUUSD] [FILE]
"""

from __future__ import annotations

import argparse
import sys

from macro_risk_officer.ingestion.scheduler import MacroScheduler


def cmd_status(instrument: str, as_json: bool) -> None:
    scheduler = MacroScheduler()
    context = scheduler.get_context(instrument=instrument)

    if context is None:
        print("ERROR: Could not fetch macro context. Check API keys and connectivity.")
        sys.exit(1)

    if as_json:
        print(context.model_dump_json(indent=2))
    else:
        print(context.arbiter_block())
        print(f"\nActive events: {', '.join(context.active_event_ids) or 'none'}")


def cmd_audit() -> None:
    from macro_risk_officer.history.tracker import OutcomeTracker
    tracker = OutcomeTracker()
    print(tracker.audit_report())


def cmd_kpi() -> None:
    """Print the Phase-4 release-gate KPI report from the persistent fetch log."""
    from macro_risk_officer.config.loader import load_thresholds
    from macro_risk_officer.history.metrics import KpiReport

    cfg = load_thresholds().get("scheduler", {})
    stale_threshold = cfg.get("stale_threshold_seconds", 3600)
    report = KpiReport.from_db(stale_threshold_seconds=stale_threshold)
    print(report.format())


def cmd_update_outcomes(dry_run: bool) -> None:
    """
    Backfill price outcomes for recorded runs that lack price data.

    Fetches T+0h / T+1h / T+24h / T+5d close prices from Yahoo Finance
    (via yfinance) and computes % changes + predicted direction accuracy.
    Run after any analysis session to keep the audit report current.
    """
    from macro_risk_officer.history.tracker import OutcomeTracker
    from macro_risk_officer.history.outcome_fetcher import OutcomeFetcher
    from macro_risk_officer.config.loader import load_weights

    tracker = OutcomeTracker()
    exposures: dict = load_weights().get("instrument_exposures", {})

    if dry_run:
        with __import__("sqlite3").connect(tracker.db_path) as conn:
            pending = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE price_at_record IS NULL"
            ).fetchone()[0]
        print(f"[DRY RUN] {pending} run(s) would be updated.")
        return

    fetcher = OutcomeFetcher(db_path=tracker.db_path, instrument_exposures=exposures)
    updated = fetcher.backfill()
    print(f"Updated price outcomes for {updated} run(s).")
    if updated > 0:
        print("Run `python -m macro_risk_officer audit` to see updated accuracy stats.")


def cmd_feeder_run(instrument: str) -> None:
    """
    Run the Modal feeder locally (no Modal SDK required) and print the
    versioned contract JSON to stdout.  Uses build_feeder_payload() directly.
    """
    import json
    import os

    from macro_risk_officer.modal_macro_worker import build_feeder_payload

    finnhub_key = os.environ.get("FINNHUB_API_KEY")
    fred_key = os.environ.get("FRED_API_KEY")
    payload = build_feeder_payload(
        finnhub_key=finnhub_key,
        fred_key=fred_key,
        instrument=instrument,
    )
    print(json.dumps(payload, indent=2))


def cmd_feeder_ingest(instrument: str, file_path: str | None) -> None:
    """
    Read a feeder contract JSON (from file or stdin) and produce a
    MacroContext through the local reasoning pipeline.
    """
    import json

    from macro_risk_officer.ingestion.feeder_ingest import ingest_feeder_payload

    if file_path and file_path != "-":
        with open(file_path) as fh:
            payload = json.load(fh)
    else:
        payload = json.load(sys.stdin)

    try:
        context = ingest_feeder_payload(payload, instrument=instrument)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    print(context.arbiter_block())
    print(f"\nActive events: {', '.join(context.active_event_ids) or 'none'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="macro_risk_officer",
        description="Macro Risk Officer — advisory-only macro context engine",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_p = subparsers.add_parser("status", help="Print current MacroContext")
    status_p.add_argument(
        "--instrument", default="XAUUSD", help="Instrument to compute conflict score for"
    )
    status_p.add_argument(
        "--json", action="store_true", dest="as_json", help="Output raw JSON"
    )

    subparsers.add_parser("audit", help="Print outcome tracking report")
    subparsers.add_parser(
        "kpi",
        help="Print Phase-4 release-gate KPI report (macro availability, freshness)",
    )

    update_p = subparsers.add_parser(
        "update-outcomes",
        help="Backfill price outcomes for recorded runs (requires yfinance)",
    )
    update_p.add_argument(
        "--dry-run", action="store_true", help="Show how many runs would be updated"
    )

    feeder_run_p = subparsers.add_parser(
        "feeder-run",
        help="Run the Modal feeder locally and print contract JSON",
    )
    feeder_run_p.add_argument(
        "--instrument", default="XAUUSD", help="Instrument context (default: XAUUSD)"
    )

    feeder_ingest_p = subparsers.add_parser(
        "feeder-ingest",
        help="Ingest feeder contract JSON and produce MacroContext",
    )
    feeder_ingest_p.add_argument(
        "--instrument", default="XAUUSD", help="Instrument for conflict score"
    )
    feeder_ingest_p.add_argument(
        "file", nargs="?", default=None,
        help="Path to feeder JSON file (default: read from stdin)",
    )

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args.instrument, args.as_json)
    elif args.command == "audit":
        cmd_audit()
    elif args.command == "kpi":
        cmd_kpi()
    elif args.command == "update-outcomes":
        cmd_update_outcomes(args.dry_run)
    elif args.command == "feeder-run":
        cmd_feeder_run(args.instrument)
    elif args.command == "feeder-ingest":
        cmd_feeder_ingest(args.instrument, args.file)


if __name__ == "__main__":
    main()
