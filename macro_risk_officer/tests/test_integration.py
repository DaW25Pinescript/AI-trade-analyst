"""
Integration tests — full pipeline, no external API calls.

Tests the complete path from raw MacroEvents → ReasoningEngine →
MacroContext → arbiter_block() string → CLI output format.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from macro_risk_officer.core.models import MacroEvent, MacroContext
from macro_risk_officer.core.reasoning_engine import ReasoningEngine
from macro_risk_officer.ingestion.normalizer import normalise_events


# ── Shared fixtures ────────────────────────────────────────────────────────────

def _make_event(
    event_id: str,
    category: str,
    tier: int,
    actual: float,
    forecast: float,
    description: str = "Test event",
    source: str = "test",
) -> MacroEvent:
    return MacroEvent(
        event_id=event_id,
        category=category,
        tier=tier,
        timestamp=datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc),
        actual=actual,
        forecast=forecast,
        previous=forecast,
        description=description,
        source=source,
    )


HAWKISH_FED = _make_event(
    "fed-hawkish-integration",
    "monetary_policy", 1, 5.5, 5.25,
    "Fed rate decision 5.5% vs 5.25% expected",
)
HOT_CPI = _make_event(
    "cpi-hot-integration",
    "inflation", 1, 3.8, 3.2,
    "CPI YoY 3.8% vs 3.2% expected",
)
WEAK_NFP = _make_event(
    "nfp-weak-integration",
    "employment", 1, 120_000, 200_000,
    "Nonfarm payrolls 120k vs 200k expected",
)
GEO_ESCALATION = _make_event(
    "geo-escalation-integration",
    "geopolitical", 2, 1.0, 0.0,
    "Geopolitical escalation event",
)


# ── Pipeline integration ───────────────────────────────────────────────────────

class TestFullPipeline:
    """End-to-end: events → normaliser → engine → MacroContext → arbiter block."""

    def _run(self, events, exposures=None):
        normalised = normalise_events(events)
        engine = ReasoningEngine()
        return engine.generate_context(normalised, exposures or {})

    def test_mixed_hawkish_hot_cpi_is_risk_off(self):
        ctx = self._run([HAWKISH_FED, HOT_CPI])
        assert ctx.regime in ("risk_off", "neutral")
        assert ctx.asset_pressure.USD > 0
        assert ctx.asset_pressure.SPX < 0

    def test_weak_nfp_alone_applies_employment_pressure(self):
        ctx = self._run([WEAK_NFP])
        assert ctx.asset_pressure.USD < 0  # weak employment → USD pressure

    def test_geopolitical_escalation_bids_gold(self):
        ctx = self._run([GEO_ESCALATION])
        assert ctx.asset_pressure.GOLD > 0

    def test_conflict_score_negative_for_long_gold_in_risk_off(self):
        ctx = self._run([HAWKISH_FED], exposures={"GOLD": 1.0, "USD": -0.5})
        # Hawkish → GOLD pressured → long GOLD conflicts with macro
        assert ctx.conflict_score < 0

    def test_conflict_score_positive_for_aligned_exposure(self):
        ctx = self._run([HAWKISH_FED], exposures={"USD": 1.0, "SPX": -0.5})
        # Hawkish → USD up, SPX down → short SPX + long USD aligns
        assert ctx.conflict_score > 0

    def test_arbiter_block_is_complete_string(self):
        ctx = self._run([HAWKISH_FED])
        block = ctx.arbiter_block()
        assert "MACRO RISK CONTEXT" in block
        assert "advisory only" in block
        assert "Regime" in block
        assert "conflict" in block.lower()
        assert "Explanation" in block

    def test_normaliser_deduplicates(self):
        duplicate_events = [HAWKISH_FED, HAWKISH_FED, HOT_CPI]
        normalised = normalise_events(duplicate_events)
        ids = [e.event_id for e in normalised]
        assert len(ids) == len(set(ids))

    def test_all_events_produce_valid_context(self):
        all_events = [HAWKISH_FED, HOT_CPI, WEAK_NFP, GEO_ESCALATION]
        ctx = self._run(all_events)
        # Pydantic validation already enforces constraints, but check key fields
        assert ctx.confidence > 0
        assert ctx.time_horizon_days == 45  # Tier-1 events present
        assert len(ctx.explanation) > 0
        assert len(ctx.active_event_ids) == 4


# ── CLI integration ────────────────────────────────────────────────────────────

class TestCLI:
    """Test the CLI entry point with mocked scheduler (in-process, no subprocess)."""

    def _mock_context(self) -> MacroContext:
        from macro_risk_officer.core.models import AssetPressure
        return MacroContext(
            regime="risk_off",
            vol_bias="expanding",
            asset_pressure=AssetPressure(USD=0.7, GOLD=0.5, SPX=-0.6),
            conflict_score=-0.55,
            confidence=0.80,
            time_horizon_days=45,
            explanation=["Tier-1 hawkish Fed surprise → USD supported, equities pressured"],
            active_event_ids=["fed-hawkish-integration"],
        )

    def test_status_text_output_contains_regime(self, capsys):
        from macro_risk_officer.main import cmd_status
        with patch(
            "macro_risk_officer.main.MacroScheduler.get_context",
            return_value=self._mock_context(),
        ):
            cmd_status(instrument="XAUUSD", as_json=False)
        captured = capsys.readouterr()
        assert "risk_off" in captured.out
        assert "expanding" in captured.out

    def test_status_json_flag_produces_valid_json(self, capsys):
        from macro_risk_officer.main import cmd_status
        with patch(
            "macro_risk_officer.main.MacroScheduler.get_context",
            return_value=self._mock_context(),
        ):
            cmd_status(instrument="XAUUSD", as_json=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["regime"] == "risk_off"
        assert data["vol_bias"] == "expanding"
        assert "conflict_score" in data
        assert "asset_pressure" in data
        assert "explanation" in data

    def test_status_no_context_raises_system_exit(self, capsys):
        from macro_risk_officer.main import cmd_status
        with patch(
            "macro_risk_officer.main.MacroScheduler.get_context",
            return_value=None,
        ):
            with pytest.raises(SystemExit) as exc:
                cmd_status(instrument="XAUUSD", as_json=False)
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "ERROR" in captured.out

    def test_audit_command_prints_stub_message(self, capsys):
        from macro_risk_officer.main import cmd_audit
        cmd_audit()
        captured = capsys.readouterr()
        assert "MRO-P3" in captured.out

    def test_module_entry_point_exists(self):
        """Verify python -m macro_risk_officer --help exits without ImportError."""
        result = subprocess.run(
            [sys.executable, "-m", "macro_risk_officer", "--help"],
            capture_output=True,
            text=True,
        )
        # argparse exits 0 for --help
        assert result.returncode == 0
        assert "status" in result.stdout
        assert "audit" in result.stdout


# ── FRED client unit tests (no API calls) ─────────────────────────────────────

class TestFredToMacroEvents:
    """Test FRED → MacroEvent conversion with mocked fetch."""

    def test_snapshot_converts_to_events(self):
        from macro_risk_officer.ingestion.clients.fred_client import FredClient
        client = FredClient.__new__(FredClient)
        client.api_key = "dummy"

        mock_snapshot = {
            "DFF": (5.33, 5.25),
            "CPIAUCSL": (315.2, 312.0),
            "T10Y2Y": (-0.3, -0.1),
            "UNRATE": (4.1, 4.0),
            "DCOILWTICO": (78.5, 75.0),
        }
        with patch.object(client, "fetch_macro_snapshot", return_value=mock_snapshot):
            events = client.to_macro_events()

        assert len(events) == 5
        ids = {e.event_id for e in events}
        assert any("DFF" in eid for eid in ids)

    def test_dff_rising_means_positive_surprise(self):
        from macro_risk_officer.ingestion.clients.fred_client import FredClient
        client = FredClient.__new__(FredClient)
        client.api_key = "dummy"

        with patch.object(client, "fetch_macro_snapshot", return_value={
            "DFF": (5.5, 5.25),
            "CPIAUCSL": None,
            "T10Y2Y": None,
            "UNRATE": None,
            "DCOILWTICO": None,
        }):
            events = client.to_macro_events()

        dff_event = next(e for e in events if "DFF" in e.event_id)
        assert dff_event.surprise is not None
        assert dff_event.surprise > 0  # rising rate = hawkish surprise

    def test_none_snapshots_are_skipped(self):
        from macro_risk_officer.ingestion.clients.fred_client import FredClient
        client = FredClient.__new__(FredClient)
        client.api_key = "dummy"

        with patch.object(client, "fetch_macro_snapshot", return_value={
            "DFF": None,
            "CPIAUCSL": None,
            "T10Y2Y": (0.1, 0.2),
            "UNRATE": None,
            "DCOILWTICO": None,
        }):
            events = client.to_macro_events()

        assert len(events) == 1
        assert "T10Y2Y" in events[0].event_id
