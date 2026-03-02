"""Unit tests for AssetSensitivityMatrix."""

import pytest

from macro_risk_officer.core.sensitivity_matrix import AssetSensitivityMatrix


class TestAssetSensitivityMatrix:
    def setup_method(self):
        self.matrix = AssetSensitivityMatrix()

    def test_hawkish_strengthens_usd(self):
        bias = self.matrix.get_base_bias("monetary_policy", "hawkish")
        assert bias["USD"] > 0

    def test_hawkish_pressures_equities(self):
        bias = self.matrix.get_base_bias("monetary_policy", "hawkish")
        assert bias["SPX"] < 0
        assert bias["NQ"] < 0

    def test_dovish_is_opposite_of_hawkish(self):
        hawkish = self.matrix.get_base_bias("monetary_policy", "hawkish")
        dovish = self.matrix.get_base_bias("monetary_policy", "dovish")
        assert hawkish["USD"] > 0
        assert dovish["USD"] < 0

    def test_geopolitical_escalation_bids_gold(self):
        bias = self.matrix.get_base_bias("geopolitical", "escalation")
        assert bias["GOLD"] > 0.5

    def test_systemic_stress_spikes_vix(self):
        bias = self.matrix.get_base_bias("systemic_risk", "stress")
        assert bias["VIX"] > 0.8

    def test_unknown_category_returns_empty(self):
        bias = self.matrix.get_base_bias("unknown", "direction")
        assert bias == {}

    def test_all_values_in_range(self):
        from macro_risk_officer.core.sensitivity_matrix import _MATRIX
        for (cat, direction), assets in _MATRIX.items():
            for asset, value in assets.items():
                assert -1.0 <= value <= 1.0, (
                    f"Out of range: {cat}/{direction}/{asset} = {value}"
                )

    def test_surprise_multiplier_scales_values(self):
        base = {"USD": 0.8, "SPX": -0.6}
        scaled = self.matrix.apply_surprise_multiplier(base, 1.5)
        assert scaled["USD"] == pytest.approx(1.2)
        assert scaled["SPX"] == pytest.approx(-0.9)
