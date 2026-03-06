"""Tests for the cache diagnostics layer (Phase 1D)."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from feed.diagnostics import (
    DiagnosticsCollector,
    FetchRecord,
    DecodeRecord,
    HourDiagnostic,
    generate_cache_inventory,
    save_cache_inventory,
    verify_decode_assumptions,
)
from feed.decode import DecodeStats, decode_with_diagnostics
from feed.config import InstrumentMeta
from feed.fetch import FetchResult, fetch_bi5_detailed


# --- FetchRecord / DecodeRecord dataclass tests ---


class TestFetchRecord:
    def test_fields(self):
        rec = FetchRecord(
            hour_utc="2025-01-13T10:00:00+00:00",
            url="https://example.com/bi5",
            http_status=200,
            payload_bytes=1024,
            content_sha256="abc123",
            fetch_utc="2025-01-13T10:00:01+00:00",
            cached_path="/tmp/test.bi5",
            error="",
        )
        assert rec.http_status == 200
        assert rec.payload_bytes == 1024
        assert rec.error == ""

    def test_error_record(self):
        rec = FetchRecord(
            hour_utc="2025-01-13T10:00:00+00:00",
            url="https://example.com/bi5",
            http_status=0,
            payload_bytes=0,
            content_sha256="",
            fetch_utc="2025-01-13T10:00:01+00:00",
            cached_path="",
            error="network_error:timeout",
        )
        assert rec.http_status == 0
        assert "timeout" in rec.error


class TestDecodeRecord:
    def test_fields(self):
        rec = DecodeRecord(
            hour_utc="2025-01-13T10:00:00+00:00",
            tick_count=500,
            bars_produced=58,
            price_min=1.08500,
            price_max=1.08600,
            volume_total=2500.0,
            decode_error="",
        )
        assert rec.tick_count == 500
        assert rec.bars_produced == 58
        assert rec.decode_error == ""

    def test_empty_decode(self):
        rec = DecodeRecord(
            hour_utc="2025-01-13T10:00:00+00:00",
            tick_count=0,
            bars_produced=0,
            price_min=None,
            price_max=None,
            volume_total=None,
            decode_error="empty_input",
        )
        assert rec.tick_count == 0
        assert rec.price_min is None


# --- DiagnosticsCollector tests ---


class TestDiagnosticsCollector:
    def test_empty_report(self):
        collector = DiagnosticsCollector("EURUSD")
        report = collector.build_report()
        assert report["symbol"] == "EURUSD"
        assert report["summary"]["total_hour_slots"] == 0
        assert report["hours"] == []

    def test_record_fetch_and_decode(self):
        collector = DiagnosticsCollector("EURUSD")

        hour = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        payload = b"test_payload_bytes"

        collector.record_fetch(
            hour_utc=hour,
            url="https://example.com/test.bi5",
            http_status=200,
            payload=payload,
            cached_path="/tmp/test.bi5",
        )
        collector.record_decode(
            hour_utc=hour,
            tick_count=500,
            bars_produced=58,
            price_min=1.085,
            price_max=1.086,
            volume_total=2500.0,
        )

        report = collector.build_report()
        assert report["summary"]["total_hour_slots"] == 1
        assert report["summary"]["fetched"] == 1
        assert report["summary"]["total_ticks_decoded"] == 500
        assert report["summary"]["total_bars_produced"] == 58

        hour_entry = report["hours"][0]
        assert hour_entry["fetch"]["http_status"] == 200
        assert hour_entry["fetch"]["payload_bytes"] == len(payload)
        expected_hash = hashlib.sha256(payload).hexdigest()
        assert hour_entry["fetch"]["content_sha256"] == expected_hash
        assert hour_entry["decode"]["tick_count"] == 500
        assert hour_entry["decode"]["price_min"] == 1.085

    def test_record_skipped(self):
        collector = DiagnosticsCollector("EURUSD")
        hour = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        collector.record_skipped(hour)

        report = collector.build_report()
        assert report["summary"]["skipped_incremental"] == 1
        assert report["summary"]["fetched"] == 0

        hour_entry = report["hours"][0]
        assert hour_entry["fetch"]["http_status"] == -1
        assert hour_entry["fetch"]["error"] == "skipped:incremental"

    def test_multiple_hours_sorted(self):
        collector = DiagnosticsCollector("EURUSD")

        h1 = datetime(2025, 1, 13, 12, 0, tzinfo=timezone.utc)
        h2 = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        h3 = datetime(2025, 1, 13, 11, 0, tzinfo=timezone.utc)

        for h in [h1, h2, h3]:
            collector.record_fetch(h, "url", 200, b"data", "")

        report = collector.build_report()
        hours = report["hours"]
        assert len(hours) == 3
        # Should be sorted by hour_utc
        assert hours[0]["hour_utc"] < hours[1]["hour_utc"] < hours[2]["hour_utc"]

    def test_fetch_error_counted(self):
        collector = DiagnosticsCollector("EURUSD")
        hour = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)

        collector.record_fetch(
            hour_utc=hour,
            url="https://example.com/test.bi5",
            http_status=0,
            payload=b"",
            error="network_error:connection_refused",
        )

        report = collector.build_report()
        assert report["summary"]["fetch_errors"] == 1
        assert report["summary"]["fetched"] == 0

    def test_empty_payload_counted(self):
        collector = DiagnosticsCollector("EURUSD")
        hour = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)

        collector.record_fetch(
            hour_utc=hour,
            url="https://example.com/test.bi5",
            http_status=200,
            payload=b"",
        )

        report = collector.build_report()
        assert report["summary"]["empty_payloads"] == 1
        assert report["summary"]["fetched"] == 1

    def test_save_report(self, tmp_path):
        collector = DiagnosticsCollector("EURUSD")
        hour = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        collector.record_fetch(hour, "url", 200, b"data")

        path = collector.save_report(output_dir=tmp_path)
        assert path.exists()
        assert path.name == "EURUSD_diagnostics.json"

        report = json.loads(path.read_text())
        assert report["symbol"] == "EURUSD"
        assert report["summary"]["total_hour_slots"] == 1

    def test_summary_byte_totals(self):
        collector = DiagnosticsCollector("EURUSD")

        h1 = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        h2 = datetime(2025, 1, 13, 11, 0, tzinfo=timezone.utc)

        collector.record_fetch(h1, "url1", 200, b"a" * 100)
        collector.record_fetch(h2, "url2", 200, b"b" * 200)

        report = collector.build_report()
        assert report["summary"]["total_payload_bytes"] == 300


# --- Cache inventory tests ---


class TestCacheInventory:
    def test_nonexistent_dir(self, tmp_path):
        inv = generate_cache_inventory("EURUSD", raw_dir=tmp_path / "raw")
        assert inv["exists"] is False
        assert inv["summary"]["total_files"] == 0

    def test_empty_dir(self, tmp_path):
        cache_dir = tmp_path / "EURUSD"
        cache_dir.mkdir(parents=True)
        inv = generate_cache_inventory("EURUSD", raw_dir=tmp_path)
        assert inv["exists"] is True
        assert inv["summary"]["total_files"] == 0

    def test_with_bi5_files(self, tmp_path):
        cache_dir = tmp_path / "EURUSD" / "2025" / "00" / "13"
        cache_dir.mkdir(parents=True)

        data1 = b"payload_hour_10"
        data2 = b"payload_hour_11"
        (cache_dir / "10h_ticks.bi5").write_bytes(data1)
        (cache_dir / "11h_ticks.bi5").write_bytes(data2)

        inv = generate_cache_inventory("EURUSD", raw_dir=tmp_path)
        assert inv["exists"] is True
        assert inv["summary"]["total_files"] == 2
        assert inv["summary"]["total_bytes"] == len(data1) + len(data2)
        assert "2025" in inv["summary"]["years"]

        # Verify sha256
        for f in inv["files"]:
            if "10h" in f["path"]:
                assert f["sha256"] == hashlib.sha256(data1).hexdigest()

    def test_save_cache_inventory(self, tmp_path):
        cache_dir = tmp_path / "raw" / "EURUSD"
        cache_dir.mkdir(parents=True)
        (cache_dir / "test.bi5").write_bytes(b"test")

        out_dir = tmp_path / "reports"
        path = save_cache_inventory("EURUSD", raw_dir=tmp_path / "raw", output_dir=out_dir)
        assert path.exists()
        assert path.name == "EURUSD_cache_inventory.json"


# --- Decode anomaly verification tests ---


class TestVerifyDecodeAssumptions:
    def _make_report_with_hours(self, hours_data):
        """Build a minimal diagnostics report dict from hour specs."""
        hours = []
        for h in hours_data:
            entry = {
                "hour_utc": h["hour_utc"],
                "fetch": {
                    "payload_bytes": h.get("payload_bytes", 1024),
                    "http_status": 200,
                },
                "decode": {
                    "tick_count": h.get("tick_count", 500),
                    "bars_produced": h.get("bars_produced", 58),
                    "price_min": h.get("price_min", 1.085),
                    "price_max": h.get("price_max", 1.086),
                    "volume_total": h.get("volume_total", 2500.0),
                    "decode_error": h.get("decode_error", ""),
                },
            }
            hours.append(entry)
        return {"symbol": "EURUSD", "hours": hours}

    def test_no_anomalies(self):
        hours = [
            {"hour_utc": f"2025-01-13T{h:02d}:00:00+00:00", "tick_count": 500,
             "price_min": 1.085, "price_max": 1.086}
            for h in range(10, 15)
        ]
        report = self._make_report_with_hours(hours)
        result = verify_decode_assumptions("EURUSD", report)
        assert result["anomalies_found"] == 0

    def test_empty_decode_anomaly(self):
        hours = [
            {"hour_utc": "2025-01-13T10:00:00+00:00", "tick_count": 500,
             "price_min": 1.085, "price_max": 1.086},
            {"hour_utc": "2025-01-13T11:00:00+00:00", "tick_count": 0,
             "payload_bytes": 1024, "price_min": None, "price_max": None},
        ]
        report = self._make_report_with_hours(hours)
        result = verify_decode_assumptions("EURUSD", report)
        assert result["anomalies_found"] >= 1
        assert any(a["type"] == "empty_decode" for a in result["anomalies"])

    def test_price_range_outlier(self):
        # Normal hours: range = 0.001
        hours = [
            {"hour_utc": f"2025-01-13T{h:02d}:00:00+00:00", "tick_count": 500,
             "price_min": 1.085, "price_max": 1.086}
            for h in range(10, 20)
        ]
        # Outlier hour: range = 0.01 (10x median)
        hours.append({
            "hour_utc": "2025-01-13T20:00:00+00:00",
            "tick_count": 500,
            "price_min": 1.080,
            "price_max": 1.090,
        })
        report = self._make_report_with_hours(hours)
        result = verify_decode_assumptions("EURUSD", report)
        assert any(a["type"] == "price_range_outlier" for a in result["anomalies"])

    def test_low_tick_density(self):
        # Most hours: 500 ticks
        hours = [
            {"hour_utc": f"2025-01-13T{h:02d}:00:00+00:00", "tick_count": 500,
             "price_min": 1.085, "price_max": 1.086}
            for h in range(10, 20)
        ]
        # Anomaly: only 10 ticks (2% of median)
        hours.append({
            "hour_utc": "2025-01-13T20:00:00+00:00",
            "tick_count": 10,
            "price_min": 1.085,
            "price_max": 1.086,
        })
        report = self._make_report_with_hours(hours)
        result = verify_decode_assumptions("EURUSD", report)
        assert any(a["type"] == "low_tick_density" for a in result["anomalies"])

    def test_high_tick_density(self):
        hours = [
            {"hour_utc": f"2025-01-13T{h:02d}:00:00+00:00", "tick_count": 500,
             "price_min": 1.085, "price_max": 1.086}
            for h in range(10, 20)
        ]
        # Anomaly: 5000 ticks (10x median)
        hours.append({
            "hour_utc": "2025-01-13T20:00:00+00:00",
            "tick_count": 5000,
            "price_min": 1.085,
            "price_max": 1.086,
        })
        report = self._make_report_with_hours(hours)
        result = verify_decode_assumptions("EURUSD", report)
        assert any(a["type"] == "high_tick_density" for a in result["anomalies"])

    def test_reference_stats_populated(self):
        hours = [
            {"hour_utc": f"2025-01-13T{h:02d}:00:00+00:00", "tick_count": 500,
             "price_min": 1.085, "price_max": 1.086}
            for h in range(10, 15)
        ]
        report = self._make_report_with_hours(hours)
        result = verify_decode_assumptions("EURUSD", report)
        assert result["reference_stats"]["median_ticks_per_hour"] == 500
        assert result["reference_stats"]["hours_analyzed"] == 5

    def test_empty_report(self):
        report = {"symbol": "EURUSD", "hours": []}
        result = verify_decode_assumptions("EURUSD", report)
        assert result["anomalies_found"] == 0


# --- decode_with_diagnostics tests ---


class TestDecodeWithDiagnostics:
    def test_empty_input(self):
        meta = InstrumentMeta(symbol="EURUSD", price_scale=100_000)
        hour = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        df, stats = decode_with_diagnostics(b"", hour, meta)
        assert df.empty
        assert stats.tick_count == 0
        assert stats.error == "empty_input"

    def test_corrupt_input(self):
        meta = InstrumentMeta(symbol="EURUSD", price_scale=100_000)
        hour = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        df, stats = decode_with_diagnostics(b"corrupt_data", hour, meta)
        assert df.empty
        assert stats.tick_count == 0
        # Either LZMA error or empty result
        assert stats.error == "" or stats.error != ""


# --- FetchResult dataclass test ---


class TestFetchResult:
    def test_success_result(self):
        result = FetchResult(
            data=b"test",
            url="https://example.com/test.bi5",
            http_status=200,
            cached_path="/tmp/test.bi5",
            error="",
        )
        assert result.http_status == 200
        assert result.data == b"test"
        assert result.error == ""

    def test_error_result(self):
        result = FetchResult(
            data=b"",
            url="https://example.com/test.bi5",
            http_status=0,
            cached_path="",
            error="network_error:timeout",
        )
        assert result.http_status == 0
        assert result.data == b""
        assert "timeout" in result.error
