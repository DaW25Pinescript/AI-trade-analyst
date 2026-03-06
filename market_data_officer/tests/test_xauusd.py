"""Phase 1B — XAUUSD end-to-end and verification tests.

Tests cover:
- Verification gate artefacts (Group 1)
- Fetch layer for XAUUSD (Group 2)
- Decode layer plausibility (Group 3)
- Aggregation and validation (Group 4)
- Price range guards (RULE X1, X2)
"""

import json
import lzma
import struct
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from feed.config import INSTRUMENTS, PRICE_RANGES, InstrumentMeta
from feed.decode import decode_dukascopy_ticks
from feed.aggregate import ticks_to_1m_ohlcv
from feed.fetch import build_bi5_url
from feed.validate import validate_ohlcv


def _make_bi5_payload(ticks: list[tuple]) -> bytes:
    """Create a fake bi5 payload from a list of (time_ms, ask_raw, bid_raw, ask_vol, bid_vol)."""
    raw = b""
    for t_ms, ask, bid, avol, bvol in ticks:
        raw += struct.pack(">IIIff", t_ms, ask, bid, avol, bvol)
    return lzma.compress(raw)


# ---------------------------------------------------------------------------
# Group 1 — Verification gate artefacts
# ---------------------------------------------------------------------------

class TestVerificationGate:
    """Group 1 — Verification artefacts exist in config.py."""

    def test_t1_1_verification_note_exists(self):
        """T1.1 — Verification note exists in config.py."""
        config_path = Path(__file__).resolve().parent.parent / "feed" / "config.py"
        content = config_path.read_text()
        assert "XAUUSD Verification" in content

    def test_t1_2_at_least_5_bars_documented(self):
        """T1.2 — At least 5 bars documented in verification output."""
        config_path = Path(__file__).resolve().parent.parent / "feed" / "config.py"
        content = config_path.read_text()
        # Check for 5 date rows in the comparison table
        date_markers = ["2025-01-13", "2025-01-14", "2025-01-15", "2025-01-16", "2025-01-17"]
        found = sum(1 for d in date_markers if d in content)
        assert found >= 5, f"Only {found} date references found in verification note, need >= 5"

    def test_t1_3_price_scale_explicitly_stated(self):
        """T1.3 — Price scale is explicitly stated and justified."""
        config_path = Path(__file__).resolve().parent.parent / "feed" / "config.py"
        content = config_path.read_text()
        assert "Price scale confirmed: 1000" in content

    def test_t1_4_volume_semantics_documented(self):
        """T1.4 — Volume semantics are explicitly documented."""
        config_path = Path(__file__).resolve().parent.parent / "feed" / "config.py"
        content = config_path.read_text()
        assert "Volume semantics:" in content

    def test_t1_5_status_not_unresolved(self):
        """T1.5 — Verification status is not UNRESOLVED."""
        config_path = Path(__file__).resolve().parent.parent / "feed" / "config.py"
        content = config_path.read_text()
        assert "Status: VERIFIED" in content
        assert "Status: UNRESOLVED" not in content


# ---------------------------------------------------------------------------
# Group 2 — XAUUSD fetch layer
# ---------------------------------------------------------------------------

class TestXAUUSDFetch:
    """Group 2 — XAUUSD fetch URL construction."""

    def test_t2_1_url_construction_zero_based_month(self):
        """T2.1 — XAUUSD URL construction uses zero-based month."""
        dt = datetime(2025, 3, 15, 9, 0, 0, tzinfo=timezone.utc)
        url = build_bi5_url("XAUUSD", dt)
        assert "XAUUSD" in url
        assert "/2025/02/15/09h_ticks.bi5" in url  # month 3 → zero-based 02


# ---------------------------------------------------------------------------
# Group 3 — XAUUSD decode layer
# ---------------------------------------------------------------------------

class TestXAUUSDDecode:
    """Group 3 — XAUUSD decode produces plausible gold prices."""

    def setup_method(self):
        self.meta = INSTRUMENTS["XAUUSD"]
        self.hour_start = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

    def test_t3_1_decoded_mid_prices_in_gold_range(self):
        """T3.1 — Decoded XAUUSD mid prices are in plausible gold range."""
        # Simulating realistic XAUUSD ticks at ~$2,694
        payload = _make_bi5_payload([
            (0, 2694105, 2693565, 0.000120, 0.000120),
            (1000, 2694161, 2693665, 0.000450, 0.000120),
            (2000, 2694185, 2693695, 0.000120, 0.000120),
            (3000, 2694271, 2693935, 0.000450, 0.000120),
            (4000, 2694441, 2693725, 0.000450, 0.000120),
        ])
        df = decode_dukascopy_ticks(payload, self.hour_start, self.meta)

        assert not df.empty
        assert df["mid"].between(1_500.0, 3_500.0).all(), (
            f"XAUUSD mid prices out of plausible range: {df['mid'].describe()}"
        )

    def test_t3_2_xauusd_uses_own_instrument_meta(self):
        """T3.2 — XAUUSD uses its own InstrumentMeta, not EURUSD's."""
        eurusd_meta = INSTRUMENTS["EURUSD"]
        xauusd_meta = INSTRUMENTS["XAUUSD"]
        assert xauusd_meta.price_scale != eurusd_meta.price_scale, (
            "XAUUSD and EURUSD should not share the same price scale"
        )

    def test_t3_3_corrupt_or_empty_bytes_return_empty(self):
        """T3.3 — Corrupt or empty bytes return empty DataFrame."""
        result = decode_dukascopy_ticks(b"", self.hour_start, self.meta)
        assert result.empty

        result = decode_dukascopy_ticks(b"invalid", self.hour_start, self.meta)
        assert result.empty

    def test_xauusd_price_scale_1000_produces_correct_values(self):
        """Verify price_scale=1000: raw ask=2715695 → $2715.695."""
        payload = _make_bi5_payload([
            (17, 2715695, 2715195, 0.0014, 0.0001),
        ])
        df = decode_dukascopy_ticks(payload, self.hour_start, self.meta)
        expected_mid = (2715.695 + 2715.195) / 2.0  # 2715.445
        assert abs(df["mid"].iloc[0] - expected_mid) < 0.01

    def test_xauusd_volume_no_divisor(self):
        """XAUUSD volume is sum of ask_vol + bid_vol with no divisor."""
        payload = _make_bi5_payload([
            (0, 2715000, 2714500, 0.0014, 0.0001),
        ])
        df = decode_dukascopy_ticks(payload, self.hour_start, self.meta)
        assert abs(df["volume"].iloc[0] - 0.0015) < 1e-6


