"""AutoTune Data Loader — fetch and cache 1H XAUUSD OHLCV via yFinance.

Returns raw pandas DataFrames. Format adaptation to lens input is the
evaluator's responsibility.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
PARQUET_PATH = DATA_DIR / "XAUUSD_1H.parquet"

# Ticker priority: GC=F first, XAUUSD=X fallback
PRIMARY_TICKER = "GC=F"
FALLBACK_TICKER = "XAUUSD=X"

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def fetch_ohlcv(refresh: bool = False) -> tuple[pd.DataFrame, str]:
    """Fetch 1H OHLCV data from yFinance or load from cache.

    Returns:
        (DataFrame with columns [timestamp, open, high, low, close, volume],
         ticker_used)
    """
    if not refresh and PARQUET_PATH.exists():
        df = pd.read_parquet(PARQUET_PATH)
        if len(df) > 0:
            # Determine ticker from metadata if stored, else unknown
            ticker = _read_cached_ticker()
            logger.info("Loaded %d bars from cache: %s", len(df), PARQUET_PATH)
            return df, ticker

    import yfinance as yf

    df, ticker = None, None

    for t in [PRIMARY_TICKER, FALLBACK_TICKER]:
        logger.info("Trying ticker %s ...", t)
        try:
            tk = yf.Ticker(t)
            raw = tk.history(period="max", interval="1h")
            if raw is not None and len(raw) > 0:
                df = _normalise(raw)
                ticker = t
                logger.info("Fetched %d bars from %s", len(df), t)
                break
            else:
                logger.warning("Ticker %s returned no data", t)
        except Exception as exc:
            logger.warning("Ticker %s failed: %s", t, exc)

    if df is None or len(df) == 0:
        raise RuntimeError(
            f"Both tickers ({PRIMARY_TICKER}, {FALLBACK_TICKER}) failed to "
            "provide 1H OHLCV data. Cannot proceed."
        )

    # Save to parquet
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PARQUET_PATH, index=False)
    _write_cached_ticker(ticker)
    logger.info("Cached %d bars to %s", len(df), PARQUET_PATH)

    return df, ticker


def _normalise(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalise yFinance DataFrame to standard columns."""
    df = raw.copy()
    df = df.reset_index()

    # yFinance uses 'Datetime' or 'Date' as index name
    time_col = None
    for col in df.columns:
        if col.lower() in ("datetime", "date", "index"):
            time_col = col
            break
    if time_col is None:
        time_col = df.columns[0]

    df = df.rename(columns={
        time_col: "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    # Ensure timestamp is timezone-naive UTC
    if hasattr(df["timestamp"].dtype, "tz") and df["timestamp"].dt.tz is not None:
        df["timestamp"] = df["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None)

    # Keep only required columns
    df = df[REQUIRED_COLUMNS].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Drop rows with any NaN in OHLCV
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

    return df


def validate_coverage(df: pd.DataFrame) -> tuple[int, int, float]:
    """Validate bar coverage using data-derived trading calendar.

    Returns (actual_bars, expected_bars, coverage_ratio).
    Raises RuntimeError if coverage < 95%.
    """
    if len(df) == 0:
        raise RuntimeError("Empty DataFrame — cannot validate coverage")

    dates = pd.to_datetime(df["timestamp"]).dt.date
    bars_per_day = dates.value_counts()

    # Filter to sufficiently populated days (>= 50% of modal)
    modal_bpd = int(bars_per_day.mode().iloc[0])
    threshold = modal_bpd * 0.5
    populated_days = bars_per_day[bars_per_day >= threshold]

    if len(populated_days) == 0:
        raise RuntimeError("No sufficiently populated trading days found")

    median_bpd = populated_days.median()
    expected = int(median_bpd * len(populated_days))
    actual = int(populated_days.sum())
    coverage = actual / expected if expected > 0 else 0.0

    logger.info(
        "Coverage: %d actual / %d expected = %.3f (populated days: %d, median bpd: %.0f)",
        actual, expected, coverage, len(populated_days), median_bpd,
    )

    if coverage < 0.95:
        raise RuntimeError(
            f"Bar coverage {coverage:.3f} < 0.95 threshold. "
            f"Actual: {actual}, Expected: {expected}. Halting."
        )

    return actual, expected, coverage


def slice_by_date(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Slice DataFrame by date range (inclusive)."""
    ts = pd.to_datetime(df["timestamp"])
    mask = (ts >= pd.Timestamp(start)) & (ts <= pd.Timestamp(end + " 23:59:59"))
    return df[mask].reset_index(drop=True)


def _ticker_meta_path() -> Path:
    return DATA_DIR / ".ticker_meta.json"


def _read_cached_ticker() -> str:
    p = _ticker_meta_path()
    if p.exists():
        meta = json.loads(p.read_text())
        return meta.get("ticker", "unknown")
    return "unknown"


def _write_cached_ticker(ticker: str) -> None:
    p = _ticker_meta_path()
    p.write_text(json.dumps({"ticker": ticker}))


def main():
    parser = argparse.ArgumentParser(description="AutoTune Data Loader")
    parser.add_argument("--refresh", action="store_true", help="Force re-fetch from yFinance")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    df, ticker = fetch_ohlcv(refresh=args.refresh)
    actual, expected, coverage = validate_coverage(df)

    print(f"Ticker: {ticker}")
    print(f"Rows: {len(df)}")
    print(f"Range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    print(f"Coverage: {actual}/{expected} = {coverage:.3f}")
    print(f"Cached at: {PARQUET_PATH}")


if __name__ == "__main__":
    main()
