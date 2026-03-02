"""
Macro Risk Officer — CLI entry point.

Usage:
    python -m macro_risk_officer status [--instrument XAUUSD] [--json]
    python -m macro_risk_officer audit
"""

from __future__ import annotations

import argparse
import json
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

    subparsers.add_parser("audit", help="Print outcome tracking report (MRO-P3 stub)")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args.instrument, args.as_json)
    elif args.command == "audit":
        cmd_audit()


if __name__ == "__main__":
    main()
