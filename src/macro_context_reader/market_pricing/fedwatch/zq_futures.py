"""
Fed Funds Futures (ZQ) historical price ingestion from Databento.

Data source: CME Globex MDP 3.0 (GLBX.MDP3) via Databento Historical API
Coverage: 2010-06-07 → present (free tier dataset limitation)
Contract: ZQ = 30-Day Federal Funds Futures (CBOT)
Symbology: continuous front-month chains ZQ.c.0 (front) through ZQ.c.8 (9 months ahead)

These 9 continuous series together provide the input needed by pyfedwatch to
reconstruct FOMC rate change probabilities at any historical watch_date.

Price convention:
  Futures price = 100 - implied average Fed Funds rate for the contract month
  Example: close = 94.87 → implied rate = 5.13%

Persistence: one parquet per continuous chain in data/market_pricing/zq_futures/
Schema per parquet:
  index: DatetimeIndex (daily, timezone-naive UTC)
  columns: open, high, low, close, volume (all float64 except volume int64)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Configuration constants
DATASET_ID = "GLBX.MDP3"
ROOT_SYMBOL = "ZQ"
FRONT_MONTHS = 9  # ZQ.c.0 through ZQ.c.8
SCHEMA = "ohlcv-1d"
EARLIEST_AVAILABLE = "2010-06-07"  # Verified via probe — Databento GLBX.MDP3 start

# Output path
_REPO_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_DIR = _REPO_ROOT / "data" / "market_pricing" / "zq_futures"


def _get_client():
    """Initialize Databento client from .env; fail loudly if key missing."""
    load_dotenv()
    api_key = os.getenv("DATABENTO_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DATABENTO_API_KEY not found in environment. "
            "Add to .env or shell environment before calling zq_futures functions."
        )
    import databento as db

    return db.Historical(api_key)


def _continuous_symbol(n: int) -> str:
    """Format continuous front-month symbol: ZQ.c.0 ... ZQ.c.8."""
    if not 0 <= n < FRONT_MONTHS:
        raise ValueError(f"n must be in [0, {FRONT_MONTHS}), got {n}")
    return f"{ROOT_SYMBOL}.c.{n}"


def fetch_zq_chain(
    n: int,
    start: str = EARLIEST_AVAILABLE,
    end: str | None = None,
) -> pd.DataFrame:
    """
    Fetch one continuous ZQ chain (ZQ.c.{n}) as daily OHLCV.

    Args:
        n: chain index 0..8 (0 = front-month, 8 = 9 months ahead)
        start: ISO date (default: 2010-06-07, earliest available)
        end: ISO date (default: today)

    Returns:
        DataFrame indexed by date (daily), columns [open, high, low, close, volume]
    """
    symbol = _continuous_symbol(n)
    if end is None:
        end = pd.Timestamp.today().normalize().strftime("%Y-%m-%d")

    logger.info("Fetching %s from %s to %s (schema=%s)", symbol, start, end, SCHEMA)
    client = _get_client()

    data = client.timeseries.get_range(
        dataset=DATASET_ID,
        symbols=[symbol],
        schema=SCHEMA,
        start=start,
        end=end,
        stype_in="continuous",
    )
    df = data.to_df()

    if len(df) == 0:
        raise RuntimeError(f"No data returned for {symbol} {start}→{end}")

    # Normalize schema: keep only OHLCV columns
    cols_wanted = ["open", "high", "low", "close", "volume"]
    missing = set(cols_wanted) - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing expected columns in {symbol} data: {missing}")
    df = df[cols_wanted].copy()

    # Ensure datetime index, sorted, no timezone
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    df.index = pd.to_datetime(df.index).normalize()
    df.index.name = "date"
    df = df.sort_index()

    # Deduplicate (defensive)
    df = df[~df.index.duplicated(keep="last")]

    # Dtypes
    for c in ["open", "high", "low", "close"]:
        df[c] = df[c].astype("float64")
    df["volume"] = df["volume"].astype("int64")

    logger.info("%s: %d rows, %s → %s", symbol, len(df), df.index.min().date(), df.index.max().date())
    return df


def persist_zq_chain(n: int, df: pd.DataFrame) -> Path:
    """Save a single chain DataFrame to data/market_pricing/zq_futures/ZQ.c.{n}.parquet."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{_continuous_symbol(n)}.parquet"
    df.to_parquet(path, engine="pyarrow", compression="snappy", index=True)
    logger.info("Wrote %s (%.1f KB)", path, path.stat().st_size / 1024)
    return path


def load_zq_chain(n: int) -> pd.DataFrame:
    """Load a persisted chain from parquet."""
    path = OUTPUT_DIR / f"{_continuous_symbol(n)}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing chain parquet: {path}. Run fetch_all_chains() first.")
    return pd.read_parquet(path)


def fetch_all_chains(
    start: str = EARLIEST_AVAILABLE,
    end: str | None = None,
    persist: bool = True,
) -> dict[int, pd.DataFrame]:
    """
    Fetch all 9 continuous ZQ chains and optionally persist each to parquet.

    Returns:
        dict mapping chain index (0..8) to DataFrame
    """
    result: dict[int, pd.DataFrame] = {}
    for n in range(FRONT_MONTHS):
        df = fetch_zq_chain(n, start=start, end=end)
        if persist:
            persist_zq_chain(n, df)
        result[n] = df
    return result


def load_all_chains() -> dict[int, pd.DataFrame]:
    """Load all 9 persisted chains from parquet cache."""
    return {n: load_zq_chain(n) for n in range(FRONT_MONTHS)}


def implied_rate_from_price(close_price: float) -> float:
    """
    Convert ZQ settlement price to implied Fed Funds rate.

    Formula: implied_rate = 100 - close_price
    Example: close = 94.87 → implied rate = 5.13%
    """
    return 100.0 - close_price
