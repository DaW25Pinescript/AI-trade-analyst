"""Tests for officer.quality — Group 2 acceptance criteria."""

import json
import os
from datetime import datetime, timezone, timedelta

import pytest

from market_data_officer.officer.quality import check_package_quality


class TestValidPackage:
    """T2.1 — Valid package passes all quality checks."""

    def test_valid_package_passes(self, hot_packages_dir):
        result = check_package_quality("EURUSD", hot_packages_dir)
        assert result.manifest_valid is True
        assert result.all_timeframes_present is True
        assert result.partial is False
        # No flags except potentially staleness (synthetic data may be "stale"
        # depending on generation time vs test run time)
        non_stale_flags = [f for f in result.flags if f != "stale"]
        assert non_stale_flags == []


class TestStalePackage:
    """T2.2 — Stale package is flagged, not crashed."""

    def test_stale_package_flagged(self, stale_packages_dir):
        result = check_package_quality("EURUSD", stale_packages_dir)
        assert result.stale is True
        assert result.staleness_minutes > 60


class TestPartialPackage:
    """T2.3 — Partial package degrades gracefully."""

    def test_partial_package(self, hot_packages_dir):
        # Rename the 4h CSV to simulate missing timeframe
        csv_path = hot_packages_dir / "EURUSD_4h_latest.csv"
        csv_path.rename(hot_packages_dir / "EURUSD_4h_latest.csv.bak")

        result = check_package_quality("EURUSD", hot_packages_dir)
        assert result.partial is True
        assert any("4h" in f for f in result.flags)

        # Restore for other tests
        (hot_packages_dir / "EURUSD_4h_latest.csv.bak").rename(csv_path)


class TestMissingManifest:
    """Missing manifest raises FileNotFoundError."""

    def test_missing_manifest_raises(self, hot_packages_dir):
        with pytest.raises(FileNotFoundError):
            check_package_quality("FAKEINSTRUMENT", hot_packages_dir)
