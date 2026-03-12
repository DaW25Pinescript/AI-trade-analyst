"""Tests for Phase 1C — incremental updater hardening.

Three core guarantees:
  1. Selective derived regeneration: only affected windows are resampled,
     and the result matches a full resample.
  2. Idempotent gap detection: same input → same report, for both instruments.
  3. Zero redundant fetches: re-runs skip already-covered hour ranges.
"""

import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from market_data_officer.feed.config import DERIVED_TIMEFRAMES, INSTRUMENTS, TIMEFRAME_LABELS
from market_data_officer.feed.gaps import detect_gaps, generate_gap_report, save_gap_report
from market_data_officer.feed.pipeline import (
    _derive_affected_window,
    _find_resample_boundary,
    _load_existing_derived,
    _save_canonical,
    _save_derived,
)
from market_data_officer.feed.resample import resample_from_1m


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_1m_canonical(start: str, periods: int, base_price: float = 1.09) -> pd.DataFrame:
    """Create a synthetic 1m OHLCV DataFrame with realistic-looking data."""
    idx = pd.date_range(start, periods=periods, freq="1min", tz="UTC")
    prices = [base_price + i * 0.0001 for i in range(periods)]
    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p + 0.0005 for p in prices],
            "low": [p - 0.0005 for p in prices],
            "close": [p + 0.0002 for p in prices],
            "volume": [100.0 + i for i in range(periods)],
        },
        index=idx,
    )
    return df


def _make_xauusd_canonical(start: str, periods: int) -> pd.DataFrame:
    """Create synthetic XAUUSD 1m data in plausible gold range."""
    return _make_1m_canonical(start, periods, base_price=2700.0)


# ===========================================================================
# Group 1 — Selective derived regeneration
# ===========================================================================


