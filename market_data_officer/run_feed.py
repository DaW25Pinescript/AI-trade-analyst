"""CLI entry point for the market data feed pipeline."""

import argparse
import sys
from datetime import datetime, timezone


def main() -> None:
    """Run the market data feed pipeline from the command line."""
    parser = argparse.ArgumentParser(
        description="Market Data Officer Feed — ingestion spine (EURUSD, XAUUSD)",
    )
    parser.add_argument(
        "--instrument",
        type=str,
        required=True,
        help="Instrument symbol (e.g. EURUSD)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="End date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--save-raw",
        action="store_true",
        default=False,
        help="Cache raw bi5 files to disk",
    )

    args = parser.parse_args()

    try:
        start = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end = datetime.strptime(args.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        print(f"Error parsing dates: {exc}")
        sys.exit(1)

    if end < start:
        print("Error: end-date must be >= start-date")
        sys.exit(1)

    # Import here to avoid import errors when just running --help
    from feed.pipeline import run_pipeline

    run_pipeline(
        symbol=args.instrument,
        start_date=start,
        end_date=end,
        save_raw=args.save_raw,
    )


if __name__ == "__main__":
    main()