# ---------------------------------------------------------------------------
# Group 4 — XAUUSD aggregation and validation
# ---------------------------------------------------------------------------

class TestXAUUSDAggregate:
    """Group 4 — XAUUSD 1m OHLCV aggregation."""

    def setup_method(self):
        self.meta = INSTRUMENTS["XAUUSD"]
        self.hour_start = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

    def test_t4_1_ohlcv_schema_correct(self):
        """T4.1 — 1m OHLCV schema is correct."""
        # Create ticks spanning 2 minutes
        payload = _make_bi5_payload([
            (0, 2694000, 2693500, 0.001, 0.001),
            (30000, 2694500, 2694000, 0.002, 0.001),
            (60000, 2695000, 2694500, 0.001, 0.002),
            (90000, 2695500, 2695000, 0.003, 0.001),
        ])
        ticks = decode_dukascopy_ticks(payload, self.hour_start, self.meta)
        bars = ticks_to_1m_ohlcv(ticks)

        assert not bars.empty
        assert set(bars.columns) >= {"open", "high", "low", "close", "volume"}
        assert bars.index.tzinfo is not None
        assert bars.index.is_monotonic_increasing

    def test_no_mid_column_in_ohlcv(self):
        """T4.5 — No mid column in aggregated OHLCV output."""
        payload = _make_bi5_payload([
            (0, 2694000, 2693500, 0.001, 0.001),
            (60000, 2695000, 2694500, 0.001, 0.002),
        ])
        ticks = decode_dukascopy_ticks(payload, self.hour_start, self.meta)
        bars = ticks_to_1m_ohlcv(ticks)
        assert "mid" not in bars.columns

    def test_xauusd_ohlcv_passes_validation(self):
        """XAUUSD 1m bars pass the standard OHLCV validation."""
        payload = _make_bi5_payload([
            (0, 2694000, 2693500, 0.001, 0.001),
            (10000, 2694500, 2694000, 0.002, 0.001),
            (20000, 2693800, 2693300, 0.001, 0.001),
            (40000, 2694200, 2693700, 0.003, 0.001),
        ])
        ticks = decode_dukascopy_ticks(payload, self.hour_start, self.meta)
        bars = ticks_to_1m_ohlcv(ticks)
        validate_ohlcv(bars, "test_xauusd_1m")  # should not raise


# ---------------------------------------------------------------------------
# Price range guards (RULE X1, X2)
# ---------------------------------------------------------------------------

class TestPriceRangeGuards:
    """RULE X1 / X2 — Instrument-specific price range guards."""

    def test_xauusd_price_range_defined(self):
        """XAUUSD has its own price range in PRICE_RANGES."""
        assert "XAUUSD" in PRICE_RANGES
        low, high = PRICE_RANGES["XAUUSD"]
        assert low == 1_500.0
        assert high == 3_500.0

    def test_eurusd_price_range_defined(self):
        """EURUSD has its own price range in PRICE_RANGES."""
        assert "EURUSD" in PRICE_RANGES
        low, high = PRICE_RANGES["EURUSD"]
        assert low == 0.8
        assert high == 1.5

    def test_xauusd_range_not_same_as_eurusd(self):
        """RULE X2 — XAUUSD and EURUSD do not share price range guards."""
        assert PRICE_RANGES["XAUUSD"] != PRICE_RANGES["EURUSD"]

    def test_xauusd_plausibility_check(self):
        """RULE X1 — XAUUSD prices must pass plausibility check."""
        meta = INSTRUMENTS["XAUUSD"]
        hour_start = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        payload = _make_bi5_payload([
            (0, 2694105, 2693565, 0.000120, 0.000120),
        ])
        ticks = decode_dukascopy_ticks(payload, hour_start, meta)
        bars = ticks_to_1m_ohlcv(ticks)

        low, high = PRICE_RANGES["XAUUSD"]
        assert bars["close"].between(low, high).all(), (
            f"XAUUSD close prices out of plausible range {PRICE_RANGES['XAUUSD']}"
        )
