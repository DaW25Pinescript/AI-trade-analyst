"""Tests for officer.loader — Group 1 acceptance criteria."""

import pytest

from market_data_officer.officer.loader import load_manifest, load_timeframe, load_all_timeframes


class TestManifest:
    """T1.1 — Manifest loads and parses correctly."""

    def test_manifest_loads(self, hot_packages_dir):
        manifest = load_manifest("EURUSD", hot_packages_dir)
        assert manifest["instrument"] == "EURUSD"
        assert "as_of_utc" in manifest
        assert "windows" in manifest
        assert "1m" in manifest["windows"]
        assert "1d" in manifest["windows"]

    def test_missing_manifest_raises(self, hot_packages_dir):
        """T1.4 — Missing manifest raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_manifest("FAKEINSTRUMENT", hot_packages_dir)


class TestTimeframeLoading:
    """T1.2 — All six timeframe DataFrames load with correct schema."""

    @pytest.mark.parametrize("tf", ["1m", "5m", "15m", "1h", "4h", "1d"])
    def test_timeframe_loads(self, hot_packages_dir, tf):
        df = load_timeframe("EURUSD", tf, hot_packages_dir)
        assert not df.empty, f"{tf} DataFrame is empty"
        assert set(df.columns) >= {"open", "high", "low", "close", "volume"}
        assert df.index.tzinfo is not None, f"{tf} index is not UTC-aware"
        assert df.index.is_monotonic_increasing, f"{tf} index is not monotonic"

    def test_load_all_timeframes(self, hot_packages_dir):
        tfs = load_all_timeframes("EURUSD", hot_packages_dir)
        assert len(tfs) == 6
        for tf_label in ["1m", "5m", "15m", "1h", "4h", "1d"]:
            assert tf_label in tfs

    def test_missing_csv_raises(self, hot_packages_dir):
        with pytest.raises(FileNotFoundError):
            load_timeframe("EURUSD", "99m", hot_packages_dir)


class TestNoRawParquet:
    """T1.3 — Loader does not read raw Parquet."""

    def test_no_read_parquet_in_loader(self):
        import inspect
        from market_data_officer.officer import loader

        source = inspect.getsource(loader)
        assert "read_parquet" not in source
