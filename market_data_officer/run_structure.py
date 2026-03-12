"""Structure Engine CLI entry point for Phase 3A.

Usage:
    python run_structure.py --instrument EURUSD --timeframes 15m 1h 4h
    python run_structure.py --instrument XAUUSD --timeframes 15m 1h 4h
    python run_structure.py --help
"""

import argparse
from pathlib import Path

from market_data_officer.structure.config import StructureConfig
from market_data_officer.structure.engine import run_engine


def main() -> None:
    """Run the Phase 3A Structure Engine from the command line."""
    parser = argparse.ArgumentParser(
        description="Phase 3A Structure Engine — compute ICT structural state from OHLCV bars",
    )
    parser.add_argument(
        "--instrument",
        type=str,
        required=True,
        help="Instrument symbol (e.g. EURUSD, XAUUSD)",
    )
    parser.add_argument(
        "--timeframes",
        nargs="+",
        default=["15m", "1h", "4h"],
        help="Timeframes to compute (default: 15m 1h 4h)",
    )
    parser.add_argument(
        "--pivot-left",
        type=int,
        default=3,
        help="Pivot left bars for swing confirmation (default: 3)",
    )
    parser.add_argument(
        "--pivot-right",
        type=int,
        default=3,
        help="Pivot right bars for swing confirmation (default: 3)",
    )
    parser.add_argument(
        "--packages-dir",
        type=str,
        default=None,
        help="Custom hot packages directory (default: market_data/packages/latest)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom output directory (default: market_data_officer/structure/output)",
    )

    args = parser.parse_args()

    config = StructureConfig(
        pivot_left_bars=args.pivot_left,
        pivot_right_bars=args.pivot_right,
        timeframes=args.timeframes,
    )

    print(f"Phase 3A Structure Engine")
    print(f"  Instrument: {args.instrument}")
    print(f"  Timeframes: {', '.join(args.timeframes)}")
    print(f"  Pivot: {config.pivot_left_bars}L / {config.pivot_right_bars}R")
    print()

    packages_dir = Path(args.packages_dir) if args.packages_dir else None
    output_dir = Path(args.output_dir) if args.output_dir else None

    results = run_engine(
        instruments=[args.instrument],
        config=config,
        packages_dir=packages_dir,
        output_dir=output_dir,
    )

    print()
    print(f"Done. {len(results)} packet(s) written.")


if __name__ == "__main__":
    main()
