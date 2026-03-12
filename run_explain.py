"""Phase 3G CLI entry point: run_explain.py.

Usage:
    python run_explain.py --instrument EURUSD
    python run_explain.py --file analyst/output/EURUSD_multi_analyst_output.json

Re-derives explanation from saved MultiAnalystOutput without any model calls.
"""

from __future__ import annotations

import argparse
import json
import sys

from analyst.explain_service import run_explain, run_explain_from_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 3G: Re-derive explainability block from saved artifacts.",
    )
    parser.add_argument(
        "--instrument",
        type=str,
        help="Instrument name (e.g. EURUSD). Loads saved output from analyst/output/.",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to saved MultiAnalystOutput JSON file.",
    )

    args = parser.parse_args()

    if not args.instrument and not args.file:
        parser.error("Either --instrument or --file must be specified.")

    if args.file:
        block = run_explain_from_file(args.file)
    else:
        block = run_explain(args.instrument)

    print(json.dumps(block.to_dict(), indent=2))
    print(f"\nExplainability file written for {block.instrument}.", file=sys.stderr)


if __name__ == "__main__":
    main()
