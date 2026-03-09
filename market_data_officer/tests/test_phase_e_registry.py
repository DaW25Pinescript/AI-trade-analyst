"""Phase E+ tests — instrument registry shape, consumer derivation, and extension ergonomics.

Validates AC-1 through AC-10 from docs/MDO_PhaseE_Spec.md.
"""

import sys
from pathlib import Path

import pytest

# Ensure package root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from instrument_registry import INSTRUMENT_REGISTRY, InstrumentMeta, get_meta


# ── AC-1: Centralised instrument metadata ────────────────────────────

class TestRegistryShape:
    """Every registered instrument must carry the full metadata contract."""

    REQUIRED_SYMBOLS = {"EURUSD", "XAUUSD", "GBPUSD", "XAGUSD", "XPTUSD"}

    def test_all_target_instruments_present(self):
        assert self.REQUIRED_SYMBOLS <= set(INSTRUMENT_REGISTRY.keys())

    @pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSD", "GBPUSD", "XAGUSD", "XPTUSD"])
    def test_meta_has_required_fields(self, symbol):
        meta = get_meta(symbol)
        assert isinstance(meta, InstrumentMeta)
        assert meta.symbol == symbol
        assert meta.price_scale > 0
        assert meta.price_range[0] < meta.price_range[1]
        assert meta.base_price > 0
        assert meta.fixture_volatility > 0
        assert meta.fixture_volume_range[0] < meta.fixture_volume_range[1]
        assert len(meta.timeframes) >= 4
        assert meta.yfinance_alias != ""
        assert meta.trust_level in ("trusted", "provisional", "unverified")

    @pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSD", "GBPUSD", "XAGUSD", "XPTUSD"])
    def test_base_price_within_range(self, symbol):
        """Fixture base price must fall inside the plausible price range."""
        meta = get_meta(symbol)
        lo, hi = meta.price_range
        assert lo <= meta.base_price <= hi, (
            f"{symbol} base_price {meta.base_price} outside range ({lo}, {hi})"
        )

    @pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSD", "GBPUSD", "XAGUSD", "XPTUSD"])
    def test_frozen_immutability(self, symbol):
        """InstrumentMeta must be frozen (immutable)."""
        meta = get_meta(symbol)
        with pytest.raises(AttributeError):
            meta.price_scale = 999  # type: ignore[misc]

    def test_get_meta_raises_for_unknown(self):
        with pytest.raises(KeyError):
            get_meta("ZZZZZ")


# ── AC-2: Provider metadata model ────────────────────────────────────

class TestProviderMetadata:
    """yfinance_alias is metadata-only — present but not live."""

    EXPECTED_ALIASES = {
        "EURUSD": "EURUSD=X",
        "XAUUSD": "GC=F",
        "GBPUSD": "GBPUSD=X",
        "XAGUSD": "SI=F",
        "XPTUSD": "PL=F",
    }

    @pytest.mark.parametrize("symbol,alias", list(EXPECTED_ALIASES.items()))
    def test_yfinance_alias_correct(self, symbol, alias):
        assert get_meta(symbol).yfinance_alias == alias


# ── AC-5: Fixture generalisation ─────────────────────────────────────

class TestFixtureParams:
    """Fixture seeding parameters are consistent and registry-derived."""

    def test_eurusd_fixture_params_unchanged(self):
        meta = get_meta("EURUSD")
        assert meta.base_price == 1.0850
        assert meta.fixture_volatility == 0.0005
        assert meta.fixture_volume_range == (100, 5000)

    def test_xauusd_fixture_params_unchanged(self):
        meta = get_meta("XAUUSD")
        assert meta.base_price == 2700.0
        assert meta.fixture_volatility == 2.0
        assert meta.fixture_volume_range == (0.1, 10.0)


# ── AC-2 / Trust model ───────────────────────────────────────────────

class TestTrustLevels:
    """Trust levels derive correctly from the registry."""

    def test_trusted_set(self):
        trusted = {s for s, m in INSTRUMENT_REGISTRY.items() if m.trust_level == "trusted"}
        assert trusted == {"EURUSD", "XAUUSD", "GBPUSD", "XAGUSD", "XPTUSD"}

    def test_no_unverified_instruments(self):
        unverified = {s for s, m in INSTRUMENT_REGISTRY.items() if m.trust_level == "unverified"}
        assert unverified == set()


# ── AC-3 / AC-4: Consumer derivation ─────────────────────────────────