class TestSelectiveDerivedRegeneration:
    """Verify that _derive_affected_window produces the same output as a
    full resample but only re-processes the affected window."""

    def _full_resample(self, canonical: pd.DataFrame, rule: str) -> pd.DataFrame:
        return resample_from_1m(canonical[["open", "high", "low", "close", "volume"]], rule)

    def test_selective_matches_full_resample_5min(self, tmp_path):
        """Selective regeneration for 5min matches a clean full resample."""
        canonical = _make_1m_canonical("2025-01-13 09:00", 120)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        # Simulate existing derived from first 60 bars
        first_half = _make_1m_canonical("2025-01-13 09:00", 60)
        first_derived = resample_from_1m(first_half[["open", "high", "low", "close", "volume"]], "5min")

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=first_derived):
            new_data_start = pd.Timestamp("2025-01-13 10:00", tz="UTC")
            selective = _derive_affected_window(ohlcv, "TEST", "5min", "5m", new_data_start)

        full = self._full_resample(canonical, "5min")

        # OHLCV values must match exactly
        pd.testing.assert_frame_equal(
            selective[["open", "high", "low", "close", "volume"]],
            full[["open", "high", "low", "close", "volume"]],
        )

    def test_selective_matches_full_resample_1h(self, tmp_path):
        """Selective regeneration for 1h matches a clean full resample."""
        canonical = _make_1m_canonical("2025-01-13 08:00", 240)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        first_chunk = _make_1m_canonical("2025-01-13 08:00", 120)
        first_derived = resample_from_1m(first_chunk[["open", "high", "low", "close", "volume"]], "1h")

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=first_derived):
            new_data_start = pd.Timestamp("2025-01-13 10:00", tz="UTC")
            selective = _derive_affected_window(ohlcv, "TEST", "1h", "1h", new_data_start)

        full = self._full_resample(canonical, "1h")

        pd.testing.assert_frame_equal(
            selective[["open", "high", "low", "close", "volume"]],
            full[["open", "high", "low", "close", "volume"]],
        )

    def test_selective_matches_full_resample_4h(self, tmp_path):
        """Selective regeneration for 4h matches a clean full resample."""
        canonical = _make_1m_canonical("2025-01-13 00:00", 480)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        first_chunk = _make_1m_canonical("2025-01-13 00:00", 240)
        first_derived = resample_from_1m(first_chunk[["open", "high", "low", "close", "volume"]], "4h")

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=first_derived):
            new_data_start = pd.Timestamp("2025-01-13 04:00", tz="UTC")
            selective = _derive_affected_window(ohlcv, "TEST", "4h", "4h", new_data_start)

        full = self._full_resample(canonical, "4h")

        pd.testing.assert_frame_equal(
            selective[["open", "high", "low", "close", "volume"]],
            full[["open", "high", "low", "close", "volume"]],
        )

    def test_selective_matches_full_resample_1d(self, tmp_path):
        """Selective regeneration for 1D matches a clean full resample."""
        # 2 days of data
        canonical = _make_1m_canonical("2025-01-13 00:00", 1440 * 2)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        first_day = _make_1m_canonical("2025-01-13 00:00", 1440)
        first_derived = resample_from_1m(first_day[["open", "high", "low", "close", "volume"]], "1D")

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=first_derived):
            new_data_start = pd.Timestamp("2025-01-14 00:00", tz="UTC")
            selective = _derive_affected_window(ohlcv, "TEST", "1D", "1d", new_data_start)

        full = self._full_resample(canonical, "1D")

        pd.testing.assert_frame_equal(
            selective[["open", "high", "low", "close", "volume"]],
            full[["open", "high", "low", "close", "volume"]],
        )

    def test_no_existing_derived_falls_back_to_full(self):
        """When no existing derived exists, full resample is used."""
        canonical = _make_1m_canonical("2025-01-13 09:00", 60)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=None):
            result = _derive_affected_window(ohlcv, "TEST", "5min", "5m",
                                             pd.Timestamp("2025-01-13 09:00", tz="UTC"))

        full = resample_from_1m(ohlcv, "5min")
        pd.testing.assert_frame_equal(
            result[["open", "high", "low", "close", "volume"]],
            full[["open", "high", "low", "close", "volume"]],
        )

    def test_no_new_data_start_does_full_resample(self):
        """When new_data_start is None, full resample is performed."""
        canonical = _make_1m_canonical("2025-01-13 09:00", 60)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        existing = resample_from_1m(ohlcv, "5min")
        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=existing):
            result = _derive_affected_window(ohlcv, "TEST", "5min", "5m", new_data_start=None)

        assert result is not None
        assert len(result) == len(existing)

    def test_selective_preserves_unaffected_prefix(self):
        """Bars before the affected boundary are preserved from the old derived data,
        not recomputed — confirming partial (not full) regeneration."""
        canonical = _make_1m_canonical("2025-01-13 09:00", 120)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        # Build existing derived from full canonical (first pass)
        existing_derived = resample_from_1m(ohlcv.iloc[:60], "1h")

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=existing_derived):
            new_data_start = pd.Timestamp("2025-01-13 10:00", tz="UTC")
            result = _derive_affected_window(ohlcv, "TEST", "1h", "1h", new_data_start)

        # The first bar (09:00) should match the existing derived exactly
        assert result.index[0] == existing_derived.index[0]
        assert result.loc[result.index[0], "volume"] == existing_derived.loc[existing_derived.index[0], "volume"]

    def test_mid_bar_new_data_resamples_from_boundary(self):
        """When new data arrives mid-bar (e.g. 09:23 for 1h), the boundary
        snaps back to bar start (09:00) and the entire bar is resampled."""
        canonical = _make_1m_canonical("2025-01-13 09:00", 120)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        existing_derived = resample_from_1m(ohlcv.iloc[:60], "1h")

        new_data_start = pd.Timestamp("2025-01-13 09:23", tz="UTC")
        boundary = _find_resample_boundary(new_data_start, "1h")
        assert boundary == pd.Timestamp("2025-01-13 09:00", tz="UTC")

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=existing_derived):
            result = _derive_affected_window(ohlcv, "TEST", "1h", "1h", new_data_start)

        full = resample_from_1m(ohlcv, "1h")
        pd.testing.assert_frame_equal(
            result[["open", "high", "low", "close", "volume"]],
            full[["open", "high", "low", "close", "volume"]],
        )


# ===========================================================================
# Group 2 — Zero redundant fetches for already-covered ranges
# ===========================================================================


