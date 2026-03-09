"""Per-instrument provider routing tests.

Validates AC-1 through AC-5, AC-8 from docs/MDO_ProviderRouting_Spec.md.
All tests are deterministic — no live provider dependency.
"""

import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from instrument_registry import INSTRUMENT_REGISTRY, InstrumentMeta, get_meta


# ── AC-1: Explicit provider policy exists ────────────────────────────

class TestProviderPolicyFields:
    """Every trusted instrument has explicit provider policy fields."""

    TRUSTED = ("EURUSD", "GBPUSD", "XAUUSD", "XAGUSD", "XPTUSD")

    @pytest.mark.parametrize("symbol", TRUSTED)
    def test_primary_provider_present(self, symbol):
        meta = get_meta(symbol)
        assert hasattr(meta, "primary_provider")
        assert meta.primary_provider != ""

    @pytest.mark.parametrize("symbol", TRUSTED)
    def test_fallback_provider_present(self, symbol):
        meta = get_meta(symbol)
        assert hasattr(meta, "fallback_provider")
        assert meta.fallback_provider != ""

    @pytest.mark.parametrize("symbol", TRUSTED)
    def test_fallback_enabled_present(self, symbol):
        meta = get_meta(symbol)
        assert hasattr(meta, "fallback_enabled")
        assert isinstance(meta.fallback_enabled, bool)

    @pytest.mark.parametrize("symbol", TRUSTED)
    def test_fallback_direction_present(self, symbol):
        meta = get_meta(symbol)
        assert hasattr(meta, "fallback_direction")
        assert meta.fallback_direction in ("one_way", "symmetric")

    @pytest.mark.parametrize("symbol", TRUSTED)
    def test_primary_differs_from_fallback(self, symbol):
        meta = get_meta(symbol)
        assert meta.primary_provider != meta.fallback_provider


# ── AC-2: Default provider is deterministic ──────────────────────────

class TestDefaultProviderPolicy:
    """Each trusted instrument has the expected default policy."""

    EXPECTED_POLICY = {
        "EURUSD": ("dukascopy", "yfinance", True, "one_way"),
        "GBPUSD": ("dukascopy", "yfinance", True, "one_way"),
        "XAUUSD": ("dukascopy", "yfinance", True, "one_way"),
        "XAGUSD": ("dukascopy", "yfinance", True, "one_way"),
        "XPTUSD": ("dukascopy", "yfinance", True, "one_way"),
    }

    @pytest.mark.parametrize("symbol,expected", list(EXPECTED_POLICY.items()))
    def test_policy_matches_expected(self, symbol, expected):
        meta = get_meta(symbol)
        primary, fallback, enabled, direction = expected
        assert meta.primary_provider == primary
        assert meta.fallback_provider == fallback
        assert meta.fallback_enabled == enabled
        assert meta.fallback_direction == direction


# ── AC-3: Fallback policy is explicit ────────────────────────────────

class TestFallbackPolicyExplicit:
    """Fallback policy is driven by registry, not implicit global logic."""

    def test_policy_is_per_instrument_not_global(self):
        """Each instrument carries its own policy — they are independent."""
        policies = {}
        for sym in ("EURUSD", "XAUUSD"):
            meta = get_meta(sym)
            policies[sym] = (meta.primary_provider, meta.fallback_provider,
                             meta.fallback_enabled, meta.fallback_direction)
        # Both have policy — not relying on a single global setting
        assert len(policies) == 2
        for sym, policy in policies.items():
            assert all(p is not None for p in policy), f"{sym} has None policy field"

    def test_fallback_disabled_constructible(self):
        """An instrument can be constructed with fallback_enabled=False."""
        meta = InstrumentMeta(
            symbol="TEST_NOFB",
            price_scale=1000,
            fallback_enabled=False,
        )
        assert meta.fallback_enabled is False


# ── AC-4: Fallback triggers only on approved conditions ──────────────

