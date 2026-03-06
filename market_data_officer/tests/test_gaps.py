"""Tests for the gap detection and reporting layer."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from feed.gaps import detect_gaps, generate_gap_report, is_fx_trading_hour


def _make_1m_ohlcv(
    start: str,
    periods: int,
    freq: str = "1min",
    drop_indices: list = None,
) -> pd.DataFrame:
    """Create a 1m OHLCV DataFrame, optionally dropping specific minute indices."""
    idx = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    df = pd.DataFrame(
        {
            "open": [1.09] * periods,
            "high": [1.095] * periods,
            "low": [1.085] * periods,
            "close": [1.092] * periods,
            "volume": [100.0] * periods,
        },
        index=idx,
    )
    if drop_indices:
        df = df.drop(df.index[drop_indices])
    return df


class TestIsFxTradingHour:
    """Tests for FX trading hour classification."""

    def test_monday_midday_is_trading(self):
        # 2025-01-13 is a Monday
        dt = datetime(2025, 1, 13, 12, 0, tzinfo=timezone.utc)
        assert is_fx_trading_hour(dt) is True

    def test_saturday_is_not_trading(self):
        # 2025-01-18 is a Saturday
        dt = datetime(2025, 1, 18, 12, 0, tzinfo=timezone.utc)
        assert is_fx_trading_hour(dt) is False

    def test_sunday_before_open_is_not_trading(self):
        # 2025-01-19 is a Sunday, 10:00 < 22:00
        dt = datetime(2025, 1, 19, 10, 0, tzinfo=timezone.utc)
        assert is_fx_trading_hour(dt) is False

    def test_sunday_at_open_is_trading(self):
        # 2025-01-19 is a Sunday, 22:00 is open
        dt = datetime(2025, 1, 19, 22, 0, tzinfo=timezone.utc)
        assert is_fx_trading_hour(dt) is True

    def test_friday_before_close_is_trading(self):
        # 2025-01-17 is a Friday, 21:00 < 22:00
        dt = datetime(2025, 1, 17, 21, 0, tzinfo=timezone.utc)
        assert is_fx_trading_hour(dt) is True

    def test_friday_at_close_is_not_trading(self):
        # 2025-01-17 is a Friday, 22:00 is closed
        dt = datetime(2025, 1, 17, 22, 0, tzinfo=timezone.utc)
        assert is_fx_trading_hour(dt) is False


class TestDetectGaps:
    """Tests for gap detection in canonical data."""

    def test_no_gaps_in_contiguous_data(self):
        """Contiguous 1m data has no gaps."""
        df = _make_1m_ohlcv("2025-01-13 09:00", 60)
        gaps = detect_gaps(df, "EURUSD")
        assert len(gaps) == 0

    def test_single_missing_minute(self):
        """One dropped minute produces one gap with 1 missing minute."""
        df = _make_1m_ohlcv("2025-01-13 09:00", 10, drop_indices=[5])
        gaps = detect_gaps(df, "EURUSD")

        assert len(gaps) == 1
        assert gaps[0]["missing_minutes"] == 1
        assert gaps[0]["classification"] == "trading_hours"

    def test_contiguous_gap(self):
        """Multiple consecutive missing minutes form a single gap."""
        df = _make_1m_ohlcv("2025-01-13 09:00", 10, drop_indices=[3, 4, 5])
        gaps = detect_gaps(df, "EURUSD")

        assert len(gaps) == 1
        assert gaps[0]["missing_minutes"] == 3

    def test_multiple_separate_gaps(self):
        """Non-adjacent missing minutes form separate gaps."""
        df = _make_1m_ohlcv("2025-01-13 09:00", 20, drop_indices=[3, 4, 10, 11, 12])
        gaps = detect_gaps(df, "EURUSD")

        assert len(gaps) == 2
        assert gaps[0]["missing_minutes"] == 2
        assert gaps[1]["missing_minutes"] == 3

    def test_weekend_gap_classified_correctly(self):
        """Gaps entirely outside FX trading hours are classified as weekend."""
        # Friday 21:00-21:59 (last trading hour) → Sunday 22:00-22:59 (first open)
        # Gap from Fri 22:00 to Sun 21:59 is entirely non-trading:
        #   Fri >=22:00 closed, Sat closed, Sun <22:00 closed.
        fri = pd.date_range("2025-01-17 21:00", periods=60, freq="1min", tz="UTC")
        sun = pd.date_range("2025-01-19 22:00", periods=60, freq="1min", tz="UTC")
        idx = fri.union(sun)

        df = pd.DataFrame(
            {
                "open": [1.09] * len(idx),
                "high": [1.095] * len(idx),
                "low": [1.085] * len(idx),
                "close": [1.092] * len(idx),
                "volume": [100.0] * len(idx),
            },
            index=idx,
        )

        gaps = detect_gaps(df, "EURUSD")

        weekend_gaps = [g for g in gaps if g["classification"] == "weekend"]
        assert len(weekend_gaps) >= 1

    def test_empty_dataframe_returns_no_gaps(self):
        gaps = detect_gaps(pd.DataFrame(), "EURUSD")
        assert gaps == []

    def test_gap_detection_is_idempotent(self):
        """Running gap detection twice produces identical results."""
        df = _make_1m_ohlcv("2025-01-13 09:00", 20, drop_indices=[5, 6, 15])
        gaps1 = detect_gaps(df, "EURUSD")
        gaps2 = detect_gaps(df, "EURUSD")
        assert gaps1 == gaps2


class TestGenerateGapReport:
    """Tests for the full gap report generation."""

    def test_report_structure(self):
        df = _make_1m_ohlcv("2025-01-13 09:00", 60, drop_indices=[10, 11])
        report = generate_gap_report("EURUSD", df)

        assert report["symbol"] == "EURUSD"
        assert "generated_utc" in report
        assert "canonical_range" in report
        assert "summary" in report
        assert "trading_hour_gaps" in report
        assert "weekend_gaps" in report
        assert report["summary"]["total_gaps"] > 0

    def test_report_with_no_gaps(self):
        df = _make_1m_ohlcv("2025-01-13 09:00", 60)
        report = generate_gap_report("EURUSD", df)

        assert report["summary"]["total_gaps"] == 0
        assert report["summary"]["trading_hour_missing_minutes"] == 0

    def test_report_empty_data(self):
        report = generate_gap_report("EURUSD", pd.DataFrame())
        assert "error" in report

    def test_report_is_idempotent(self):
        """Running report generation twice produces same gap data."""
        df = _make_1m_ohlcv("2025-01-13 09:00", 60, drop_indices=[10])
        r1 = generate_gap_report("EURUSD", df)
        r2 = generate_gap_report("EURUSD", df)

        # generated_utc may differ by a few ms, compare everything else
        assert r1["summary"] == r2["summary"]
        assert r1["trading_hour_gaps"] == r2["trading_hour_gaps"]
