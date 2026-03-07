"""CLI entry point for the Market Data Officer.

Usage:
    python run_officer.py --instrument EURUSD
    python run_officer.py --instrument EURUSD --output-path state/packets/
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from officer.service import build_market_packet, write_packet


def main() -> None:
    """Run the Market Data Officer to build and write a market packet."""
    parser = argparse.ArgumentParser(
        description="Market Data Officer — build structured market packets from validated feed data."
    )
    parser.add_argument(
        "--instrument",
        required=True,
        help="Instrument symbol, e.g. EURUSD",
    )
    parser.add_argument(
        "--output-path",
        default="state/packets/",
        help="Output directory for packet JSON (default: state/packets/)",
    )
    args = parser.parse_args()

    instrument = args.instrument.upper()
    output_dir = Path(args.output_path)

    print(f"[officer] Building market packet v2 for {instrument}...")

    packet = build_market_packet(instrument)

    # Write packet to file
    output_path = write_packet(packet, output_dir)
    print(f"[officer] Packet written to: {output_path}")

    # Print summary
    print(f"\nMarket packet v2 built: {instrument}")
    print(f"  schema_version: market_packet_v2")
    print(f"  as_of_utc: {packet.as_of_utc}")
    print(f"  data_quality: {packet.state_summary.data_quality}")
    print(f"  stale: {packet.quality.stale}")
    print(f"  partial: {packet.quality.partial}")
    print(f"  flags: {packet.quality.flags}")
    print(f"  trusted: {packet.is_trusted()}")
    print(f"  structure_available: {packet.structure.available}")
    print(f"  has_structure: {packet.has_structure()}")


if __name__ == "__main__":
    main()