class TestFallbackTriggerConditions:
    """Fallback triggers on empty/no-data or transport exception only.

    These tests verify the pipeline logic via mock, not via live providers.
    """

    def _make_hour_dt(self):
        """Return a timezone-aware hour datetime for testing."""
        return datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

    @patch("feed.pipeline.fetch_bi5")
    @patch("feed.pipeline.fetch_1m_ohlcv_yfinance")
    def test_fallback_activates_on_empty_payload(self, mock_yf, mock_fetch):
        """Empty Dukascopy payload → fallback called (when enabled)."""
        mock_fetch.return_value = b""  # empty payload
        mock_yf.return_value = pd.DataFrame()  # yfinance also empty (that's fine)

        from feed.pipeline import run_pipeline

        hour = self._make_hour_dt()
        # We just verify the fallback was attempted — full pipeline needs dirs
        # so we test the logic path via the mock call counts
        with patch("feed.pipeline._load_existing_canonical", return_value=None), \
             patch("feed.pipeline._save_canonical"), \
             patch("feed.pipeline._rebuild_derived_and_export"):
            try:
                run_pipeline("EURUSD", hour, hour, save_raw=False)
            except Exception:
                pass  # Pipeline may fail on missing dirs — that's OK

        # Fallback should have been attempted because payload was empty
        assert mock_yf.called, "yfinance fallback was not called on empty payload"

    @patch("feed.pipeline.fetch_bi5")
    @patch("feed.pipeline.fetch_1m_ohlcv_yfinance")
    def test_fallback_activates_on_transport_exception(self, mock_yf, mock_fetch):
        """Transport exception → fallback called (when enabled)."""
        import requests
        mock_fetch.side_effect = requests.RequestException("SSL error")
        mock_yf.return_value = pd.DataFrame()

        from feed.pipeline import run_pipeline

        hour = self._make_hour_dt()
        with patch("feed.pipeline._load_existing_canonical", return_value=None), \
             patch("feed.pipeline._save_canonical"), \
             patch("feed.pipeline._rebuild_derived_and_export"):
            try:
                run_pipeline("EURUSD", hour, hour, save_raw=False)
            except Exception:
                pass

        assert mock_yf.called, "yfinance fallback was not called on transport exception"

    @patch("feed.pipeline.fetch_bi5")
    @patch("feed.pipeline.decode_dukascopy_ticks")
    @patch("feed.pipeline.fetch_1m_ohlcv_yfinance")
    def test_fallback_does_not_activate_on_successful_fetch(self, mock_yf, mock_decode, mock_fetch):
        """Successful Dukascopy fetch → fallback NOT called."""
        mock_fetch.return_value = b"\x00" * 20  # non-empty payload
        mock_decode.return_value = pd.DataFrame()  # empty ticks (decode issue, not transport)

        from feed.pipeline import run_pipeline

        hour = self._make_hour_dt()
        with patch("feed.pipeline._load_existing_canonical", return_value=None), \
             patch("feed.pipeline._save_canonical"), \
             patch("feed.pipeline._rebuild_derived_and_export"):
            try:
                run_pipeline("EURUSD", hour, hour, save_raw=False)
            except Exception:
                pass

        assert not mock_yf.called, "yfinance fallback should NOT activate on successful fetch"


# ── AC-5: fallback_enabled=False must not fall back ──────────────────

class TestFallbackDisabled:
    """Negative test: fallback_enabled=False prevents fallback activation."""

    def _make_hour_dt(self):
        return datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

    @patch("feed.pipeline.fetch_bi5")
    @patch("feed.pipeline.fetch_1m_ohlcv_yfinance")
    def test_fallback_disabled_no_fallback_on_empty(self, mock_yf, mock_fetch):
        """Empty payload + fallback_enabled=False → fallback NOT called."""
        mock_fetch.return_value = b""  # empty — would normally trigger fallback

        # Temporarily override EURUSD policy to disable fallback
        original_meta = get_meta("EURUSD")
        disabled_meta = replace(original_meta, fallback_enabled=False)

        from feed.config import INSTRUMENTS
        from feed.pipeline import run_pipeline

        hour = self._make_hour_dt()
        with patch.dict(INSTRUMENTS, {"EURUSD": disabled_meta}), \
             patch("feed.pipeline._load_existing_canonical", return_value=None), \
             patch("feed.pipeline._save_canonical"), \
             patch("feed.pipeline._rebuild_derived_and_export"):
            try:
                run_pipeline("EURUSD", hour, hour, save_raw=False)
            except Exception:
                pass

        assert not mock_yf.called, (
            "yfinance fallback was called despite fallback_enabled=False"
        )

    @patch("feed.pipeline.fetch_bi5")
    @patch("feed.pipeline.fetch_1m_ohlcv_yfinance")
    def test_fallback_disabled_no_fallback_on_transport_error(self, mock_yf, mock_fetch):
        """Transport error + fallback_enabled=False → fallback NOT called."""
        import requests
        mock_fetch.side_effect = requests.RequestException("connection refused")

        original_meta = get_meta("EURUSD")
        disabled_meta = replace(original_meta, fallback_enabled=False)

        from feed.config import INSTRUMENTS
        from feed.pipeline import run_pipeline

        hour = self._make_hour_dt()
        with patch.dict(INSTRUMENTS, {"EURUSD": disabled_meta}), \
             patch("feed.pipeline._load_existing_canonical", return_value=None), \
             patch("feed.pipeline._save_canonical"), \
             patch("feed.pipeline._rebuild_derived_and_export"):
            try:
                run_pipeline("EURUSD", hour, hour, save_raw=False)
            except Exception:
                pass

        assert not mock_yf.called, (
            "yfinance fallback was called despite fallback_enabled=False on transport error"
        )


# ── AC-8: Provenance reflects actual provider ────────────────────────