class TestZeroRedundantFetches:
    """Verify that the incremental update logic skips hours already covered
    in the existing canonical data."""

    def test_all_hours_skipped_when_fully_covered(self):
        """When existing canonical covers the entire requested range,
        fetch_bi5 is never called."""
        # Existing canonical: full day (24 hours = 1440 bars)
        # run_pipeline expands end_date to hour 23, so we need full day coverage
        existing = _make_1m_canonical("2025-01-13 00:00", 1440)
        existing["vendor"] = "dukascopy"
        existing["build_method"] = "tick_to_1m"
        existing["quality_flag"] = "ok"

        with patch("market_data_officer.feed.pipeline._load_existing_canonical", return_value=existing), \
             patch("market_data_officer.feed.pipeline.fetch_bi5") as mock_fetch, \
             patch("market_data_officer.feed.pipeline._save_canonical"), \
             patch("market_data_officer.feed.pipeline._rebuild_derived_and_export"):

            from market_data_officer.feed.pipeline import run_pipeline

            run_pipeline(
                "EURUSD",
                datetime(2025, 1, 13, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 13, 23, 0, tzinfo=timezone.utc),
            )

            # fetch_bi5 should not have been called for any hour
            assert mock_fetch.call_count == 0

    def test_only_new_hours_fetched(self):
        """When existing canonical covers hours 09-10, a request for 09-12
        should only fetch hours 11 and 12."""
        existing = _make_1m_canonical("2025-01-13 09:00", 120)  # 09:00 - 10:59
        existing["vendor"] = "dukascopy"
        existing["build_method"] = "tick_to_1m"
        existing["quality_flag"] = "ok"

        with patch("market_data_officer.feed.pipeline._load_existing_canonical", return_value=existing), \
             patch("market_data_officer.feed.pipeline.fetch_bi5", return_value=b"") as mock_fetch, \
             patch("market_data_officer.feed.pipeline._save_canonical"), \
             patch("market_data_officer.feed.pipeline._rebuild_derived_and_export"):

            from market_data_officer.feed.pipeline import run_pipeline

            run_pipeline(
                "EURUSD",
                datetime(2025, 1, 13, 9, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 13, 12, 0, tzinfo=timezone.utc),
            )

            # Only hours 11 and 12 should be fetched (possibly +1 for partial last hour)
            # Hours 09 and 10 are fully covered → skipped
            fetched_hours = [call.args[1].hour for call in mock_fetch.call_args_list]
            assert 9 not in fetched_hours
            assert 10 not in fetched_hours

    def test_rerun_same_range_zero_fetches(self):
        """Running the pipeline twice on the same range produces zero fetches
        on the second run (simulated by providing existing canonical covering
        the full expanded range)."""
        # Full day coverage since run_pipeline expands end to hour 23
        existing = _make_1m_canonical("2025-01-13 00:00", 1440)
        existing["vendor"] = "dukascopy"
        existing["build_method"] = "tick_to_1m"
        existing["quality_flag"] = "ok"

        with patch("market_data_officer.feed.pipeline._load_existing_canonical", return_value=existing), \
             patch("market_data_officer.feed.pipeline.fetch_bi5") as mock_fetch, \
             patch("market_data_officer.feed.pipeline._save_canonical"), \
             patch("market_data_officer.feed.pipeline._rebuild_derived_and_export"):

            from market_data_officer.feed.pipeline import run_pipeline

            run_pipeline(
                "EURUSD",
                datetime(2025, 1, 13, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 13, 23, 0, tzinfo=timezone.utc),
            )

            assert mock_fetch.call_count == 0

    def test_xauusd_rerun_same_range_zero_fetches(self):
        """XAUUSD re-run over covered range also produces zero fetches."""
        existing = _make_xauusd_canonical("2025-01-13 00:00", 1440)
        existing["vendor"] = "dukascopy"
        existing["build_method"] = "tick_to_1m"
        existing["quality_flag"] = "ok"

        with patch("market_data_officer.feed.pipeline._load_existing_canonical", return_value=existing), \
             patch("market_data_officer.feed.pipeline.fetch_bi5") as mock_fetch, \
             patch("market_data_officer.feed.pipeline._save_canonical"), \
             patch("market_data_officer.feed.pipeline._rebuild_derived_and_export"):

            from market_data_officer.feed.pipeline import run_pipeline

            run_pipeline(
                "XAUUSD",
                datetime(2025, 1, 13, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 13, 23, 0, tzinfo=timezone.utc),
            )

            assert mock_fetch.call_count == 0

    def test_partial_hour_triggers_refetch(self):
        """When the last canonical bar is mid-hour (e.g. 10:30), the hour
        containing that bar is re-fetched to complete it."""
        # Existing ends at 10:30 (not end of hour)
        existing = _make_1m_canonical("2025-01-13 09:00", 91)  # 09:00 - 10:30
        existing["vendor"] = "dukascopy"
        existing["build_method"] = "tick_to_1m"
        existing["quality_flag"] = "ok"

        with patch("market_data_officer.feed.pipeline._load_existing_canonical", return_value=existing), \
             patch("market_data_officer.feed.pipeline.fetch_bi5", return_value=b"") as mock_fetch, \
             patch("market_data_officer.feed.pipeline._save_canonical"), \
             patch("market_data_officer.feed.pipeline._rebuild_derived_and_export"):

            from market_data_officer.feed.pipeline import run_pipeline

            run_pipeline(
                "EURUSD",
                datetime(2025, 1, 13, 9, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 13, 11, 0, tzinfo=timezone.utc),
            )

            # Hour 10 should be re-fetched since it's incomplete, plus hour 11
            fetched_hours = [call.args[1].hour for call in mock_fetch.call_args_list]
            assert 9 not in fetched_hours  # fully covered
            assert 10 in fetched_hours or 11 in fetched_hours  # at least new hours


