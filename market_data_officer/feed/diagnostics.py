"""Cache diagnostics layer — structured payload audit, decode stats, and vendor trail per bar.

Phase 1D: provides per-hour fetch/decode diagnostics, raw cache inventory,
and a full diagnostics report for debugging trust and replay capability.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_ROOT, RAW_DIR, REPORTS_DIR


@dataclass
class FetchRecord:
    """Per-hour fetch metadata captured during pipeline execution."""

    hour_utc: str  # ISO format
    url: str
    http_status: int  # 0 = network error, -1 = skipped (incremental)
    payload_bytes: int
    content_sha256: str  # hex digest, empty string if no payload
    fetch_utc: str  # ISO format, empty string if skipped
    cached_path: str  # relative path if saved to raw cache, empty string otherwise
    error: str  # empty string if no error


@dataclass
class DecodeRecord:
    """Per-hour decode statistics captured during pipeline execution."""

    hour_utc: str  # ISO format
    tick_count: int
    bars_produced: int
    price_min: Optional[float]
    price_max: Optional[float]
    volume_total: Optional[float]
    decode_error: str  # empty string if no error


@dataclass
class HourDiagnostic:
    """Combined fetch + decode diagnostic for a single hour slot."""

    hour_utc: str
    fetch: FetchRecord
    decode: Optional[DecodeRecord]


class DiagnosticsCollector:
    """Accumulates per-hour diagnostics during a pipeline run.

    Usage:
        collector = DiagnosticsCollector(symbol)
        collector.record_fetch(hour, url, status, payload, ...)
        collector.record_decode(hour, tick_count, bars, price_range, ...)
        report = collector.build_report()
        collector.save_report()
    """

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._hours: Dict[str, HourDiagnostic] = {}
        self._start_utc = datetime.now(timezone.utc)

    def record_fetch(
        self,
        hour_utc: datetime,
        url: str,
        http_status: int,
        payload: bytes,
        cached_path: str = "",
        error: str = "",
    ) -> None:
        """Record fetch metadata for one hour slot."""
        hour_key = hour_utc.isoformat()
        content_hash = hashlib.sha256(payload).hexdigest() if payload else ""

        fetch_rec = FetchRecord(
            hour_utc=hour_key,
            url=url,
            http_status=http_status,
            payload_bytes=len(payload),
            content_sha256=content_hash,
            fetch_utc=datetime.now(timezone.utc).isoformat(),
            cached_path=cached_path,
            error=error,
        )

        if hour_key in self._hours:
            self._hours[hour_key].fetch = fetch_rec
        else:
            self._hours[hour_key] = HourDiagnostic(
                hour_utc=hour_key, fetch=fetch_rec, decode=None
            )

    def record_skipped(self, hour_utc: datetime) -> None:
        """Record that an hour was skipped due to incremental logic."""
        hour_key = hour_utc.isoformat()
        fetch_rec = FetchRecord(
            hour_utc=hour_key,
            url="",
            http_status=-1,
            payload_bytes=0,
            content_sha256="",
            fetch_utc="",
            cached_path="",
            error="skipped:incremental",
        )
        self._hours[hour_key] = HourDiagnostic(
            hour_utc=hour_key, fetch=fetch_rec, decode=None
        )

    def record_decode(
        self,
        hour_utc: datetime,
        tick_count: int,
        bars_produced: int,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        volume_total: Optional[float] = None,
        decode_error: str = "",
    ) -> None:
        """Record decode statistics for one hour slot."""
        hour_key = hour_utc.isoformat()
        decode_rec = DecodeRecord(
            hour_utc=hour_key,
            tick_count=tick_count,
            bars_produced=bars_produced,
            price_min=price_min,
            price_max=price_max,
            volume_total=volume_total,
            decode_error=decode_error,
        )

        if hour_key in self._hours:
            self._hours[hour_key].decode = decode_rec
        else:
            # Decode recorded without a fetch (unusual, but handle gracefully)
            dummy_fetch = FetchRecord(
                hour_utc=hour_key,
                url="",
                http_status=0,
                payload_bytes=0,
                content_sha256="",
                fetch_utc="",
                cached_path="",
                error="fetch_not_recorded",
            )
            self._hours[hour_key] = HourDiagnostic(
                hour_utc=hour_key, fetch=dummy_fetch, decode=decode_rec
            )

    def build_report(self) -> Dict:
        """Build a JSON-serializable diagnostics report."""
        hours_sorted = sorted(self._hours.values(), key=lambda h: h.hour_utc)

        # Compute summary stats
        total_hours = len(hours_sorted)
        fetched = [h for h in hours_sorted if h.fetch.http_status > 0]
        skipped = [h for h in hours_sorted if h.fetch.http_status == -1]
        errors = [h for h in hours_sorted if h.fetch.error and h.fetch.http_status == 0]
        empty_payloads = [h for h in fetched if h.fetch.payload_bytes == 0]
        with_ticks = [h for h in hours_sorted if h.decode and h.decode.tick_count > 0]

        total_bytes = sum(h.fetch.payload_bytes for h in hours_sorted)
        total_ticks = sum(h.decode.tick_count for h in hours_sorted if h.decode)
        total_bars = sum(h.decode.bars_produced for h in hours_sorted if h.decode)

        # Decode error summary
        decode_errors = [
            h for h in hours_sorted if h.decode and h.decode.decode_error
        ]

        report = {
            "symbol": self.symbol,
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pipeline_started_utc": self._start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "summary": {
                "total_hour_slots": total_hours,
                "fetched": len(fetched),
                "skipped_incremental": len(skipped),
                "fetch_errors": len(errors),
                "empty_payloads": len(empty_payloads),
                "hours_with_ticks": len(with_ticks),
                "total_payload_bytes": total_bytes,
                "total_ticks_decoded": total_ticks,
                "total_bars_produced": total_bars,
                "decode_errors": len(decode_errors),
            },
            "hours": [_hour_to_dict(h) for h in hours_sorted],
        }

        return report

    def save_report(self, output_dir: Optional[Path] = None) -> Path:
        """Save the diagnostics report to disk as JSON."""
        out = output_dir or REPORTS_DIR
        out.mkdir(parents=True, exist_ok=True)

        report = self.build_report()
        path = out / f"{self.symbol}_diagnostics.json"
        path.write_text(json.dumps(report, indent=2))
        print(f"[diagnostics] saved report: {path}")
        return path


def _hour_to_dict(h: HourDiagnostic) -> Dict:
    """Convert an HourDiagnostic to a plain dict for JSON serialization."""
    result = {"hour_utc": h.hour_utc, "fetch": asdict(h.fetch)}
    if h.decode is not None:
        result["decode"] = asdict(h.decode)
    return result


def generate_cache_inventory(symbol: str, raw_dir: Optional[Path] = None) -> Dict:
    """Scan the raw bi5 cache directory and build an inventory report.

    Returns a JSON-serializable dict listing every cached file with its
    size, along with summary statistics.
    """
    base = (raw_dir or RAW_DIR) / symbol

    if not base.exists():
        return {
            "symbol": symbol,
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cache_dir": str(base),
            "exists": False,
            "summary": {
                "total_files": 0,
                "total_bytes": 0,
                "years": [],
            },
            "files": [],
        }

    files: List[Dict] = []
    total_bytes = 0
    years_seen: set = set()

    for bi5_path in sorted(base.rglob("*.bi5")):
        rel = bi5_path.relative_to(base)
        size = bi5_path.stat().st_size
        total_bytes += size

        # Parse path components: {year}/{month_zero}/{day}/{hour}h_ticks.bi5
        parts = rel.parts
        year = parts[0] if len(parts) >= 1 else "?"
        years_seen.add(year)

        content_hash = hashlib.sha256(bi5_path.read_bytes()).hexdigest()

        files.append({
            "path": str(rel),
            "bytes": size,
            "sha256": content_hash,
        })

    return {
        "symbol": symbol,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cache_dir": str(base),
        "exists": True,
        "summary": {
            "total_files": len(files),
            "total_bytes": total_bytes,
            "years": sorted(years_seen),
        },
        "files": files,
    }


def save_cache_inventory(symbol: str, raw_dir: Optional[Path] = None,
                         output_dir: Optional[Path] = None) -> Path:
    """Generate and save a raw cache inventory report."""
    out = output_dir or REPORTS_DIR
    out.mkdir(parents=True, exist_ok=True)

    inventory = generate_cache_inventory(symbol, raw_dir)
    path = out / f"{symbol}_cache_inventory.json"
    path.write_text(json.dumps(inventory, indent=2))
    print(f"[diagnostics] saved cache inventory: {path}")
    return path


def verify_decode_assumptions(symbol: str, diagnostics_report: Dict) -> Dict:
    """Analyze a diagnostics report for decode anomalies.

    Checks:
    - Hours with zero ticks but non-empty payload (possible decode failure)
    - Price range outliers (> 2x range vs median hour)
    - Tick density anomalies (hours with unusually few/many ticks)

    Returns a JSON-serializable anomaly report.
    """
    hours = diagnostics_report.get("hours", [])
    anomalies: List[Dict] = []

    # Collect stats for hours that decoded successfully
    tick_counts = []
    price_ranges = []
    for h in hours:
        decode = h.get("decode")
        if decode and decode.get("tick_count", 0) > 0:
            tick_counts.append(decode["tick_count"])
            pmin = decode.get("price_min")
            pmax = decode.get("price_max")
            if pmin is not None and pmax is not None and pmax > 0:
                price_ranges.append(pmax - pmin)

    # Compute medians for comparison
    median_ticks = sorted(tick_counts)[len(tick_counts) // 2] if tick_counts else 0
    median_range = sorted(price_ranges)[len(price_ranges) // 2] if price_ranges else 0

    for h in hours:
        fetch = h.get("fetch", {})
        decode = h.get("decode")

        # Check 1: non-empty payload but zero ticks
        if fetch.get("payload_bytes", 0) > 0 and decode and decode.get("tick_count", 0) == 0:
            if not decode.get("decode_error"):
                anomalies.append({
                    "hour_utc": h["hour_utc"],
                    "type": "empty_decode",
                    "detail": f"payload {fetch['payload_bytes']} bytes but 0 ticks decoded",
                })

        if decode and decode.get("tick_count", 0) > 0:
            # Check 2: price range outlier (> 3x median)
            pmin = decode.get("price_min")
            pmax = decode.get("price_max")
            if pmin is not None and pmax is not None and median_range > 0:
                hour_range = pmax - pmin
                if hour_range > 3 * median_range:
                    anomalies.append({
                        "hour_utc": h["hour_utc"],
                        "type": "price_range_outlier",
                        "detail": f"range {hour_range:.6f} is >{3}x median {median_range:.6f}",
                    })

            # Check 3: tick density anomaly (< 10% or > 500% of median)
            tc = decode["tick_count"]
            if median_ticks > 0:
                ratio = tc / median_ticks
                if ratio < 0.1:
                    anomalies.append({
                        "hour_utc": h["hour_utc"],
                        "type": "low_tick_density",
                        "detail": f"{tc} ticks vs median {median_ticks} ({ratio:.1%})",
                    })
                elif ratio > 5.0:
                    anomalies.append({
                        "hour_utc": h["hour_utc"],
                        "type": "high_tick_density",
                        "detail": f"{tc} ticks vs median {median_ticks} ({ratio:.1%})",
                    })

    return {
        "symbol": symbol,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reference_stats": {
            "median_ticks_per_hour": median_ticks,
            "median_price_range_per_hour": round(median_range, 8) if median_range else None,
            "hours_analyzed": len(tick_counts),
        },
        "anomalies_found": len(anomalies),
        "anomalies": anomalies,
    }