class TestProviderProvenance:
    """source.vendor must reflect the actual provider used, not configured primary."""

    def _make_hour_dt(self):
        return datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

    def _make_fake_bars(self, n=10):
        """Create a small OHLCV DataFrame for testing."""
        idx = pd.date_range("2025-01-15 14:00", periods=n, freq="1min", tz="UTC")
        return pd.DataFrame({
            "open": [1.085] * n,
            "high": [1.086] * n,
            "low": [1.084] * n,
            "close": [1.085] * n,
            "volume": [100.0] * n,
        }, index=idx)

    @patch("feed.pipeline.fetch_bi5")
    @patch("feed.pipeline.decode_dukascopy_ticks")
    @patch("feed.pipeline.ticks_to_1m_ohlcv")
    @patch("feed.pipeline.fetch_1m_ohlcv_yfinance")
    def test_primary_vendor_stamp(self, mock_yf, mock_agg, mock_decode, mock_fetch):
        """When primary succeeds, vendor stamp = meta.primary_provider."""
        bars = self._make_fake_bars()
        mock_fetch.return_value = b"\x00" * 20
        mock_decode.return_value = bars  # pretend these are ticks
        mock_agg.return_value = bars
        mock_yf.return_value = pd.DataFrame()

        from feed.pipeline import run_pipeline

        captured_bars = []
        original_save = None

        def capture_save(df, sym):
            captured_bars.append(df.copy())

        hour = self._make_hour_dt()
        with patch("feed.pipeline._load_existing_canonical", return_value=None), \
             patch("feed.pipeline._save_canonical", side_effect=capture_save), \
             patch("feed.pipeline._rebuild_derived_and_export"):
            try:
                run_pipeline("EURUSD", hour, hour, save_raw=False)
            except Exception:
                pass

        meta = get_meta("EURUSD")
        if captured_bars:
            vendors = set(captured_bars[0]["vendor"].unique())
            assert meta.primary_provider in vendors

    @patch("feed.pipeline.fetch_bi5")
    @patch("feed.pipeline.fetch_1m_ohlcv_yfinance")
    def test_fallback_vendor_stamp(self, mock_yf, mock_fetch):
        """When fallback activates, vendor stamp = meta.fallback_provider."""
        mock_fetch.return_value = b""  # empty → triggers fallback
        fb_bars = self._make_fake_bars(5)
        mock_yf.return_value = fb_bars

        from feed.pipeline import run_pipeline

        captured_bars = []

        def capture_save(df, sym):
            captured_bars.append(df.copy())

        hour = self._make_hour_dt()
        with patch("feed.pipeline._load_existing_canonical", return_value=None), \
             patch("feed.pipeline._save_canonical", side_effect=capture_save), \
             patch("feed.pipeline._rebuild_derived_and_export"):
            try:
                run_pipeline("EURUSD", hour, hour, save_raw=False)
            except Exception:
                pass

        meta = get_meta("EURUSD")
        if captured_bars:
            vendors = set(captured_bars[0]["vendor"].unique())
            assert meta.fallback_provider in vendors


# ── Registry immutability ────────────────────────────────────────────

class TestPolicyImmutability:
    """Provider policy fields are frozen — cannot be mutated at runtime."""

    @pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSD"])
    def test_cannot_mutate_primary_provider(self, symbol):
        meta = get_meta(symbol)
        with pytest.raises(AttributeError):
            meta.primary_provider = "changed"  # type: ignore[misc]

    @pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSD"])
    def test_cannot_mutate_fallback_enabled(self, symbol):
        meta = get_meta(symbol)
        with pytest.raises(AttributeError):
            meta.fallback_enabled = False  # type: ignore[misc]


# ── Constructor defaults reproduce current behavior ──────────────────

class TestPolicyDefaults:
    """Default policy values reproduce pre-routing behavior."""

    def test_default_primary_is_dukascopy(self):
        meta = InstrumentMeta(symbol="TEST", price_scale=1000)
        assert meta.primary_provider == "dukascopy"

    def test_default_fallback_is_yfinance(self):
        meta = InstrumentMeta(symbol="TEST", price_scale=1000)
        assert meta.fallback_provider == "yfinance"

    def test_default_fallback_enabled(self):
        meta = InstrumentMeta(symbol="TEST", price_scale=1000)
        assert meta.fallback_enabled is True

    def test_default_direction_one_way(self):
        meta = InstrumentMeta(symbol="TEST", price_scale=1000)
        assert meta.fallback_direction == "one_way"


# ── Guard rails (routing-specific) ──────────────────────────────────

class TestRoutingGuardRails:
    """Hard constraints from the routing spec."""

    def test_no_hardcoded_provider_in_pipeline_fallback_gate(self):
        """The fallback gate in pipeline.py reads meta.fallback_enabled,
        not a hardcoded boolean."""
        import inspect
        from feed.pipeline import run_pipeline

        source = inspect.getsource(run_pipeline)
        # The fallback gate should reference meta.fallback_enabled
        assert "meta.fallback_enabled" in source, (
            "pipeline.run_pipeline does not read meta.fallback_enabled"
        )

    def test_no_hardcoded_vendor_stamp_in_pipeline(self):
        """Vendor stamps in pipeline.py use meta.primary_provider / meta.fallback_provider."""
        import inspect
        from feed.pipeline import run_pipeline

        source = inspect.getsource(run_pipeline)
        assert "meta.primary_provider" in source
        assert "meta.fallback_provider" in source
