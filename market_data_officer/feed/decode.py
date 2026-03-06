"""Dukascopy bi5 tick decode layer — decompresses and parses tick structs."""

import lzma
import struct
from datetime import datetime, timedelta, timezone

import pandas as pd

from .config import TICK_STRUCT_SIZE, InstrumentMeta


# TODO Phase 1B — XAUUSD
# The 20-byte tick struct format (>IIIff) is the same for all Dukascopy instruments,
# but the MEANING of the raw integer fields depends on the instrument:
#   - price_scale differs (EURUSD=100000, XAUUSD likely=1000 but MUST be verified)
#   - volume interpretation may differ (raw float vs lots vs units)
# Do NOT assume EURUSD parsing logic is correct for XAUUSD without independent
# verification against a known reference bar.


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
