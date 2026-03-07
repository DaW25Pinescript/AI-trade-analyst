"""Phase 3F multi-analyst service: top-level run_multi_analyst orchestrator.

Wires together: Officer → pre-filter → two personas → Arbiter → output file.
Does not modify analyst/service.py or any 3E module.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "market_data_officer"))

from analyst.contracts import AnalystVerdict, StructureDigest
from analyst.multi_contracts import ArbiterDecision, MultiAnalystOutput
from analyst.pre_filter import compute_digest
from analyst.personas import run_all_personas, validate_persona_verdict
from analyst.arbiter import arbitrate, validate_arbiter_decision
from market_data_officer.officer.contracts import MarketPacketV2
from market_data_officer.officer.service import build_market_packet

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _arbiter_to_analyst_verdict(
    decision: ArbiterDecision,
    digest: StructureDigest,
) -> AnalystVerdict:
    """Re-express ArbiterDecision as AnalystVerdict for downstream compat (RULE 9)."""
    return AnalystVerdict(
        instrument=decision.instrument,
        as_of_utc=decision.as_of_utc,
        verdict=decision.final_verdict,
        confidence=decision.final_confidence,
        structure_gate=digest.structure_gate,
        htf_bias=digest.htf_bias,
        ltf_structure_alignment="unknown",
        active_fvg_context=digest.active_fvg_context,
        recent_sweep_signal=digest.recent_sweep_signal,
        structure_supports=list(digest.structure_supports),
        structure_conflicts=list(digest.structure_conflicts),
        no_trade_flags=list(digest.no_trade_flags),
        caution_flags=list(digest.caution_flags),
    )


def run_multi_analyst(
    instrument: str,
    proposed_direction: str | None = None,
    packet: MarketPacketV2 | None = None,
    structure_output_dir: Path | None = None,
    packages_dir: Path | None = None,
) -> MultiAnalystOutput:
    """Run the full multi-analyst pipeline for an instrument.

    Steps:
    1. Build MarketPacketV2 (or use provided)
    2. Compute StructureDigest via pre-filter
    3. Run both personas on the same digest
    4. Validate persona outputs
    5. Run Arbiter synthesis
    6. Build final_verdict as AnalystVerdict
    7. Write output atomically

    Returns:
        MultiAnalystOutput with all blocks populated.
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

    # Step 3: Run both personas
    persona_outputs = run_all_personas(digest)

    # Step 4: Validate persona outputs
    for pv in persona_outputs:
        validate_persona_verdict(pv, digest)

    # Step 5: Run Arbiter
    arbiter_decision = arbitrate(persona_outputs, digest)
    validate_arbiter_decision(arbiter_decision, digest)

    # Step 6: Build final_verdict as AnalystVerdict
    final_verdict = _arbiter_to_analyst_verdict(arbiter_decision, digest)

    # Step 7: Assemble output
    output = MultiAnalystOutput(
        instrument=instrument,
        as_of_utc=digest.as_of_utc,
        digest=digest,
        persona_outputs=persona_outputs,
        arbiter_decision=arbiter_decision,
        final_verdict=final_verdict,
    )

    # Step 8: Write atomically (RULE 10)
    _write_output(instrument, output)

    return output


def run_multi_analyst_with_digest(
    digest: StructureDigest,
    packet: MarketPacketV2 | None = None,
) -> MultiAnalystOutput:
    """Run the multi-analyst pipeline with a pre-computed digest.

    Useful for testing with synthetic digests.
    """
    # Run personas
    persona_outputs = run_all_personas(digest)
    for pv in persona_outputs:
        validate_persona_verdict(pv, digest)

    # Run Arbiter
    arbiter_decision = arbitrate(persona_outputs, digest)
    validate_arbiter_decision(arbiter_decision, digest)

    # Build final_verdict
    final_verdict = _arbiter_to_analyst_verdict(arbiter_decision, digest)

    output = MultiAnalystOutput(
        instrument=digest.instrument,
        as_of_utc=digest.as_of_utc,
        digest=digest,
        persona_outputs=persona_outputs,
        arbiter_decision=arbiter_decision,
        final_verdict=final_verdict,
    )

    _write_output(digest.instrument, output)
    return output


def _write_output(instrument: str, output: MultiAnalystOutput) -> Path:
    """Write MultiAnalystOutput to JSON atomically (RULE 10).

    Writes to a temp file first, then renames to avoid partial writes.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / f"{instrument}_multi_analyst_output.json"

    data = json.dumps(output.to_dict(), indent=2)

    # Atomic write: temp file + rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(OUTPUT_DIR),
        prefix=f".{instrument}_multi_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.replace(tmp_path, str(target))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return target
