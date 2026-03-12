"""Phase 3F CLI entry point: run multi-analyst consensus for a given instrument."""

from __future__ import annotations

import argparse
import json

from analyst.multi_analyst_service import run_multi_analyst


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 3F multi-analyst consensus")
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

    print(f"[multi-analyst] Running multi-analyst for {args.instrument}...")

    output = run_multi_analyst(args.instrument, proposed_direction=args.direction)

    ad = output.arbiter_decision
    print(f"[multi-analyst] Consensus state: {ad.consensus_state}")
    print(f"[multi-analyst] Final verdict: {ad.final_verdict} ({ad.final_confidence})")
    print(f"[multi-analyst] Directional bias: {ad.final_directional_bias}")
    print(f"[multi-analyst] No-trade enforced: {ad.no_trade_enforced}")

    for pv in output.persona_outputs:
        print(f"[multi-analyst] Persona {pv.persona_name}: {pv.verdict} ({pv.confidence})")

    if ad.no_trade_enforced:
        print(f"[multi-analyst] No-trade flags: {output.digest.no_trade_flags}")

    print(f"[multi-analyst] Output written to analyst/output/{args.instrument}_multi_analyst_output.json")
    print()
    print(json.dumps(output.to_dict(), indent=2))


if __name__ == "__main__":
    main()
