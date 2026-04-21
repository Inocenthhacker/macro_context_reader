"""CC-2a-v2 targets — classification labels for dual-signal architecture.

Two independent targets operating on different timeframes:
- target_surprise_class: FedWatch surprise direction (short-term reaction signal)
- target_regime_class: EUR/USD regime 42-day (long-term macro direction signal)

Both labeled as {-1, 0, +1} with an explicit neutral zone to avoid forcing
predictions in ambiguous conditions (matches real trading workflow).

Methodology references: Macrosynergy 2024 "information change" framing for
short-horizon policy-surprise signals; Scheffer 2009 regime-concept framing for
multi-week structural FX direction.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from macro_context_reader.divergence.targets import (
    DEFAULT_EURUSD_CACHE,
    fetch_eurusd_daily,
)

logger = logging.getLogger(__name__)

REGIME_WINDOW_DAYS: int = 42  # ~2 calendar months, standard macro FX horizon
REGIME_THRESHOLD_PCT: float = 0.02  # 2% = meaningful EUR/USD structural move (~200 pips)
SURPRISE_THRESHOLD_BPS: float = 2.0  # < 2bps absolute = noise, ignore

logger.info(
    "CC-2a-v2 targets — SURPRISE_THRESHOLD_BPS=%.2f, "
    "REGIME_WINDOW_DAYS=%d bd, REGIME_THRESHOLD_PCT=%.2f%%",
    SURPRISE_THRESHOLD_BPS,
    REGIME_WINDOW_DAYS,
    REGIME_THRESHOLD_PCT * 100,
)


def compute_target_surprise_class(
    master_table: pd.DataFrame,
    threshold_bps: float = SURPRISE_THRESHOLD_BPS,
) -> pd.Series:
    """Discretize fedwatch_surprise_bps into {-1, 0, +1}.

    Returns:
      +1 if surprise >= +threshold (Fed more hawkish than priced)
      -1 if surprise <= -threshold (Fed more dovish than priced)
       0 if |surprise| < threshold (neutral / priced-in)

    NaN in input → NaN (pd.NA) in output. Output dtype is Int64 (nullable).

    Rationale: surprise below ~2bps absolute is market noise; don't force a
    direction signal when the Fed basically met expectations.
    """
    s = master_table["fedwatch_surprise_bps"]
    out = pd.Series(pd.NA, index=s.index, dtype="Int64", name="target_surprise_class")
    valid = s.notna()
    pos = valid & (s >= threshold_bps)
    neg = valid & (s <= -threshold_bps)
    zero = valid & ~pos & ~neg
    out.loc[pos] = 1
    out.loc[neg] = -1
    out.loc[zero] = 0
    return out


def _forward_business_day(t: pd.Timestamp, n_business_days: int) -> pd.Timestamp:
    return (pd.Timestamp(t).normalize() + pd.offsets.BusinessDay(n_business_days)).normalize()


def _lookup_or_walk_forward(
    series: pd.Series,
    target: pd.Timestamp,
    max_walk: int = 5,
) -> tuple[float, Optional[pd.Timestamp]]:
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


def _compute_regime_details(
    master_table: pd.DataFrame,
    eurusd_daily: pd.DataFrame,
    window_days: int = REGIME_WINDOW_DAYS,
    threshold_pct: float = REGIME_THRESHOLD_PCT,
) -> pd.DataFrame:
    """Internal helper — computes class, raw_pct, source_date in one pass.

    NaN preserved for meetings whose T+window_days business-day target exceeds
    the available EUR/USD series.
    """
    eu = eurusd_daily.copy()
    if not isinstance(eu.index, pd.DatetimeIndex):
        eu.index = pd.to_datetime(eu.index)
    eu.index = eu.index.normalize()
    series = eu["eurusd_close"].sort_index()
    last_available = series.index.max()

    cls = pd.Series(pd.NA, index=master_table.index, dtype="Int64", name="target_regime_class")
    pct = pd.Series(np.nan, index=master_table.index, dtype="float64", name="target_regime_raw_pct")
    src = pd.Series(pd.NaT, index=master_table.index, dtype="datetime64[ns]", name="target_regime_source_date")

    for T in master_table.index:
        T_norm = pd.Timestamp(T).normalize()
        v_t, _ = _lookup_or_walk_forward(series, T_norm)
        if pd.isna(v_t) or v_t <= 0:
            continue
        target_end = _forward_business_day(T_norm, window_days)
        if target_end > last_available:
            continue  # window exceeds available data — NaN
        v_end, actual_end = _lookup_or_walk_forward(series, target_end)
        if pd.isna(v_end) or actual_end is None:
            continue
        change = (v_end - v_t) / v_t
        pct.loc[T] = change
        src.loc[T] = actual_end
        if change >= threshold_pct:
            cls.loc[T] = 1
        elif change <= -threshold_pct:
            cls.loc[T] = -1
        else:
            cls.loc[T] = 0

    return pd.DataFrame(
        {
            "target_regime_class": cls,
            "target_regime_raw_pct": pct,
            "target_regime_source_date": src,
        }
    )


def compute_target_regime_class(
    master_table: pd.DataFrame,
    eurusd_daily: pd.DataFrame,
    window_days: int = REGIME_WINDOW_DAYS,
    threshold_pct: float = REGIME_THRESHOLD_PCT,
) -> pd.Series:
    """Discretize EUR/USD structural move over [T, T+window business days].

    For each FOMC date T:
      pct_change = (close(T+window_bd) - close(T)) / close(T)

    Returns {-1, 0, +1} or NaN:
      +1 if pct_change >= +threshold (bullish EUR regime — USD weak)
      -1 if pct_change <= -threshold (bearish EUR regime — USD strong)
       0 if |pct_change| < threshold (range / unclear regime)
      NaN if T+window exceeds available EUR/USD data

    Rationale: 42-bd window (~2 months) captures typical macro leg duration.
    2% threshold filters noise; moves under 2% are not structural signals.
    """
    return _compute_regime_details(
        master_table,
        eurusd_daily,
        window_days=window_days,
        threshold_pct=threshold_pct,
    )["target_regime_class"]


def build_targets_v2_table(
    master_table_path: Path = Path("data/divergence/calibration_features.parquet"),
    eurusd_path: Path = DEFAULT_EURUSD_CACHE,
    output_path: Path = Path("data/divergence/targets_v2.parquet"),
) -> pd.DataFrame:
    """Build classification targets aligned on canonical FOMC meeting dates.

    Columns:
      - target_surprise_class: {-1, 0, +1} or NaN (Int64)
      - target_regime_class: {-1, 0, +1} or NaN (Int64)
      - target_surprise_raw: original bps (float, for diagnostics)
      - target_regime_raw_pct: original % change (float, for diagnostics)
      - target_regime_source_date: actual T+42bd date used (datetime64[ns])

    Index: meeting_date (DatetimeIndex).
    """
    master = pd.read_parquet(master_table_path)
    eurusd = fetch_eurusd_daily(cache_path=eurusd_path)

    surprise_cls = compute_target_surprise_class(master)
    surprise_raw = master["fedwatch_surprise_bps"].astype("float64").rename("target_surprise_raw")
    regime = _compute_regime_details(master, eurusd)

    out = pd.DataFrame(
        {
            "target_surprise_class": surprise_cls,
            "target_regime_class": regime["target_regime_class"],
            "target_surprise_raw": surprise_raw,
            "target_regime_raw_pct": regime["target_regime_raw_pct"],
            "target_regime_source_date": regime["target_regime_source_date"],
        },
        index=master.index,
    )
    out.index.name = "meeting_date"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path)
    logger.info("Targets v2 table persisted: %s (%d rows)", output_path, len(out))
    return out
