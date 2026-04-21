"""Target labels for calibration experiment — PRD-300 / CC-2a.

Builds four candidate target series aligned on canonical FOMC dates:
- A: FedWatch surprise (bps) — already in master table
- D: real_rate_differential change [T, T+5bd]
- E: EUR/USD log return [T, T+5bd]
- F: EUR/USD log return [T, T+21bd]

EUR/USD sourced from FRED series DEXUSEU (daily, USD per EUR). Cached locally.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DEFAULT_EURUSD_CACHE = Path("data/market_pricing/eurusd_daily.parquet")
FRED_SERIES_EURUSD = "DEXUSEU"
DEFAULT_EURUSD_START = datetime(2021, 1, 1)


def _get_fred_client():
    """Lazy-load Fred client; same pattern as market_pricing.us_rates."""
    from fredapi import Fred  # local import — avoids hard dependency at module load

    load_dotenv(Path(".env"))
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key or api_key.startswith("REPLACE_") or api_key == "your_fred_api_key_here":
        raise ValueError(
            "FRED_API_KEY nu e configurat în .env. Vezi .env.example pentru template."
        )
    return Fred(api_key=api_key)


def fetch_eurusd_daily(
    start: datetime = DEFAULT_EURUSD_START,
    end: Optional[datetime] = None,
    cache_path: Path = DEFAULT_EURUSD_CACHE,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Fetch DEXUSEU from FRED, cache to parquet.

    Returns DataFrame indexed on date with 'eurusd_close' column (float64).
    """
    cache_path = Path(cache_path)
    if use_cache and cache_path.exists():
        df = pd.read_parquet(cache_path)
        logger.info("EUR/USD loaded from cache: %s (%d rows)", cache_path, len(df))
        return df

    fred = _get_fred_client()
    raw = fred.get_series(FRED_SERIES_EURUSD, observation_start=start, observation_end=end)
    raw = raw.dropna().astype("float64")
    df = pd.DataFrame({"eurusd_close": raw.values}, index=raw.index)
    df.index = pd.to_datetime(df.index).normalize()
    df.index.name = "date"

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path)
    logger.info("EUR/USD fetched from FRED and cached: %s (%d rows)", cache_path, len(df))
    return df


def compute_target_A_fedwatch_surprise(master_table: pd.DataFrame) -> pd.Series:
    """Target A: FedWatch surprise (bps). Pass-through from master table."""
    return master_table["fedwatch_surprise_bps"].rename("target_A_fedwatch_surprise")


def _forward_business_day(t: pd.Timestamp, n_business_days: int) -> pd.Timestamp:
    return (pd.Timestamp(t).normalize() + pd.offsets.BusinessDay(n_business_days)).normalize()


def _lookup_or_walk_forward(series: pd.Series, target: pd.Timestamp, max_walk: int = 5) -> tuple[float, Optional[pd.Timestamp]]:
    """Return (value, actual_date_used) — walks forward if target missing/NaN."""
    cur = target
    val = series.get(cur, float("nan"))
    walks = 0
    while pd.isna(val) and walks < max_walk:
        cur = cur + pd.offsets.BusinessDay(1)
        val = series.get(cur, float("nan"))
        walks += 1
    if pd.isna(val):
        return float("nan"), None
    return float(val), cur


def compute_target_D_real_rate_diff_change(
    master_table: pd.DataFrame,
    rrd_daily: pd.DataFrame,
    window_days: int = 5,
) -> pd.Series:
    """Target D: real_rate_differential change over [T, T+5bd]."""
    rrd = rrd_daily.copy()
    rrd["date"] = pd.to_datetime(rrd["date"]).dt.normalize()
    series = rrd.set_index("date")["real_rate_differential"].sort_index()

    out = {}
    for T in master_table.index:
        T_norm = pd.Timestamp(T).normalize()
        v_t, _ = _lookup_or_walk_forward(series, T_norm)
        v_end, _ = _lookup_or_walk_forward(series, _forward_business_day(T_norm, window_days))
        if pd.isna(v_t) or pd.isna(v_end):
            out[T] = float("nan")
        else:
            out[T] = v_end - v_t
    return pd.Series(out, name="target_D_rrd_change_5d")


def compute_target_E_eurusd_5d_return(
    master_table: pd.DataFrame,
    eurusd_daily: pd.DataFrame,
    window_days: int = 5,
) -> pd.Series:
    """Target E: EUR/USD log return over [T, T+5bd]. Positive = EUR up / USD down."""
    eu = eurusd_daily.copy()
    if not isinstance(eu.index, pd.DatetimeIndex):
        eu.index = pd.to_datetime(eu.index)
    eu.index = eu.index.normalize()
    series = eu["eurusd_close"].sort_index()

    out = {}
    for T in master_table.index:
        T_norm = pd.Timestamp(T).normalize()
        v_t, _ = _lookup_or_walk_forward(series, T_norm)
        v_end, _ = _lookup_or_walk_forward(series, _forward_business_day(T_norm, window_days))
        if pd.isna(v_t) or pd.isna(v_end) or v_t <= 0 or v_end <= 0:
            out[T] = float("nan")
        else:
            out[T] = float(np.log(v_end / v_t))
    return pd.Series(out, name="target_E_eurusd_5d")


def compute_target_F_eurusd_21d_return(
    master_table: pd.DataFrame,
    eurusd_daily: pd.DataFrame,
    window_days: int = 21,
) -> pd.Series:
    """Target F: EUR/USD log return over [T, T+21bd] (~1 calendar month)."""
    s = compute_target_E_eurusd_5d_return(master_table, eurusd_daily, window_days=window_days)
    return s.rename("target_F_eurusd_21d")


def build_targets_table(
    master_table_path: Path = Path("data/divergence/calibration_features.parquet"),
    rrd_path: Path = Path("data/market_pricing/real_rate_differential.parquet"),
    output_path: Path = Path("data/divergence/targets.parquet"),
    eurusd_cache_path: Path = DEFAULT_EURUSD_CACHE,
) -> pd.DataFrame:
    """Build all 4 targets aligned on canonical FOMC meeting dates."""
    master = pd.read_parquet(master_table_path)
    rrd = pd.read_parquet(rrd_path)
    eurusd = fetch_eurusd_daily(cache_path=eurusd_cache_path)

    tA = compute_target_A_fedwatch_surprise(master)
    tD = compute_target_D_real_rate_diff_change(master, rrd, window_days=5)
    tE = compute_target_E_eurusd_5d_return(master, eurusd, window_days=5)
    tF = compute_target_F_eurusd_21d_return(master, eurusd, window_days=21)

    targets = pd.DataFrame(
        {
            "target_A_fedwatch_surprise": tA,
            "target_D_rrd_change_5d": tD,
            "target_E_eurusd_5d": tE,
            "target_F_eurusd_21d": tF,
        },
        index=master.index,
    )
    targets.index.name = "meeting_date"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    targets.to_parquet(output_path)
    logger.info("Targets table persisted: %s (%d rows)", output_path, len(targets))
    return targets
