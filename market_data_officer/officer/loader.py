"""Package loader — reads OHLCV data from PriceStore (default) or hot package CSVs (fallback).

Primary path: PriceStore via PriceStoreAdapter (trading-data-pipeline).
Fallback path: CSV hot packages from market_data/packages/latest/.

Fallback activates only on infrastructure unavailability (TDP not installed,
not configured, or data dir missing) — NOT on empty data from PriceStore.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from market_data_officer.instrument_registry import INSTRUMENT_REGISTRY

logger = logging.getLogger(__name__)

# Default hot package directory (matches feed config)
PACKAGES_DIR = Path("market_data/packages/latest")

# Legacy global constant — retained for backward compatibility but no longer
# used in the primary path. Use get_expected_timeframes() instead.
EXPECTED_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]


def get_expected_timeframes(instrument: str) -> list[str]:
    """Return expected timeframes for an instrument from the registry.

    FX instruments: ["5m", "15m", "1h", "4h", "1d"]
    Metals: ["15m", "1h", "4h", "1d"]

    Note: 1m removed per MDO 1m Dependency Audit (Verdict C).

    This function is the single source of truth for expected timeframes.
    The global EXPECTED_TIMEFRAMES constant is retained for backward
    compatibility but is no longer used in the primary path.
    """
    meta = INSTRUMENT_REGISTRY.get(instrument)
    if meta and meta.timeframes:
        return [tf for tf in meta.timeframes if tf != "1m"]
    return ["5m", "15m", "1h", "4h", "1d"]


def _get_pricestore_adapter():
    """Get PriceStoreAdapter instance. Returns None if TDP unavailable.

    Wiring: uses TDP_SRC_DIR for sys.path import, TDP_DATA_DIR for
    PipelineConfig construction. Does NOT call TDP's load_config() to
    avoid DATA_DIR env var collision (D-25).
    """
    try:
        from pipeline.adapters.mdo_adapter import PriceStoreAdapter
        from pipeline.config import PipelineConfig
        from pipeline.stores.price_store import PriceStore
    except ImportError:
        tdp_src = os.getenv("TDP_SRC_DIR", "")
        if tdp_src:
            import sys
            if tdp_src not in sys.path:
                sys.path.insert(0, tdp_src)
            try:
                from pipeline.adapters.mdo_adapter import PriceStoreAdapter
                from pipeline.config import PipelineConfig
                from pipeline.stores.price_store import PriceStore
            except ImportError:
                return None
        else:
            return None

    tdp_data_dir = os.getenv("TDP_DATA_DIR", "")
    if not tdp_data_dir or not Path(tdp_data_dir).exists():
        return None

    try:
        config = PipelineConfig(data_dir=Path(tdp_data_dir))
        store = PriceStore(config)
        return PriceStoreAdapter(store)
    except Exception:
        return None


def load_from_pricestore(
    instrument: str,
    timeframes: Optional[tuple[str, ...]] = None,
    source: Optional[str] = None,
    price_basis: Optional[str] = None,
) -> dict[str, pd.DataFrame]:
    """Load timeframes from TDP PriceStore via PriceStoreAdapter.

    Returns the same shape as load_all_timeframes():
    dict mapping MDO timeframe codes to UTC DatetimeIndex DataFrames
    with [open, high, low, close, volume] columns.

    Missing timeframes return empty DataFrame (not KeyError).

    Source selection: if source/price_basis are not specified,
    PriceStoreAdapter applies its documented default precedence
    (bid > mid, capital > oanda).
    """
    adapter = _get_pricestore_adapter()
    if adapter is None:
        raise RuntimeError("PriceStore not available")

    if timeframes is None:
        timeframes = tuple(get_expected_timeframes(instrument))

    return adapter.get_timeframes(
        instrument, timeframes, source=source, price_basis=price_basis,
    )


def load_manifest(instrument: str, packages_dir: Path = PACKAGES_DIR) -> dict:
    """Load and parse the JSON manifest for an instrument's hot package.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory.

    Returns:
        Parsed manifest dict with keys: instrument, as_of_utc, schema, windows.

    Raises:
        FileNotFoundError: If the manifest file does not exist.
    """
    manifest_path = packages_dir / f"{instrument}_hot.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Hot package manifest not found for {instrument}. "
            f"Has the feed pipeline run? Expected: {manifest_path}"
        )
    return json.loads(manifest_path.read_text())


def load_timeframe(
    instrument: str,
    tf: str,
    packages_dir: Path = PACKAGES_DIR,
) -> pd.DataFrame:
    """Load a single timeframe CSV from the hot package.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        tf: Timeframe label, e.g. '1h'.
        packages_dir: Path to the hot packages directory.

    Returns:
        UTC-aware DataFrame with DatetimeIndex and OHLCV columns.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
    """
    csv_path = packages_dir / f"{instrument}_{tf}_latest.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Hot package CSV not found: {csv_path}")

    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)

    # Ensure UTC-aware index
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize("UTC")

    df.index.name = "timestamp_utc"
    return df


def _load_from_csv(
    instrument: str,
    packages_dir: Path = PACKAGES_DIR,
) -> Dict[str, pd.DataFrame]:
    """Load all available timeframes from CSV hot packages (legacy path)."""
    result = {}
    for tf in EXPECTED_TIMEFRAMES:
        try:
            result[tf] = load_timeframe(instrument, tf, packages_dir)
        except FileNotFoundError:
            continue
    return result


def load_all_timeframes(
    instrument: str,
    packages_dir: Path = PACKAGES_DIR,
    use_pricestore: bool = True,
) -> Dict[str, pd.DataFrame]:
    """Load all available timeframe DataFrames for an instrument.

    If use_pricestore=True (default) and PriceStore is configured,
    reads from PriceStore via PriceStoreAdapter.
    Falls back to file-based hot package CSVs if PriceStore is
    unavailable or unconfigured.

    Fallback is all-or-nothing infrastructure switch, not per-timeframe.
    Empty PriceStore data is a genuine data gap, not a fallback trigger.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory (fallback).
        use_pricestore: If True, attempt PriceStore first.

    Returns:
        Dict mapping timeframe label to DataFrame. Missing timeframes are omitted.
    """
    if use_pricestore:
        try:
            result = load_from_pricestore(instrument)
            # Filter out empty DataFrames to match legacy behavior
            result = {tf: df for tf, df in result.items() if not df.empty}
            n_tfs = len(result)
            logger.info("Loaded %s from PriceStore (%d timeframes)", instrument, n_tfs)
            return result
        except Exception as e:
            logger.warning(
                "PriceStore unavailable (%s), falling back to CSV for %s",
                e, instrument,
            )

    return _load_from_csv(instrument, packages_dir)
