"""Deterministic tests for Market Data OHLCV endpoint (PR-CHART-1).

Covers AC-7 through AC-24 from docs/specs/PR_CHART_1_SPEC.md §7.

All tests use temp directories with fixture CSV data — no live pipeline dependency.
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from ai_analyst.api.models.market_data import Candle, OHLCVResponse
from ai_analyst.api.services.market_data_read import (
    InstrumentNotFound,
    MarketDataReadError,
    TimeframeNotFound,
    read_ohlcv,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_csv(packages_dir: Path, instrument: str, tf: str, rows: list[dict]) -> Path:
    """Write a hot package CSV with OHLCV data."""
    packages_dir.mkdir(parents=True, exist_ok=True)
    csv_path = packages_dir / f"{instrument}_{tf}_latest.csv"
    if not rows:
        csv_path.write_text("timestamp_utc,open,high,low,close,volume\n")
        return csv_path

    lines = ["timestamp_utc,open,high,low,close,volume"]
    for r in rows:
        lines.append(
            f"{r['ts']},{r['o']},{r['h']},{r['l']},{r['c']},{r['v']}"
        )
    csv_path.write_text("\n".join(lines) + "\n")
    return csv_path


def _write_manifest(packages_dir: Path, instrument: str, as_of: str = "2026-03-15T11:00:00Z") -> Path:
    """Write a hot package manifest JSON."""
    packages_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = packages_dir / f"{instrument}_hot.json"
    manifest = {
        "instrument": instrument,
        "as_of_utc": as_of,
        "schema": "timestamp_utc,open,high,low,close,volume",
        "windows": {},
    }
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


def _make_rows(count: int, base_ts: int = 1710000000, interval: int = 14400) -> list[dict]:
    """Generate N valid OHLCV rows starting from base_ts, spaced by interval seconds."""
    rows = []
    for i in range(count):
        ts = datetime.fromtimestamp(base_ts + i * interval, tz=timezone.utc)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S+00:00")
        rows.append({
            "ts": ts_str,
            "o": round(2700.0 + i * 0.5, 2),
            "h": round(2701.0 + i * 0.5, 2),
            "l": round(2699.0 + i * 0.5, 2),
            "c": round(2700.5 + i * 0.5, 2),
            "v": round(1.0 + i * 0.1, 2),
        })
    return rows


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def packages_dir(tmp_path):
    """Provide a temp hot packages directory."""
    d = tmp_path / "packages" / "latest"
    d.mkdir(parents=True)
    return d


@pytest.fixture()
def populated_dir(packages_dir):
    """Provide a directory with valid XAUUSD 4h data and manifest."""
    rows = _make_rows(120)
    _write_csv(packages_dir, "XAUUSD", "4h", rows)
    _write_manifest(packages_dir, "XAUUSD")
    return packages_dir


# ── AC-7: Endpoint exists / valid response shape ────────────────────────────


class TestAC7ResponseShape:
    def test_valid_response_shape(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=10, packages_dir=populated_dir)
        assert isinstance(resp, OHLCVResponse)
        assert resp.instrument == "XAUUSD"
        assert resp.timeframe == "4h"
        assert isinstance(resp.candles, list)
        assert isinstance(resp.candle_count, int)

    def test_response_has_all_fields(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=5, packages_dir=populated_dir)
        d = resp.model_dump()
        assert "version" in d
        assert "generated_at" in d
        assert "data_state" in d
        assert "instrument" in d
        assert "timeframe" in d
        assert "candles" in d
        assert "candle_count" in d


# ── AC-8: ResponseMeta present ──────────────────────────────────────────────


class TestAC8ResponseMeta:
    def test_version_present(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=5, packages_dir=populated_dir)
        assert resp.version == "2026.03"

    def test_generated_at_is_iso(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=5, packages_dir=populated_dir)
        # Should parse as a valid datetime
        dt = datetime.fromisoformat(resp.generated_at.replace("Z", "+00:00"))
        assert dt.tzinfo is not None or resp.generated_at.endswith("Z")

    def test_data_state_is_valid(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=5, packages_dir=populated_dir)
        assert resp.data_state in ("live", "stale", "unavailable")


# ── AC-9: Candle shape correct ──────────────────────────────────────────────


class TestAC9CandleShape:
    def test_candle_has_epoch_timestamp(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=5, packages_dir=populated_dir)
        for candle in resp.candles:
            assert isinstance(candle.timestamp, int)
            # Should be a reasonable epoch (after 2020)
            assert candle.timestamp > 1577836800

    def test_candle_has_numeric_ohlcv(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=5, packages_dir=populated_dir)
        for candle in resp.candles:
            assert isinstance(candle.open, float)
            assert isinstance(candle.high, float)
            assert isinstance(candle.low, float)
            assert isinstance(candle.close, float)
            assert isinstance(candle.volume, float)


# ── AC-10: Oldest-first order ───────────────────────────────────────────────


class TestAC10OldestFirst:
    def test_ascending_timestamp_order(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=50, packages_dir=populated_dir)
        timestamps = [c.timestamp for c in resp.candles]
        assert timestamps == sorted(timestamps)
        assert len(set(timestamps)) == len(timestamps)  # no duplicates


# ── AC-11: Limit parameter ─────────────────────────────────────────────────


class TestAC11Limit:
    def test_limit_50_returns_at_most_50(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=50, packages_dir=populated_dir)
        assert resp.candle_count <= 50
        assert len(resp.candles) == resp.candle_count

    def test_default_limit_100(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", packages_dir=populated_dir)
        assert resp.candle_count <= 100

    def test_limit_500_max(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=500, packages_dir=populated_dir)
        assert resp.candle_count <= 500

    def test_limit_returns_most_recent(self, populated_dir):
        resp_all = read_ohlcv("XAUUSD", "4h", limit=500, packages_dir=populated_dir)
        resp_10 = read_ohlcv("XAUUSD", "4h", limit=10, packages_dir=populated_dir)
        # The 10 most recent from full set should match limit=10
        last_10 = [c.timestamp for c in resp_all.candles[-10:]]
        got_10 = [c.timestamp for c in resp_10.candles]
        assert got_10 == last_10


# ── AC-12: Limit negative cases (validated by router, tested via TestClient) ─


class TestAC12LimitValidation:
    """Limit validation is done in the router. Test via FastAPI TestClient."""

    @pytest.fixture()
    def client(self, populated_dir, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.market_data import router
        import ai_analyst.api.services.market_data_read as svc

        monkeypatch.setattr(svc, "PACKAGES_DIR", populated_dir)
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_limit_zero_returns_422(self, client):
        r = client.get("/market-data/XAUUSD/ohlcv?limit=0")
        assert r.status_code == 422
        body = r.json()
        assert body["detail"]["error"] == "INVALID_PARAMS"

    def test_limit_negative_returns_422(self, client):
        r = client.get("/market-data/XAUUSD/ohlcv?limit=-1")
        assert r.status_code == 422
        body = r.json()
        assert body["detail"]["error"] == "INVALID_PARAMS"

    def test_limit_501_returns_422(self, client):
        r = client.get("/market-data/XAUUSD/ohlcv?limit=501")
        assert r.status_code == 422
        body = r.json()
        assert body["detail"]["error"] == "INVALID_PARAMS"


# ── AC-13: Timeframe parameter ──────────────────────────────────────────────


class TestAC13Timeframe:
    def test_specific_timeframe(self, packages_dir):
        rows_1h = _make_rows(50, interval=3600)
        _write_csv(packages_dir, "XAUUSD", "1h", rows_1h)
        _write_manifest(packages_dir, "XAUUSD")
        resp = read_ohlcv("XAUUSD", "1h", limit=50, packages_dir=packages_dir)
        assert resp.timeframe == "1h"
        assert resp.candle_count == 50


# ── AC-14: Default timeframe ───────────────────────────────────────────────


class TestAC14DefaultTimeframe:
    def test_default_is_4h(self, populated_dir, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.market_data import router
        import ai_analyst.api.services.market_data_read as svc

        monkeypatch.setattr(svc, "PACKAGES_DIR", populated_dir)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        r = client.get("/market-data/XAUUSD/ohlcv")
        assert r.status_code == 200
        body = r.json()
        assert body["timeframe"] == "4h"


# ── AC-15: Unknown instrument → 404 ────────────────────────────────────────


class TestAC15UnknownInstrument:
    def test_unknown_instrument_raises(self, packages_dir):
        with pytest.raises(InstrumentNotFound):
            read_ohlcv("FAKEUSD", "4h", packages_dir=packages_dir)

    def test_unknown_instrument_404_via_client(self, packages_dir, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.market_data import router
        import ai_analyst.api.services.market_data_read as svc

        monkeypatch.setattr(svc, "PACKAGES_DIR", packages_dir)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        r = client.get("/market-data/FAKEUSD/ohlcv")
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "INSTRUMENT_NOT_FOUND"


# ── AC-16: Unknown timeframe → 404 ─────────────────────────────────────────


class TestAC16UnknownTimeframe:
    def test_missing_timeframe_raises(self, packages_dir):
        _write_manifest(packages_dir, "XAUUSD")
        with pytest.raises(TimeframeNotFound):
            read_ohlcv("XAUUSD", "99h", packages_dir=packages_dir)

    def test_missing_timeframe_404_via_client(self, packages_dir, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.market_data import router
        import ai_analyst.api.services.market_data_read as svc

        monkeypatch.setattr(svc, "PACKAGES_DIR", packages_dir)
        _write_manifest(packages_dir, "XAUUSD")
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        r = client.get("/market-data/XAUUSD/ohlcv?timeframe=99h")
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "TIMEFRAME_NOT_FOUND"


# ── AC-17: Empty data store → 200 with candles:[] ──────────────────────────


class TestAC17EmptyStore:
    def test_empty_csv_returns_empty_candles(self, packages_dir):
        _write_csv(packages_dir, "XAUUSD", "4h", [])
        _write_manifest(packages_dir, "XAUUSD")
        resp = read_ohlcv("XAUUSD", "4h", packages_dir=packages_dir)
        assert resp.candles == []
        assert resp.candle_count == 0
        assert resp.data_state == "unavailable"


# ── AC-18: Malformed row tolerance ──────────────────────────────────────────


class TestAC18MalformedRows:
    def test_some_malformed_rows_dropped(self, packages_dir):
        # 9 valid + 1 malformed (10%) → should be "live" since exactly 10% is < threshold
        rows = _make_rows(9)
        rows.append({"ts": "2026-03-15 12:00:00+00:00", "o": "NaN", "h": "1", "l": "1", "c": "1", "v": "1"})
        _write_csv(packages_dir, "XAUUSD", "4h", rows)
        _write_manifest(packages_dir, "XAUUSD")
        resp = read_ohlcv("XAUUSD", "4h", packages_dir=packages_dir)
        assert resp.candle_count == 9

    def test_over_10pct_malformed_stale(self, packages_dir):
        # 8 valid + 2 malformed (20%) → "stale"
        rows = _make_rows(8)
        rows.append({"ts": "2026-03-15 12:00:00+00:00", "o": "NaN", "h": "1", "l": "1", "c": "1", "v": "1"})
        rows.append({"ts": "2026-03-15 16:00:00+00:00", "o": "", "h": "1", "l": "1", "c": "1", "v": "1"})
        _write_csv(packages_dir, "XAUUSD", "4h", rows)
        _write_manifest(packages_dir, "XAUUSD")
        resp = read_ohlcv("XAUUSD", "4h", packages_dir=packages_dir)
        assert resp.candle_count == 8
        assert resp.data_state == "stale"

    def test_all_malformed_unavailable(self, packages_dir):
        rows = [
            {"ts": "2026-03-15 12:00:00+00:00", "o": "NaN", "h": "NaN", "l": "NaN", "c": "NaN", "v": "NaN"},
            {"ts": "2026-03-15 16:00:00+00:00", "o": "bad", "h": "bad", "l": "bad", "c": "bad", "v": "bad"},
        ]
        _write_csv(packages_dir, "XAUUSD", "4h", rows)
        _write_manifest(packages_dir, "XAUUSD")
        resp = read_ohlcv("XAUUSD", "4h", packages_dir=packages_dir)
        assert resp.candles == []
        assert resp.data_state == "unavailable"


# ── AC-19: No scheduler trigger ─────────────────────────────────────────────


class TestAC19NoScheduler:
    def test_no_scheduler_modules_loaded(self, populated_dir):
        # Track modules before the read
        scheduler_before = {m for m in sys.modules if "scheduler" in m.lower() or "apscheduler" in m.lower()}
        read_ohlcv("XAUUSD", "4h", limit=10, packages_dir=populated_dir)
        scheduler_after = {m for m in sys.modules if "scheduler" in m.lower() or "apscheduler" in m.lower()}
        new_scheduler = scheduler_after - scheduler_before
        assert new_scheduler == set(), f"Scheduler modules loaded during read: {new_scheduler}"


# ── AC-20: Read-only ────────────────────────────────────────────────────────


class TestAC20ReadOnly:
    def test_csv_unchanged_after_read(self, populated_dir):
        csv_path = populated_dir / "XAUUSD_4h_latest.csv"
        before = csv_path.read_text()
        read_ohlcv("XAUUSD", "4h", limit=10, packages_dir=populated_dir)
        after = csv_path.read_text()
        assert before == after


# ── AC-21: Error envelope shape ─────────────────────────────────────────────


class TestAC21ErrorEnvelope:
    @pytest.fixture()
    def client(self, packages_dir, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.market_data import router
        import ai_analyst.api.services.market_data_read as svc

        monkeypatch.setattr(svc, "PACKAGES_DIR", packages_dir)
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_404_has_error_and_message(self, client):
        r = client.get("/market-data/FAKEUSD/ohlcv")
        body = r.json()
        assert "detail" in body
        detail = body["detail"]
        assert "error" in detail
        assert "message" in detail

    def test_422_has_error_and_message(self, client):
        r = client.get("/market-data/XAUUSD/ohlcv?limit=0")
        body = r.json()
        detail = body["detail"]
        assert "error" in detail
        assert "message" in detail


# ── AC-22: data_state: live ─────────────────────────────────────────────────


class TestAC22DataStateLive:
    def test_clean_data_is_live(self, populated_dir):
        resp = read_ohlcv("XAUUSD", "4h", limit=10, packages_dir=populated_dir)
        assert resp.data_state == "live"


# ── AC-23: data_state: stale ───────────────────────────────────────────────


class TestAC23DataStateStale:
    def test_no_manifest_is_stale(self, packages_dir):
        rows = _make_rows(20)
        _write_csv(packages_dir, "XAUUSD", "4h", rows)
        # No manifest written → freshness unknown → stale
        resp = read_ohlcv("XAUUSD", "4h", packages_dir=packages_dir)
        assert resp.data_state == "stale"

    def test_high_drop_rate_is_stale(self, packages_dir):
        # 7 valid + 3 malformed = 30% drop → stale
        rows = _make_rows(7)
        for i in range(3):
            rows.append({"ts": f"2026-03-15 {12+i}:00:00+00:00", "o": "NaN", "h": "1", "l": "1", "c": "1", "v": "1"})
        _write_csv(packages_dir, "XAUUSD", "4h", rows)
        _write_manifest(packages_dir, "XAUUSD")
        resp = read_ohlcv("XAUUSD", "4h", packages_dir=packages_dir)
        assert resp.data_state == "stale"


# ── AC-24: data_state: unavailable ──────────────────────────────────────────


class TestAC24DataStateUnavailable:
    def test_empty_store_unavailable(self, packages_dir):
        _write_csv(packages_dir, "XAUUSD", "4h", [])
        _write_manifest(packages_dir, "XAUUSD")
        resp = read_ohlcv("XAUUSD", "4h", packages_dir=packages_dir)
        assert resp.data_state == "unavailable"

    def test_all_malformed_unavailable(self, packages_dir):
        rows = [{"ts": "2026-03-15 12:00:00+00:00", "o": "NaN", "h": "NaN", "l": "NaN", "c": "NaN", "v": "NaN"}]
        _write_csv(packages_dir, "XAUUSD", "4h", rows)
        _write_manifest(packages_dir, "XAUUSD")
        resp = read_ohlcv("XAUUSD", "4h", packages_dir=packages_dir)
        assert resp.data_state == "unavailable"


# ── AC-31: Router separation ───────────────────────────────────────────────


class TestAC31RouterSeparation:
    def test_market_data_route_registered(self):
        from ai_analyst.api.routers.market_data import router
        routes = [r.path for r in router.routes]
        assert "/market-data/{instrument}/ohlcv" in routes

    def test_ops_router_unchanged(self):
        from ai_analyst.api.routers.ops import router
        routes = [r.path for r in router.routes]
        assert all("/market-data" not in r for r in routes)

    def test_runs_router_unchanged(self):
        from ai_analyst.api.routers.runs import router
        routes = [r.path for r in router.routes]
        assert all("/market-data" not in r for r in routes)


# ── AC-34: Import boundary respected ───────────────────────────────────────


class TestAC34ImportBoundary:
    def test_service_does_not_import_forbidden(self):
        import ai_analyst.api.services.market_data_read as svc
        source = Path(svc.__file__).read_text()
        forbidden = [
            "from market_data_officer.structure",
            "from market_data_officer.scheduler",
            "from market_data_officer.officer.service",
            "build_market_packet",
            "compute_core_features",
            "APScheduler",
        ]
        for pattern in forbidden:
            assert pattern not in source, f"Forbidden import found: {pattern}"

    def test_allowed_imports_only(self):
        import ai_analyst.api.services.market_data_read as svc
        source = Path(svc.__file__).read_text()
        # Should import from these allowed modules
        assert "from market_data_officer.officer.loader" in source
        assert "from market_data_officer.instrument_registry" in source
        assert "from market_data_officer.feed.config" in source


# ── PR-CHART-2: Timeframe Discovery Endpoint ────────────────────────────────


class TestTimeframeDiscoveryService:
    """Service-level tests for discover_timeframes (PR-CHART-2 §4.2)."""

    def test_fx_instrument_returns_six_timeframes(self):
        from ai_analyst.api.services.market_data_read import discover_timeframes
        result = discover_timeframes("EURUSD")
        assert result == ["1m", "5m", "15m", "1h", "4h", "1d"]

    def test_metal_instrument_returns_four_timeframes(self):
        from ai_analyst.api.services.market_data_read import discover_timeframes
        result = discover_timeframes("XAUUSD")
        assert result == ["15m", "1h", "4h", "1d"]

    def test_another_metal_instrument(self):
        from ai_analyst.api.services.market_data_read import discover_timeframes
        result = discover_timeframes("XAGUSD")
        assert result == ["15m", "1h", "4h", "1d"]

    def test_unknown_instrument_raises(self):
        from ai_analyst.api.services.market_data_read import (
            InstrumentNotFound,
            discover_timeframes,
        )
        with pytest.raises(InstrumentNotFound):
            discover_timeframes("NOTREAL")

    def test_gbpusd_fx_timeframes(self):
        from ai_analyst.api.services.market_data_read import discover_timeframes
        result = discover_timeframes("GBPUSD")
        assert result == ["1m", "5m", "15m", "1h", "4h", "1d"]

    def test_xptusd_metal_timeframes(self):
        from ai_analyst.api.services.market_data_read import discover_timeframes
        result = discover_timeframes("XPTUSD")
        assert result == ["15m", "1h", "4h", "1d"]

    def test_all_registry_instruments_discoverable(self):
        from market_data_officer.instrument_registry import INSTRUMENT_REGISTRY
        from ai_analyst.api.services.market_data_read import discover_timeframes
        for symbol in INSTRUMENT_REGISTRY:
            result = discover_timeframes(symbol)
            assert isinstance(result, list)
            assert len(result) > 0
            assert "4h" in result  # All instruments should have 4h


class TestTimeframeDiscoveryEndpoint:
    """Router-level tests for GET /market-data/{instrument}/timeframes."""

    def test_valid_instrument_response_shape(self):
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.market_data import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/market-data/XAUUSD/timeframes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["instrument"] == "XAUUSD"
        assert body["available_timeframes"] == ["15m", "1h", "4h", "1d"]

    def test_fx_instrument_response(self):
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.market_data import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/market-data/EURUSD/timeframes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["instrument"] == "EURUSD"
        assert body["available_timeframes"] == ["1m", "5m", "15m", "1h", "4h", "1d"]

    def test_unknown_instrument_404(self):
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.market_data import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/market-data/NOTREAL/timeframes")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"] == "INSTRUMENT_NOT_FOUND"

    def test_response_has_no_extra_envelope(self):
        """Response must be flat {instrument, available_timeframes} per §4.2."""
        from fastapi.testclient import TestClient
        from ai_analyst.api.routers.market_data import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/market-data/XAUUSD/timeframes")
        body = resp.json()
        assert set(body.keys()) == {"instrument", "available_timeframes"}
