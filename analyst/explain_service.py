"""Phase 3G orchestrator: run_explain(instrument) or run_explain_from_file(path).

Zero LLM calls. Loads saved MultiAnalystOutput, derives ExplainabilityBlock,
writes standalone file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from analyst.explainability import build_explanation, build_explanation_from_dict
from analyst.explain_contracts import ExplainabilityBlock
from analyst.multi_contracts import MultiAnalystOutput

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def run_explain(instrument: str) -> ExplainabilityBlock:
    """Re-derive explanation from saved multi_analyst_output.json.

    Loads the saved output file for the instrument, builds the
    ExplainabilityBlock, and writes the standalone explainability file.
    No LLM calls, no network access, no re-running models.
    """
    input_path = OUTPUT_DIR / f"{instrument}_multi_analyst_output.json"
    if not input_path.exists():
        raise FileNotFoundError(
            f"No saved output for {instrument}: {input_path}"
        )
    return run_explain_from_file(str(input_path))


def run_explain_from_file(path: str) -> ExplainabilityBlock:
    """Re-derive explanation from a saved MultiAnalystOutput JSON file.

    Steps:
    1. Load the JSON file
    2. Re-derive ExplainabilityBlock from the in-memory dict
    3. Write standalone file

    No network, no LLM, no filesystem access beyond input file + output.
    """
    with open(path) as f:
        saved_dict = json.load(f)

    block = build_explanation_from_dict(saved_dict)

    # Write standalone explainability file
    instrument = block.instrument
    _write_explainability_file(instrument, block)

    return block


def attach_explanation(output: MultiAnalystOutput) -> MultiAnalystOutput:
    """Build explanation and attach it to the MultiAnalystOutput.

    Also writes the standalone explainability file.
    Returns the same output object with explanation populated.
    """
    block = build_explanation(output)
    output.explanation = block
    _write_explainability_file(output.instrument, block)
    return output


def _write_explainability_file(
    instrument: str,
    block: ExplainabilityBlock,
) -> Path:
    """Write standalone explainability JSON file atomically."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / f"{instrument}_multi_analyst_explainability.json"

    data = json.dumps(block.to_dict(), indent=2)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(OUTPUT_DIR),
        prefix=f".{instrument}_explain_",
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
