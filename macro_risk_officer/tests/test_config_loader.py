"""
Unit tests for macro_risk_officer.config.loader.

Verifies that:
  1. Both YAML files can be parsed and return dicts with expected top-level keys.
  2. Key numeric values match documented defaults (regression guard).
  3. The module-level cache works correctly.
  4. _clear_cache() resets the cache so a subsequent load re-reads the file.
"""

from __future__ import annotations

import pytest

from macro_risk_officer.config.loader import (
    _clear_cache,
    load_thresholds,
    load_weights,
)


@pytest.fixture(autouse=True)
def clear_loader_cache():
    """Ensure each test starts with a clean cache."""
    _clear_cache()
    yield
    _clear_cache()


class TestThresholdsYaml:
    def test_returns_dict(self):
        data = load_thresholds()
        assert isinstance(data, dict)

    def test_required_top_level_keys(self):
        data = load_thresholds()
        for key in ("regime", "volatility", "surprise", "decay", "scheduler"):
            assert key in data, f"Missing key: {key}"

    def test_regime_thresholds(self):
        reg = load_thresholds()["regime"]
        assert reg["risk_off_threshold"] == -0.25
        assert reg["risk_on_threshold"] == 0.25

    def test_volatility_thresholds(self):
        vol = load_thresholds()["volatility"]
        assert vol["expanding_threshold"] == 0.20
        assert vol["contracting_threshold"] == -0.20

    def test_surprise_cap(self):
        assert load_thresholds()["surprise"]["cap"] == 3.0

    def test_decay_half_lives(self):
        dec = load_thresholds()["decay"]
        assert dec["tier_1_half_life_hours"] == 168.0
        assert dec["tier_2_half_life_hours"] == 72.0
        assert dec["tier_3_half_life_hours"] == 24.0
        assert dec["min_floor"] == 0.05

    def test_scheduler_ttl(self):
        assert load_thresholds()["scheduler"]["ttl_seconds"] == 1800


class TestWeightsYaml:
    def test_returns_dict(self):
        data = load_weights()
        assert isinstance(data, dict)

    def test_required_top_level_keys(self):
        data = load_weights()
        for key in ("tier_weights", "regime_weights", "vol_weights", "confidence", "instrument_exposures"):
            assert key in data, f"Missing key: {key}"

    def test_tier_weights(self):
        tw = load_weights()["tier_weights"]
        assert tw["tier_1"] == 3.0
        assert tw["tier_2"] == 1.5
        assert tw["tier_3"] == 0.75

    def test_regime_weights(self):
        rw = load_weights()["regime_weights"]
        assert rw["spx_weight"] == 1.0
        assert rw["vix_weight"] == 0.5
        assert rw["gold_weight"] == 0.3

    def test_vol_weights(self):
        vw = load_weights()["vol_weights"]
        assert vw["vix_pressure"] == 0.7
        assert vw["conflict_magnitude"] == 0.3

    def test_confidence_scale(self):
        conf = load_weights()["confidence"]
        assert conf["scale_factor"] == 10.0
        assert conf["max"] == 0.95

    def test_instrument_exposures_present(self):
        exposures = load_weights()["instrument_exposures"]
        assert "XAUUSD" in exposures
        assert exposures["XAUUSD"]["GOLD"] == 1.0
        assert exposures["XAUUSD"]["USD"] == -0.5

    def test_all_standard_instruments_present(self):
        exposures = load_weights()["instrument_exposures"]
        for symbol in ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "US500", "NAS100", "USOIL"):
            assert symbol in exposures, f"Missing instrument: {symbol}"


class TestLoaderCache:
    def test_same_object_returned_on_second_call(self):
        """Module-level cache: second call returns the identical dict object."""
        first = load_thresholds()
        second = load_thresholds()
        assert first is second

    def test_clear_cache_forces_reload(self):
        first = load_thresholds()
        _clear_cache()
        second = load_thresholds()
        # Same content, but not the same cached object
        assert first == second
        assert first is not second
