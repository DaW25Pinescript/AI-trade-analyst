"""Tests for the decode layer."""

import lzma
import struct
from datetime import datetime, timezone

import pandas as pd
import pytest

from feed.config import INSTRUMENTS
from feed.decode import decode_dukascopy_ticks


def _make_bi5_payload(ticks: list[tuple]) -> bytes:
    """Create a fake bi5 payload from a list of (time_ms, ask_raw, bid_raw, ask_vol, bid_vol)."""
    raw = b""
    for t_ms, ask, bid, avol, bvol in ticks:
        raw += struct.pack(">IIIff", t_ms, ask, bid, avol, bvol)
    return lzma.compress(raw)


class TestDecodeDukascopyTicks:
    """Tests for decode_dukascopy_ticks."""

    def setup_method(self):
        self.meta = INSTRUMENTS["EURUSD"]
        self.hour_start = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)

    def test_decode_correct_schema(self):
        """T2.1 — Tick decode produces correct schema."""
        payload = _make_bi5_payload([
            (0, 109000, 108980, 1.0, 1.0),
            (1000, 109010, 108990, 2.0, 2.0),
        ])
        df = decode_dukascopy_ticks(payload, self.hour_start, self.meta)

        assert not df.empty
        assert set(df.columns) >= {"mid", "volume"}
        assert df.index.name == "timestamp_utc"
        assert df.index.tzinfo is not None
        assert df.index.is_monotonic_increasing

    def test_price_scale_eurusd(self):
        """T2.2 — Price scale applied correctly for EURUSD."""
        # ask=109050 / 100000 = 1.09050, bid=109030 / 100000 = 1.09030
        # mid = (1.09050 + 1.09030) / 2 = 1.09040
        payload = _make_bi5_payload([
            (0, 109050, 109030, 1.0, 1.0),
        ])
        df = decode_dukascopy_ticks(payload, self.hour_start, self.meta)

        assert df["mid"].between(0.8, 1.5).all()
        assert abs(df["mid"].iloc[0] - 1.09040) < 1e-6

    def test_empty_bytes_returns_empty(self):
        """T2.3 — Empty bytes return empty DataFrame."""
        result = decode_dukascopy_ticks(b"", self.hour_start, self.meta)
        assert result.empty

    def test_corrupt_bytes_returns_empty(self):
        """T2.3 — Corrupt bytes return empty DataFrame."""
        result = decode_dukascopy_ticks(b"not_valid_lzma_data", self.hour_start, self.meta)
        assert result.empty

    def test_naive_datetime_raises(self):
        """Naive datetime raises ValueError."""
        naive = datetime(2025, 1, 15, 9, 0, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            decode_dukascopy_ticks(b"", naive, self.meta)

    def test_volume_sum(self):
        """Volume is sum of ask_vol + bid_vol."""
        payload = _make_bi5_payload([
            (0, 109000, 108980, 3.5, 2.5),
        ])
        df = decode_dukascopy_ticks(payload, self.hour_start, self.meta)
        assert abs(df["volume"].iloc[0] - 6.0) < 1e-6


class TestDecodeXAUUSD:
    """Phase 1B — XAUUSD-specific decode tests."""

    def setup_method(self):
        self.meta = INSTRUMENTS["XAUUSD"]
        self.hour_start = datetime(2025, 1, 16, 14, 0, 0, tzinfo=timezone.utc)

    def test_price_scale_xauusd(self):
        """XAUUSD price_scale=1000 produces plausible gold prices.

        Verification reference: Dukascopy bi5 2025-01-16 14:00 UTC showed
        raw ask=2715695 → $2715.695, matching known spot ~$2702-2720.
        """
        # ask=2715695 / 1000 = 2715.695, bid=2715195 / 1000 = 2715.195
        # mid = (2715.695 + 2715.195) / 2 = 2715.445
        payload = _make_bi5_payload([
            (17, 2715695, 2715195, 0.0014, 0.0001),
        ])
        df = decode_dukascopy_ticks(payload, self.hour_start, self.meta)

        assert not df.empty
        assert df["mid"].between(2000.0, 4000.0).all(), (
            f"XAUUSD mid outside plausible range: {df['mid'].iloc[0]}"
        )
        assert abs(df["mid"].iloc[0] - 2715.445) < 0.01

    def test_xauusd_schema_matches_eurusd(self):
        """XAUUSD decode produces same schema as EURUSD."""
        payload = _make_bi5_payload([
            (0, 2715000, 2714500, 0.001, 0.001),
            (1000, 2715100, 2714600, 0.002, 0.002),
        ])
        df = decode_dukascopy_ticks(payload, self.hour_start, self.meta)

        assert set(df.columns) >= {"mid", "volume"}
        assert df.index.name == "timestamp_utc"
        assert df.index.tzinfo is not None
        assert df.index.is_monotonic_increasing

    def test_xauusd_volume_no_divisor(self):
        """XAUUSD volume is sum of ask_vol + bid_vol with no divisor."""
        payload = _make_bi5_payload([
            (0, 2715000, 2714500, 0.0014, 0.0001),
        ])
        df = decode_dukascopy_ticks(payload, self.hour_start, self.meta)
        assert abs(df["volume"].iloc[0] - 0.0015) < 1e-6

    def test_xauusd_multiple_ticks_range(self):
        """Multiple XAUUSD ticks produce prices in plausible range."""
        payload = _make_bi5_payload([
            (0, 2715000, 2714500, 0.001, 0.001),
            (500, 2716000, 2715500, 0.002, 0.001),
            (1000, 2714000, 2713500, 0.001, 0.002),
            (1500, 2715500, 2715000, 0.003, 0.001),
        ])
        df = decode_dukascopy_ticks(payload, self.hour_start, self.meta)

        assert len(df) == 4
        assert df["mid"].between(2000.0, 4000.0).all()
