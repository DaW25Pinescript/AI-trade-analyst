"""Tests for the AutoTune runner."""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from autotune.run import (
    apply_acceptance_policy,
    validate_proposal,
)


class TestAcceptancePolicy:
    """Test the three acceptance conditions."""

    def _base_metrics(self):
        return {
            "accuracy": 0.55,
            "resolve_rate": 0.85,
            "resolved_calls": 1000,
            "total_calls": 1200,
        }

    def test_accepted_when_all_conditions_met(self):
        baseline = self._base_metrics()
        candidate = {**baseline, "accuracy": 0.56, "resolve_rate": 0.85, "resolved_calls": 1000}
        accepted, reasons = apply_acceptance_policy(baseline, candidate)
        assert accepted is True
        assert reasons == []

    def test_rejected_on_accuracy_tie(self):
        """Tie in accuracy → rejection."""
        baseline = self._base_metrics()
        candidate = {**baseline}
        accepted, reasons = apply_acceptance_policy(baseline, candidate)
        assert accepted is False
        assert any("accuracy" in r for r in reasons)

    def test_rejected_on_accuracy_decrease(self):
        baseline = self._base_metrics()
        candidate = {**baseline, "accuracy": 0.54}
        accepted, reasons = apply_acceptance_policy(baseline, candidate)
        assert accepted is False

    def test_rejected_on_low_resolve_rate(self):
        """Resolve rate below 0.70 → rejected."""
        baseline = self._base_metrics()
        candidate = {**baseline, "accuracy": 0.60, "resolve_rate": 0.65, "resolved_calls": 1000}
        accepted, reasons = apply_acceptance_policy(baseline, candidate)
        assert accepted is False
        assert any("resolve_rate" in r for r in reasons)

    def test_rejected_on_low_resolved_calls(self):
        """Resolved calls < 80% of baseline → rejected."""
        baseline = self._base_metrics()
        candidate = {**baseline, "accuracy": 0.60, "resolve_rate": 0.85, "resolved_calls": 700}
        accepted, reasons = apply_acceptance_policy(baseline, candidate)
        assert accepted is False
        assert any("resolved_calls" in r for r in reasons)

    def test_multiple_rejection_reasons(self):
        """Multiple conditions can fail simultaneously."""
        baseline = self._base_metrics()
        candidate = {
            "accuracy": 0.50,  # worse
            "resolve_rate": 0.60,  # below 0.70
            "resolved_calls": 500,  # below 80%
            "total_calls": 800,
        }
        accepted, reasons = apply_acceptance_policy(baseline, candidate)
        assert accepted is False
        assert len(reasons) == 3

    def test_tiny_accuracy_improvement_accepted(self):
        """Even a 0.0001 improvement counts as strict improvement."""
        baseline = self._base_metrics()
        candidate = {**baseline, "accuracy": 0.5501, "resolve_rate": 0.85, "resolved_calls": 1000}
        accepted, reasons = apply_acceptance_policy(baseline, candidate)
        assert accepted is True


class TestValidateProposal:
    """Test parameter validation."""

    def _manifest(self):
        return {
            "meta": {"version": "v1.0"},
            "structure_short": {
                "instance_id": "structure_short",
                "parameters": {
                    "lookback_bars": {
                        "current": 60,
                        "min": 40,
                        "max": 100,
                        "step": 5,
                        "mutable": True,
                    },
                    "pivot_window": {
                        "current": 3,
                        "min": 2,
                        "max": 6,
                        "step": 1,
                        "mutable": True,
                    },
                },
            },
        }

    def test_valid_proposal(self):
        m = self._manifest()
        result = validate_proposal(m, "structure_short", "lookback_bars", 55)
        assert result == 55

    def test_out_of_bounds_high(self):
        m = self._manifest()
        with pytest.raises(ValueError, match="outside bounds"):
            validate_proposal(m, "structure_short", "lookback_bars", 999)

    def test_out_of_bounds_low(self):
        m = self._manifest()
        with pytest.raises(ValueError, match="outside bounds"):
            validate_proposal(m, "structure_short", "lookback_bars", 10)

    def test_off_step_grid(self):
        m = self._manifest()
        with pytest.raises(ValueError, match="step grid"):
            validate_proposal(m, "structure_short", "lookback_bars", 57)

    def test_unknown_parameter(self):
        m = self._manifest()
        with pytest.raises(ValueError, match="not found"):
            validate_proposal(m, "structure_short", "fake_param", 5)

    def test_unknown_instance(self):
        m = self._manifest()
        with pytest.raises(ValueError, match="not in manifest"):
            validate_proposal(m, "fake_instance", "lookback_bars", 55)

    def test_boundary_values_accepted(self):
        m = self._manifest()
        assert validate_proposal(m, "structure_short", "lookback_bars", 40) == 40
        assert validate_proposal(m, "structure_short", "lookback_bars", 100) == 100

    def test_pivot_window_valid(self):
        m = self._manifest()
        assert validate_proposal(m, "structure_short", "pivot_window", 4) == 4
