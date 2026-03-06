"""Dukascopy bi5 tick decode layer — decompresses and parses tick structs."""

import lzma
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import pandas as pd

from .config import TICK_STRUCT_SIZE, InstrumentMeta


@dataclass
class DecodeStats:
    """Decode statistics for diagnostics layer."""

    tick_count: int
    price_min: Optional[float]
    price_max: Optional[float]
    volume_total: Optional[float]
    error: str  # empty string if no error


# Phase 1B — XAUUSD tick struct verification notes (VERIFIED 2026-03-06)
# The 20-byte tick struct format (>IIIff) is identical for EURUSD and XAUUSD.
# Verified against Dukascopy bi5 data for 5 days (2025-01-13 to 2025-01-17):
#   - XAUUSD price_scale=1000 (raw 2694105 → $2694.105, confirmed against
#     pricegold.net and bullion-rates.com daily OHLC for 5 trading days)
#   - EURUSD price_scale=100000 (unchanged)
#   - Volume floats: same format, no divisor needed for either instrument.
#     XAUUSD volumes are naturally smaller (~0.0006/tick) vs EURUSD (~5.3/tick).
# If additional instruments are added beyond EURUSD/XAUUSD, their price_scale
# and volume interpretation MUST be independently verified before populating
# InstrumentMeta — the struct format is universal but the semantics are not.


def decode_dukascopy_ticks(
    raw_bytes: bytes,
    hour_start: datetime,
    meta: InstrumentMeta,
) -> pd.DataFrame:
    """Decode a Dukascopy bi5 payload into a tick DataFrame.

    Returns a DataFrame with columns [mid, volume] indexed by timestamp_utc.
    Returns an empty DataFrame on corrupt or empty input.
    """
    if hour_start.tzinfo is None:
        raise ValueError("hour_start must be timezone-aware (UTC)")

    if not raw_bytes:
        return pd.DataFrame()

    try:
        decompressed = lzma.decompress(raw_bytes)
    except lzma.LZMAError:
        print(f"[decode] LZMA decompression failed for {meta.symbol} at {hour_start}")
        return pd.DataFrame()

    if len(decompressed) == 0:
        return pd.DataFrame()

    n_ticks = len(decompressed) // TICK_STRUCT_SIZE
    if n_ticks == 0:
        return pd.DataFrame()

    ticks = []
    for i in range(n_ticks):
        offset = i * TICK_STRUCT_SIZE
        chunk = decompressed[offset : offset + TICK_STRUCT_SIZE]
        if len(chunk) < TICK_STRUCT_SIZE:
            break

        time_ms, ask_raw, bid_raw, ask_vol, bid_vol = struct.unpack(">IIIff", chunk)

        ts = hour_start + timedelta(milliseconds=time_ms)
        ask = ask_raw / meta.price_scale
        bid = bid_raw / meta.price_scale
        mid = (ask + bid) / 2.0

        volume = ask_vol + bid_vol
        if meta.volume_divisor is not None:
            volume = volume / meta.volume_divisor

        ticks.append({"timestamp_utc": ts, "mid": mid, "volume": volume})

    if not ticks:
        return pd.DataFrame()

    df = pd.DataFrame(ticks)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.set_index("timestamp_utc")
    df = df.sort_index()

    return df


def decode_with_diagnostics(
    raw_bytes: bytes,
    hour_start: datetime,
    meta: InstrumentMeta,
) -> Tuple[pd.DataFrame, DecodeStats]:
    """Decode a bi5 payload and return both the tick DataFrame and decode stats.

    Wraps decode_dukascopy_ticks, capturing price range, tick count, and
    volume totals for the diagnostics layer.
    """
    if not raw_bytes:
        return pd.DataFrame(), DecodeStats(
            tick_count=0, price_min=None, price_max=None,
            volume_total=None, error="empty_input",
        )

    try:
        df = decode_dukascopy_ticks(raw_bytes, hour_start, meta)
    except Exception as exc:
        return pd.DataFrame(), DecodeStats(
            tick_count=0, price_min=None, price_max=None,
            volume_total=None, error=str(exc),
        )

    if df.empty:
        return df, DecodeStats(
            tick_count=0, price_min=None, price_max=None,
            volume_total=None, error="",
        )

    return df, DecodeStats(
        tick_count=len(df),
        price_min=float(df["mid"].min()),
        price_max=float(df["mid"].max()),
        volume_total=float(df["volume"].sum()),
        error="",
    )
