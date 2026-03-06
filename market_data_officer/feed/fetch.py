"""Dukascopy bi5 fetch layer — downloads hourly tick archives."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from .config import DUKASCOPY_BASE_URL, RAW_DIR

# Dukascopy requires a browser-like User-Agent to avoid Cloudflare 403 blocks
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


def build_bi5_url(symbol: str, hour_dt: datetime) -> str:
    """Build the Dukascopy bi5 URL for a given symbol and hour.

    Dukascopy uses zero-based month indexing (January = 00).
    """
    month_zero = hour_dt.month - 1
    return (
        f"{DUKASCOPY_BASE_URL}/{symbol}/"
        f"{hour_dt.year}/{month_zero:02d}/{hour_dt.day:02d}/"
        f"{hour_dt.hour:02d}h_ticks.bi5"
    )


def fetch_bi5(
    symbol: str,
    hour_dt: datetime,
    save_raw: bool = False,
    raw_dir: Optional[Path] = None,
    timeout: int = 30,
) -> bytes:
    """Fetch a bi5 tick archive for the given symbol and hour.

    Returns raw bytes on success, empty bytes on HTTP error or empty response.
    Never raises on network/HTTP errors — returns b"" instead.
    """
    if hour_dt.tzinfo is None:
        raise ValueError("hour_dt must be timezone-aware (UTC)")

    url = build_bi5_url(symbol, hour_dt)

    try:
        resp = requests.get(url, timeout=timeout, headers=_HEADERS)
    except requests.exceptions.SSLError:
        # Fallback: retry without SSL verification (some environments have
        # DNS/certificate mismatches with Cloudflare-fronted origins)
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(url, timeout=timeout, headers=_HEADERS, verify=False)
        except requests.RequestException as exc:
            print(f"[fetch] network error for {url}: {exc}")
            return b""
    except requests.RequestException as exc:
        print(f"[fetch] network error for {url}: {exc}")
        return b""

    if resp.status_code == 404 or resp.status_code >= 400:
        return b""

    data = resp.content
    if not data:
        return b""

    if save_raw:
        out_dir = (raw_dir or RAW_DIR) / symbol
        month_zero = hour_dt.month - 1
        file_dir = out_dir / str(hour_dt.year) / f"{month_zero:02d}" / f"{hour_dt.day:02d}"
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / f"{hour_dt.hour:02d}h_ticks.bi5"
        file_path.write_bytes(data)

    return data