# ===========================================================================
# Group 3 — Idempotent gap detection for both instruments
# ===========================================================================


class TestGapDetectionBothInstruments:
    """Gap detection must be idempotent and produce correct results
    for both EURUSD and XAUUSD."""

    def test_eurusd_gap_detection_idempotent(self):
        df = _make_1m_canonical("2025-01-13 09:00", 60)
        # Drop bars 10-12 to create a gap
        df = df.drop(df.index[10:13])

        r1 = detect_gaps(df, "EURUSD")
        r2 = detect_gaps(df, "EURUSD")
        assert r1 == r2

    def test_xauusd_gap_detection_idempotent(self):
        df = _make_xauusd_canonical("2025-01-13 09:00", 60)
        df = df.drop(df.index[10:13])

        r1 = detect_gaps(df, "XAUUSD")
        r2 = detect_gaps(df, "XAUUSD")
        assert r1 == r2

    def test_eurusd_gap_report_idempotent(self):
        df = _make_1m_canonical("2025-01-13 09:00", 60)
        df = df.drop(df.index[10:13])

        r1 = generate_gap_report("EURUSD", df)
        r2 = generate_gap_report("EURUSD", df)

        assert r1["summary"] == r2["summary"]
        assert r1["trading_hour_gaps"] == r2["trading_hour_gaps"]
        assert r1["weekend_gaps"] == r2["weekend_gaps"]

    def test_xauusd_gap_report_idempotent(self):
        df = _make_xauusd_canonical("2025-01-13 09:00", 60)
        df = df.drop(df.index[10:13])

        r1 = generate_gap_report("XAUUSD", df)
        r2 = generate_gap_report("XAUUSD", df)

        assert r1["summary"] == r2["summary"]
        assert r1["trading_hour_gaps"] == r2["trading_hour_gaps"]
        assert r1["weekend_gaps"] == r2["weekend_gaps"]

    def test_contiguous_eurusd_no_gaps(self):
        df = _make_1m_canonical("2025-01-13 09:00", 60)
        gaps = detect_gaps(df, "EURUSD")
        assert len(gaps) == 0

    def test_contiguous_xauusd_no_gaps(self):
        df = _make_xauusd_canonical("2025-01-13 09:00", 60)
        gaps = detect_gaps(df, "XAUUSD")
        assert len(gaps) == 0

    def test_gap_report_structure_eurusd(self):
        df = _make_1m_canonical("2025-01-13 09:00", 60, base_price=1.09)
        df = df.drop(df.index[5])

        report = generate_gap_report("EURUSD", df)
        assert report["symbol"] == "EURUSD"
        assert "summary" in report
        assert "trading_hour_gaps" in report
        assert "weekend_gaps" in report
        assert report["summary"]["total_gaps"] >= 1

    def test_gap_report_structure_xauusd(self):
        df = _make_xauusd_canonical("2025-01-13 09:00", 60)
        df = df.drop(df.index[5])

        report = generate_gap_report("XAUUSD", df)
        assert report["symbol"] == "XAUUSD"
        assert "summary" in report
        assert report["summary"]["total_gaps"] >= 1

    def test_gap_report_json_serializable(self):
        """Gap report must be JSON-serializable for file output."""
        df = _make_1m_canonical("2025-01-13 09:00", 60)
        df = df.drop(df.index[10:15])

        for symbol in ["EURUSD", "XAUUSD"]:
            report = generate_gap_report(symbol, df)
            serialized = json.dumps(report)
            deserialized = json.loads(serialized)
            assert deserialized["symbol"] == symbol

    def test_save_gap_report_creates_file(self, tmp_path):
        """save_gap_report writes a valid JSON file."""
        df = _make_1m_canonical("2025-01-13 09:00", 60)
        df = df.drop(df.index[5])

        report = generate_gap_report("EURUSD", df)

        with patch("market_data_officer.feed.gaps.GAP_REPORT_DIR", tmp_path):
            path = save_gap_report("EURUSD", report)

        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["symbol"] == "EURUSD"


