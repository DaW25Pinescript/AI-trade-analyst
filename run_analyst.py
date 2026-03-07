"""Phase 3E CLI entry point: run analyst for a given instrument."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent / "market_data_officer"))

from analyst.service import run_analyst


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 3E analyst")
    parser.add_argument(
        "--instrument",
        required=True,
        help="Instrument symbol (e.g. EURUSD, XAUUSD)",
    )
    parser.add_argument(
        "--direction",
        choices=["long", "short"],
        default=None,
        help="Optional proposed trade direction for gate check",
    )
    args = parser.parse_args()

    print(f"[analyst] Running analyst for {args.instrument}...")

    output = run_analyst(args.instrument, proposed_direction=args.direction)

    print(f"[analyst] Verdict: {output.verdict.verdict} ({output.verdict.confidence})")
    print(f"[analyst] Structure gate: {output.verdict.structure_gate}")
    print(f"[analyst] HTF bias: {output.verdict.htf_bias}")

    if output.verdict.no_trade_flags:
        print(f"[analyst] No-trade flags: {output.verdict.no_trade_flags}")
    if output.verdict.caution_flags:
        print(f"[analyst] Caution flags: {output.verdict.caution_flags}")

    print(f"[analyst] Output written to analyst/output/{args.instrument}_analyst_output.json")
    print()
    print(json.dumps(output.to_dict(), indent=2))


if __name__ == "__main__":
    main()
