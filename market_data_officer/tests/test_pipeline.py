"""Tests for pipeline selective derived regeneration."""

import pandas as pd
import pytest

from feed.pipeline import _find_resample_boundary


class TestFindResampleBoundary:
    """Tests for resample boundary calculation."""

    def test_5min_boundary(self):
        ts = pd.Timestamp("2025-01-15 14:23:00", tz="UTC")
        boundary = _find_resample_boundary(ts, "5min")
        assert boundary == pd.Timestamp("2025-01-15 14:20:00", tz="UTC")

    def test_5min_boundary_exact(self):
        ts = pd.Timestamp("2025-01-15 14:20:00", tz="UTC")
        boundary = _find_resample_boundary(ts, "5min")
        assert boundary == pd.Timestamp("2025-01-15 14:20:00", tz="UTC")

    def test_15min_boundary(self):
        ts = pd.Timestamp("2025-01-15 14:23:00", tz="UTC")
        boundary = _find_resample_boundary(ts, "15min")
        assert boundary == pd.Timestamp("2025-01-15 14:15:00", tz="UTC")

    def test_1h_boundary(self):
        ts = pd.Timestamp("2025-01-15 14:23:00", tz="UTC")
        boundary = _find_resample_boundary(ts, "1h")
        assert boundary == pd.Timestamp("2025-01-15 14:00:00", tz="UTC")

    def test_4h_boundary(self):
        ts = pd.Timestamp("2025-01-15 14:23:00", tz="UTC")
        boundary = _find_resample_boundary(ts, "4h")
        assert boundary == pd.Timestamp("2025-01-15 12:00:00", tz="UTC")

    def test_4h_boundary_at_zero(self):
        ts = pd.Timestamp("2025-01-15 03:15:00", tz="UTC")
        boundary = _find_resample_boundary(ts, "4h")
        assert boundary == pd.Timestamp("2025-01-15 00:00:00", tz="UTC")

    def test_1d_boundary(self):
        ts = pd.Timestamp("2025-01-15 14:23:00", tz="UTC")
        boundary = _find_resample_boundary(ts, "1D")
        assert boundary == pd.Timestamp("2025-01-15 00:00:00", tz="UTC")