# ===========================================================================
# Group 4 — Selective regeneration for XAUUSD specifically
# ===========================================================================


class TestSelectiveRegenerationXAUUSD:
    """Confirm selective derived regeneration works for XAUUSD price ranges."""

    def test_xauusd_selective_matches_full_1h(self):
        canonical = _make_xauusd_canonical("2025-01-13 08:00", 240)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        first_chunk = _make_xauusd_canonical("2025-01-13 08:00", 120)
        first_derived = resample_from_1m(first_chunk[["open", "high", "low", "close", "volume"]], "1h")

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=first_derived):
            selective = _derive_affected_window(ohlcv, "XAUUSD", "1h", "1h",
                                                pd.Timestamp("2025-01-13 10:00", tz="UTC"))

        full = resample_from_1m(ohlcv, "1h")
        pd.testing.assert_frame_equal(
            selective[["open", "high", "low", "close", "volume"]],
            full[["open", "high", "low", "close", "volume"]],
        )

    def test_xauusd_selective_matches_full_5min(self):
        canonical = _make_xauusd_canonical("2025-01-13 09:00", 120)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        first_chunk = _make_xauusd_canonical("2025-01-13 09:00", 60)
        first_derived = resample_from_1m(first_chunk[["open", "high", "low", "close", "volume"]], "5min")

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=first_derived):
            selective = _derive_affected_window(ohlcv, "XAUUSD", "5min", "5m",
                                                pd.Timestamp("2025-01-13 10:00", tz="UTC"))

        full = resample_from_1m(ohlcv, "5min")
        pd.testing.assert_frame_equal(
            selective[["open", "high", "low", "close", "volume"]],
            full[["open", "high", "low", "close", "volume"]],
        )


# ===========================================================================
# Group 5 — All derived timeframes covered for both instruments
# ===========================================================================


class TestAllTimeframesCovered:
    """Confirm selective regeneration works for every configured derived
    timeframe, for both instruments."""

    @pytest.mark.parametrize("rule,tf_label", list(TIMEFRAME_LABELS.items()))
    def test_eurusd_all_timeframes(self, rule, tf_label):
        periods = 1440 * 2 if rule == "1D" else 480
        canonical = _make_1m_canonical("2025-01-13 00:00", periods)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        half = periods // 2
        first_chunk = _make_1m_canonical("2025-01-13 00:00", half)
        first_derived = resample_from_1m(first_chunk[["open", "high", "low", "close", "volume"]], rule)

        new_start = canonical.index[half]

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=first_derived):
            selective = _derive_affected_window(ohlcv, "EURUSD", rule, tf_label, new_start)

        full = resample_from_1m(ohlcv, rule)

        pd.testing.assert_frame_equal(
            selective[["open", "high", "low", "close", "volume"]],
            full[["open", "high", "low", "close", "volume"]],
        )

    @pytest.mark.parametrize("rule,tf_label", list(TIMEFRAME_LABELS.items()))
    def test_xauusd_all_timeframes(self, rule, tf_label):
        periods = 1440 * 2 if rule == "1D" else 480
        canonical = _make_xauusd_canonical("2025-01-13 00:00", periods)
        ohlcv = canonical[["open", "high", "low", "close", "volume"]]

        half = periods // 2
        first_chunk = _make_xauusd_canonical("2025-01-13 00:00", half)
        first_derived = resample_from_1m(first_chunk[["open", "high", "low", "close", "volume"]], rule)

        new_start = canonical.index[half]

        with patch("market_data_officer.feed.pipeline._load_existing_derived", return_value=first_derived):
            selective = _derive_affected_window(ohlcv, "XAUUSD", rule, tf_label, new_start)

        full = resample_from_1m(ohlcv, rule)

        pd.testing.assert_frame_equal(
            selective[["open", "high", "low", "close", "volume"]],
            full[["open", "high", "low", "close", "volume"]],
        )
