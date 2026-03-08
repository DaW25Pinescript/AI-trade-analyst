"""Shared test fixtures for Officer tests.

Creates synthetic hot package data that mimics the feed's export format.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure officer module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from instrument_registry import INSTRUMENT_REGISTRY, get_meta


def _generate_ohlcv(
    periods: int,
    freq: str,
    base_price: float = 1.0850,
    volatility: float = 0.0005,
    end_near_now: bool = True,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing.

    Creates a realistic random walk around a base price.
    Uses a fixed seed for determinism. Data ends near current time
    so staleness checks pass.
    """
    rng = np.random.RandomState(42)

    # Generate index ending near now so data is not stale
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    index = pd.date_range(end=now_utc, periods=periods, freq=freq, tz="UTC")

    # Random walk for close prices
    returns = rng.normal(0, volatility, periods)
    close = base_price + np.cumsum(returns)

    # Generate OHLC from close
    high = close + rng.uniform(0, volatility * 2, periods)
    low = close - rng.uniform(0, volatility * 2, periods)
    open_ = close + rng.normal(0, volatility * 0.5, periods)
    volume = rng.uniform(100, 5000, periods)

    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=index,
    )
    df.index.name = "timestamp_utc"
    return df


@pytest.fixture
def hot_packages_dir(tmp_path):
    """Create a temporary hot packages directory with synthetic EURUSD data."""
    packages_dir = tmp_path / "packages" / "latest"
    packages_dir.mkdir(parents=True)

    # Timeframe configs: label -> (pandas freq, row count)
    tf_configs = {
        "1m": ("1min", 3000),
        "5m": ("5min", 1200),
        "15m": ("15min", 600),
        "1h": ("1h", 240),
        "4h": ("4h", 120),
        "1d": ("1D", 30),
    }

    windows_manifest = {}

    for tf_label, (freq, count) in tf_configs.items():
        df = _generate_ohlcv(count, freq)
        filename = f"EURUSD_{tf_label}_latest.csv"
        df.to_csv(packages_dir / filename)
        windows_manifest[tf_label] = {
            "count": count,
            "file": filename,
        }

    # Write manifest
    manifest = {
        "instrument": "EURUSD",
        "as_of_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": "timestamp_utc,open,high,low,close,volume",
        "windows": windows_manifest,
    }
    (packages_dir / "EURUSD_hot.json").write_text(json.dumps(manifest, indent=2))

    return packages_dir


@pytest.fixture
def xauusd_hot_packages_dir(tmp_path):
    """Create a temporary hot packages directory with synthetic XAUUSD data.

    Only the analyst-target timeframes are written, matching the registry.
    """
    meta = get_meta("XAUUSD")
    packages_dir = tmp_path / "packages" / "latest"
    packages_dir.mkdir(parents=True)

    # Map label → (pandas freq, row count) for the registry timeframes
    _FREQ_MAP = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}
    _COUNT_MAP = {"1m": 3000, "5m": 1200, "15m": 600, "1h": 240, "4h": 120, "1d": 30}
    tf_configs = {
        tf: (_FREQ_MAP[tf], _COUNT_MAP[tf])
        for tf in meta.timeframes
        if tf in _FREQ_MAP
    }

    vol_lo, vol_hi = meta.fixture_volume_range
    windows_manifest = {}

    for tf_label, (freq, count) in tf_configs.items():
        df = _generate_ohlcv(
            count, freq, base_price=meta.base_price, volatility=meta.fixture_volatility,
        )
        # Scale volume to instrument range
        df["volume"] = np.random.RandomState(42).uniform(vol_lo, vol_hi, count)
        filename = f"XAUUSD_{tf_label}_latest.csv"
        df.to_csv(packages_dir / filename)
        windows_manifest[tf_label] = {
            "count": count,
            "file": filename,
        }

    manifest = {
        "instrument": "XAUUSD",
        "as_of_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": "timestamp_utc,open,high,low,close,volume",
        "windows": windows_manifest,
    }
    (packages_dir / "XAUUSD_hot.json").write_text(json.dumps(manifest, indent=2))

    return packages_dir


@pytest.fixture
def stale_packages_dir(hot_packages_dir):
    """Create hot packages with a stale manifest (3 hours old)."""
    manifest_path = hot_packages_dir / "EURUSD_hot.json"
    manifest = json.loads(manifest_path.read_text())
    three_hours_ago = datetime.now(timezone.utc) - timedelta(hours=3)
    manifest["as_of_utc"] = three_hours_ago.strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Also make the 1m CSV data stale by shifting timestamps back
    csv_path = hot_packages_dir / "EURUSD_1m_latest.csv"
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    df.index = df.index - timedelta(hours=3)
    df.to_csv(csv_path)

    return hot_packages_dir
