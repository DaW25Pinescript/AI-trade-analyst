"""TD-11 / AC-11 / AC-12 — Import-path stability tests.

Proves that the supported import model is load-bearing:
  - All four packages import successfully via packaging
  - Cross-package imports resolve correctly
  - MDO submodules import via fully-qualified paths
  - No sys.path.insert calls remain in non-test Python source
  - Packaging is load-bearing (negative test: import fails without install)
"""

import importlib
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── AC-11: Package import tests ──────────────────────────────────────


class TestPackageImports:
    """Prove all four packages import cleanly via packaging."""

    def test_import_ai_analyst(self):
        mod = importlib.import_module("ai_analyst")
        assert hasattr(mod, "__file__")

    def test_import_analyst(self):
        mod = importlib.import_module("analyst")
        assert hasattr(mod, "__file__")

    def test_import_market_data_officer(self):
        mod = importlib.import_module("market_data_officer")
        assert hasattr(mod, "__file__")

    def test_import_macro_risk_officer(self):
        mod = importlib.import_module("macro_risk_officer")
        assert hasattr(mod, "__file__")


class TestCrossPackageImports:
    """Prove cross-package imports resolve correctly."""

    def test_analyst_imports_mdo_contracts(self):
        """analyst → market_data_officer.officer.contracts (MarketPacketV2)."""
        from market_data_officer.officer.contracts import MarketPacketV2
        assert MarketPacketV2 is not None

    def test_analyst_pre_filter_imports_mdo(self):
        """analyst.pre_filter → market_data_officer.officer.contracts."""
        from analyst.pre_filter import compute_digest
        assert callable(compute_digest)

    def test_ai_analyst_imports_mro_models(self):
        """ai_analyst → macro_risk_officer.core.models (MacroContext)."""
        from macro_risk_officer.core.models import MacroContext
        assert MacroContext is not None

    def test_ai_analyst_graph_state_imports_mro(self):
        """ai_analyst.graph.state → macro_risk_officer.core.models."""
        from ai_analyst.graph.state import GraphState
        assert GraphState is not None


class TestMDOQualifiedImports:
    """Prove MDO submodules import via fully-qualified paths."""

    def test_mdo_officer_contracts(self):
        from market_data_officer.officer.contracts import MarketPacketV2
        assert MarketPacketV2 is not None

    def test_mdo_officer_service(self):
        from market_data_officer.officer.service import build_market_packet
        assert callable(build_market_packet)

    def test_mdo_structure_config(self):
        from market_data_officer.structure.config import StructureConfig
        assert StructureConfig is not None

    def test_mdo_instrument_registry(self):
        from market_data_officer.instrument_registry import INSTRUMENT_REGISTRY
        assert isinstance(INSTRUMENT_REGISTRY, dict)

    def test_mdo_scheduler(self):
        from market_data_officer.scheduler import build_scheduler
        assert callable(build_scheduler)

    def test_mdo_runtime_config(self):
        from market_data_officer.runtime_config import RuntimeConfig
        assert RuntimeConfig is not None


class TestNoSysPathInsert:
    """Grep-based lint: no sys.path.insert calls in non-test Python source."""

    def test_no_sys_path_insert_in_source(self):
        """No sys.path.insert or sys.path.append in non-test .py files."""
        violations = []
        for py_file in REPO_ROOT.rglob("*.py"):
            # Skip test files, docs, examples, .venv, __pycache__
            rel = py_file.relative_to(REPO_ROOT)
            parts = rel.parts
            if any(p in ("tests", ".venv", "__pycache__", "docs", "examples", "node_modules") for p in parts):
                continue
            if py_file.name.startswith("test_"):
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            for i, line in enumerate(source.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "sys.path.insert" in stripped or "sys.path.append" in stripped:
                    violations.append(f"{rel}:{i}: {stripped}")

        assert violations == [], (
            f"Found sys.path.insert/append in non-test source:\n"
            + "\n".join(violations)
        )


# ── AC-12: Negative test — packaging is load-bearing ─────────────────


class TestPackagingIsLoadBearing:
    """Prove that importing without editable install fails."""

    def test_import_fails_without_install(self):
        """Without site-packages (no editable install), import ai_analyst fails.

        Uses ``python -S`` (skip site-packages) to simulate an environment
        where ``pip install -e .`` has not been run.  This proves the editable
        install is load-bearing — imports succeed *because* of packaging, not
        because of accidental cwd or sys.path state.
        """
        result = subprocess.run(
            [sys.executable, "-S", "-c", "import ai_analyst"],
            capture_output=True,
            text=True,
            cwd="/tmp",  # Not the repo root
        )
        assert result.returncode != 0, (
            "ai_analyst imported without site-packages — "
            "packaging is decorative, not load-bearing.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
