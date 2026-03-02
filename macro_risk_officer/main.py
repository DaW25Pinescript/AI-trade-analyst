"""
Macro Risk Officer — CLI entry point.

Usage:
    python -m macro_risk_officer status [--instrument XAUUSD] [--json]
    python -m macro_risk_officer audit
    python -m macro_risk_officer update-outcomes [--dry-run]
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

    update_p = subparsers.add_parser(
        "update-outcomes",
        help="Backfill price outcomes for recorded runs (requires yfinance)",
    )
    update_p.add_argument(
        "--dry-run", action="store_true", help="Show how many runs would be updated"
    )

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args.instrument, args.as_json)
    elif args.command == "audit":
        cmd_audit()
    elif args.command == "update-outcomes":
        cmd_update_outcomes(args.dry_run)


if __name__ == "__main__":
    main()
