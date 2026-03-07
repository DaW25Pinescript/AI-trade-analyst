"""Officer-facing structure read API.

Provides a clean interface for the Officer to load structure engine outputs.
The Officer calls this module — it never reads structure JSON files directly
or imports from the structure engine.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

STRUCTURE_OUTPUT_DIR = Path("market_data_officer/structure/output")
STRUCTURE_STALENESS_MINUTES = 120


def load_structure_packet(
    instrument: str,
    timeframe: str,
    output_dir: Path = STRUCTURE_OUTPUT_DIR,
) -> dict | None:
    """Load the latest structure packet JSON for an instrument/timeframe.

    Returns None if file does not exist or cannot be parsed.
    Never raises on missing files.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        timeframe: Timeframe label, e.g. '1h'.
        output_dir: Directory containing structure output JSON files.

    Returns:
        Parsed structure packet dict, or None if unavailable.
    """
    path = output_dir / f"{instrument.lower()}_{timeframe}_structure.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_structure_summary(
    instrument: str,
    timeframes: tuple[str, ...] = ("15m", "1h", "4h"),
    output_dir: Path = STRUCTURE_OUTPUT_DIR,
) -> dict[str, dict]:
    """Load and merge structure packets across timeframes into a summary dict.

    Missing timeframes are skipped — not an error.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        timeframes: Timeframes to load.
        output_dir: Directory containing structure output JSON files.

    Returns:
        Dict mapping timeframe label to parsed packet dict.
    """
    result = {}
    for tf in timeframes:
        packet = load_structure_packet(instrument, tf, output_dir=output_dir)
        if packet is not None:
            result[tf] = packet
    return result


def structure_is_available(
    instrument: str,
    timeframes: tuple[str, ...] = ("15m", "1h", "4h"),
    output_dir: Path = STRUCTURE_OUTPUT_DIR,
) -> bool:
    """Returns True if at least one valid, non-stale structure packet exists.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        timeframes: Timeframes to check.
        output_dir: Directory containing structure output JSON files.

    Returns:
        True if at least one fresh structure packet is available.
    """
    for tf in timeframes:
        packet = load_structure_packet(instrument, tf, output_dir=output_dir)
        if packet and _is_fresh(packet):
            return True
    return False


def _is_fresh(packet: dict) -> bool:
    """Returns True if packet as_of is within staleness threshold.

    Args:
        packet: Parsed structure packet dict.

    Returns:
        True if packet is fresh (not stale).
    """
    try:
        as_of_raw = packet.get("as_of", "")
        if isinstance(as_of_raw, str):
            as_of = datetime.fromisoformat(as_of_raw.replace("Z", "+00:00"))
        else:
            return False
        age_minutes = (datetime.now(timezone.utc) - as_of).total_seconds() / 60
        return age_minutes <= STRUCTURE_STALENESS_MINUTES
    except Exception:
        return False