class TestConsumerDerivation:
    """Consumers (feed/config, officer/service, structure/config) derive from registry."""

    def test_feed_instruments_matches_registry(self):
        from feed.config import INSTRUMENTS
        assert set(INSTRUMENTS.keys()) == set(INSTRUMENT_REGISTRY.keys())

    def test_feed_price_ranges_matches_registry(self):
        from feed.config import PRICE_RANGES
        for sym, meta in INSTRUMENT_REGISTRY.items():
            assert PRICE_RANGES[sym] == meta.price_range

    def test_officer_trusted_from_registry(self):
        from officer.service import TRUSTED_INSTRUMENTS
        assert TRUSTED_INSTRUMENTS == {"EURUSD", "XAUUSD", "GBPUSD", "XAGUSD", "XPTUSD"}

    def test_officer_provisional_from_registry(self):
        from officer.service import PROVISIONAL_INSTRUMENTS
        assert PROVISIONAL_INSTRUMENTS == set()

    def test_structure_eqh_eql_from_registry(self):
        from structure.config import StructureConfig
        cfg = StructureConfig()
        for sym in ("EURUSD", "XAUUSD"):
            assert cfg.eqh_eql_tolerance[sym] == get_meta(sym).eqh_eql_tolerance

    def test_structure_fvg_min_from_registry(self):
        from structure.config import StructureConfig
        cfg = StructureConfig()
        assert cfg.fvg_min_size_eurusd == get_meta("EURUSD").fvg_min_size
        assert cfg.fvg_min_size_xauusd == get_meta("XAUUSD").fvg_min_size


# ── AC-6: Extension ergonomics ───────────────────────────────────────

class TestExtensionErgonomics:
    """Adding a new instrument is config-first — no scattered code edits."""

    def test_backward_compatible_constructor(self):
        """InstrumentMeta can be constructed with just symbol + price_scale."""
        meta = InstrumentMeta(symbol="TEST", price_scale=1000)
        assert meta.symbol == "TEST"
        assert meta.trust_level == "unverified"

    def test_new_instrument_auto_propagates_to_feed(self):
        """Any instrument added to INSTRUMENT_REGISTRY appears in INSTRUMENTS."""
        from feed.config import INSTRUMENTS
        # All registry entries are in INSTRUMENTS (they're the same dict)
        for sym in INSTRUMENT_REGISTRY:
            assert sym in INSTRUMENTS

    def test_new_instrument_auto_propagates_to_price_ranges(self):
        from feed.config import PRICE_RANGES
        for sym in INSTRUMENT_REGISTRY:
            assert sym in PRICE_RANGES


# ── AC-7 / AC-8 / AC-9 / AC-10: Guard rails ─────────────────────────

class TestGuardRails:
    """Phase E+ hard constraints."""

    def test_no_sqlite_import(self):
        """AC-8: No sqlite3 in any market_data_officer module."""
        import subprocess
        mdo_root = Path(__file__).resolve().parent.parent
        this_file = str(Path(__file__).resolve())
        result = subprocess.run(
            ["grep", "-r", "import sqlite", str(mdo_root),
             "--include=*.py", "-l"],
            capture_output=True, text=True,
        )
        hits = [f for f in result.stdout.strip().split("\n") if f and f != this_file]
        assert hits == [], f"sqlite import found in: {hits}"

    def test_no_scheduler_import(self):
        """AC-10: No APScheduler imports outside the designated scheduler module."""
        import subprocess
        mdo_root = Path(__file__).resolve().parent.parent
        this_file = str(Path(__file__).resolve())
        # scheduler.py and run_scheduler.py are the designated scheduler modules
        allowed = {
            str(mdo_root / "scheduler.py"),
            str(mdo_root / "run_scheduler.py"),
        }
        result = subprocess.run(
            ["grep", "-r", "-i", "import apscheduler\\|from apscheduler",
             str(mdo_root), "--include=*.py", "-l"],
            capture_output=True, text=True,
        )
        hits = [f for f in result.stdout.strip().split("\n")
                if f and f != this_file and f not in allowed]
        assert hits == [], f"apscheduler import found outside scheduler modules: {hits}"

    def test_registry_is_inside_package(self):
        """AC-9: instrument_registry.py lives inside market_data_officer/, not top-level."""
        registry_path = Path(__file__).resolve().parent.parent / "instrument_registry.py"
        assert registry_path.exists()
        # Confirm it's inside market_data_officer/
        assert "market_data_officer" in str(registry_path)


# ── Timeframe consistency ────────────────────────────────────────────

class TestTimeframes:
    """Timeframe metadata is consistent across instruments."""

    def test_fx_instruments_have_6_timeframes(self):
        for sym in ("EURUSD", "GBPUSD"):
            meta = get_meta(sym)
            assert len(meta.timeframes) == 6
            assert "1m" in meta.timeframes

    def test_metal_instruments_have_4_timeframes(self):
        for sym in ("XAUUSD", "XAGUSD", "XPTUSD"):
            meta = get_meta(sym)
            assert len(meta.timeframes) == 4
            assert "1m" not in meta.timeframes
            assert "15m" in meta.timeframes
