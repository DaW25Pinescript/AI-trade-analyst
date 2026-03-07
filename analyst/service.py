"""Phase 3E analyst service: top-level run_analyst orchestrator.

Wires together: Officer → pre-filter → LLM analyst → output file.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "market_data_officer"))

from analyst.contracts import AnalystOutput, AnalystVerdict, ReasoningBlock, StructureDigest
from analyst.pre_filter import compute_digest
from analyst.analyst import run_analyst_llm
from market_data_officer.officer.contracts import MarketPacketV2
from market_data_officer.officer.service import build_market_packet

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def run_analyst(
    instrument: str,
    proposed_direction: str | None = None,
    packet: MarketPacketV2 | None = None,
    structure_output_dir: Path | None = None,
    packages_dir: Path | None = None,
) -> AnalystOutput:
    """Run the full analyst pipeline for an instrument.

    Steps:
    1. Build MarketPacketV2 (or use provided)
    2. Compute StructureDigest via pre-filter
    3. Run LLM analyst
    4. Write output atomically

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        proposed_direction: Optional "long" or "short" for gate check.
        packet: Optional pre-built MarketPacketV2.
        structure_output_dir: Optional custom structure output dir.
        packages_dir: Optional custom packages dir.

    Returns:
        AnalystOutput with verdict, reasoning, and digest.
    """
    # Step 1: Build packet if not provided
    if packet is None:
        kwargs = {}
        if structure_output_dir is not None:
            kwargs["structure_output_dir"] = structure_output_dir
        if packages_dir is not None:
            kwargs["packages_dir"] = packages_dir
        packet = build_market_packet(instrument, **kwargs)

    # Step 2: Compute digest
    digest = compute_digest(packet, proposed_direction=proposed_direction)

    # Step 3: Run LLM analyst
    verdict, reasoning = run_analyst_llm(digest, packet)

    # Step 4: Assemble output
    output = AnalystOutput(verdict=verdict, reasoning=reasoning, digest=digest)

    # Step 5: Write atomically
    _write_output(instrument, output)

    return output


def run_analyst_with_digest(
    digest: StructureDigest,
    packet: MarketPacketV2 | None = None,
) -> AnalystOutput:
    """Run the LLM analyst with a pre-computed digest.

    Useful for testing with synthetic digests.
    """
    if packet is None:
        # Build a minimal packet for the prompt builder
        packet = build_market_packet(digest.instrument)

    verdict, reasoning = run_analyst_llm(digest, packet)
    output = AnalystOutput(verdict=verdict, reasoning=reasoning, digest=digest)
    _write_output(digest.instrument, output)
    return output


def run_analyst_with_packet(
    packet: MarketPacketV2,
    proposed_direction: str | None = None,
) -> AnalystOutput:
    """Run the full analyst pipeline with a pre-built packet."""
    return run_analyst(
        packet.instrument,
        proposed_direction=proposed_direction,
        packet=packet,
    )


def _write_output(instrument: str, output: AnalystOutput) -> Path:
    """Write AnalystOutput to JSON atomically.

    Writes to a temp file first, then renames to avoid partial writes.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / f"{instrument}_analyst_output.json"

    data = json.dumps(output.to_dict(), indent=2)

    # Atomic write: temp file + rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(OUTPUT_DIR),
        prefix=f".{instrument}_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.replace(tmp_path, str(target))
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return target
