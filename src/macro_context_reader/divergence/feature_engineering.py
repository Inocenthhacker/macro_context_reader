"""CC-2a-v3 feature engineering — derivative features for improved classification.

Rationale (theory-driven, committed BEFORE v3 experiment runs):

1. MOMENTUM (Macrosynergy 2024 — "information change framing"):
   Level alone doesn't predict; direction of change does. If NLP score keeps
   getting more hawkish meeting over meeting, that's a stronger signal than
   any single level.

2. ACCELERATION (Scheffer et al. 2009 — Early Warning Signals):
   Regime transitions are preceded by acceleration (second derivative) in
   key indicators, not by threshold crossings alone.

3. DIVERGENCE (Djourelova et al. 2025 — communication coherence):
   Discordance between sources (Fed rhetoric vs market pricing vs prior
   communication) is itself a signal. When Fed says one thing but market
   prices another, surprise is likely.

All derivative features require T-1 (previous meeting), so first meeting(s)
produce NaN. Acceleration requires T-2.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


ENGINEERED_FEATURES: list[str] = [
    # Momentum (3)
    "statement_momentum",
    "minutes_lag_momentum",
    "real_rate_diff_momentum_21bd",
    # Acceleration (2)
    "statement_acceleration",
    "cleveland_acceleration",
    # Divergence (2)
    "nlp_vs_fedwatch_divergence",
    "statement_vs_minutes_lag_divergence",
]


# ============================================================
# Momentum features
# ============================================================


def compute_statement_momentum(master_table: pd.DataFrame) -> pd.Series:
    """statement_momentum(T) = statement_ensemble_net(T) - statement_ensemble_net(T-1).

    Meeting-over-meeting change in Fed statement rhetoric.
    Positive = more hawkish than previous meeting.
    NaN for first meeting.
    """
    series = master_table["statement_ensemble_net"].diff()
    series.name = "statement_momentum"
    return series


def compute_minutes_lag_momentum(master_table: pd.DataFrame) -> pd.Series:
    """minutes_lag_momentum(T) = minutes_lag_ensemble_net(T) - minutes_lag_ensemble_net(T-1).

    Change in retrospective minutes tone. NaN for first two meetings
    (minutes_lag itself is NaN for first meeting).
    """
    series = master_table["minutes_lag_ensemble_net"].diff()
    series.name = "minutes_lag_momentum"
    return series


def compute_real_rate_diff_momentum(
    master_table: pd.DataFrame,
    rrd_daily_path: Path = Path("data/market_pricing/real_rate_differential.parquet"),
    lookback_bdays: int = 21,
) -> pd.Series:
    """real_rate_diff_momentum_21bd(T) = real_rate_diff_5y(T-1bd) - real_rate_diff_5y(T-1bd-21bd).

    One-month trend in real rate differential, measured at T-1 business day
    (pre-announcement, matching master_alignment convention).

    Uses daily rrd parquet for T-1bd-21bd lookback (master table has only
    T-1bd snapshot).
    """
    rrd = pd.read_parquet(rrd_daily_path)
    rrd = rrd[["date", "real_rate_differential"]].copy()
    rrd["date"] = pd.to_datetime(rrd["date"])
    rrd = rrd.set_index("date").sort_index()
    # Re-index to full business-day calendar to support positional lookback.
    bday_idx = pd.bdate_range(rrd.index.min(), rrd.index.max())
    rrd_bd = rrd.reindex(bday_idx).ffill()

    meeting_dates = pd.DatetimeIndex(master_table.index)
    source_dates = master_table["real_rate_diff_source_date"]
    current_vals = master_table["real_rate_diff_5y"].astype(float)

    lookback_vals = []
    for src_date in source_dates:
        if pd.isna(src_date):
            lookback_vals.append(np.nan)
            continue
        src_ts = pd.Timestamp(src_date)
        try:
            pos = rrd_bd.index.get_indexer([src_ts], method="ffill")[0]
        except Exception:
            pos = -1
        if pos < 0:
            lookback_vals.append(np.nan)
            continue
        lb_pos = pos - lookback_bdays
        if lb_pos < 0:
            lookback_vals.append(np.nan)
            continue
        lookback_vals.append(float(rrd_bd["real_rate_differential"].iloc[lb_pos]))

    lookback_series = pd.Series(lookback_vals, index=meeting_dates)
    out = current_vals.values - lookback_series.values
    series = pd.Series(out, index=meeting_dates, name="real_rate_diff_momentum_21bd")
    return series


# ============================================================
# Acceleration features
# ============================================================


def compute_statement_acceleration(
    master_table: pd.DataFrame,
    statement_momentum: pd.Series,
) -> pd.Series:
    """statement_acceleration(T) = statement_momentum(T) - statement_momentum(T-1).

    Second derivative — is Fed rhetoric accelerating in one direction?
    Critical for early warning of regime change (Scheffer 2009).
    NaN for first two meetings.
    """
    series = statement_momentum.diff()
    series.name = "statement_acceleration"
    return series


def compute_cleveland_acceleration(master_table: pd.DataFrame) -> pd.Series:
    """cleveland_acceleration(T) = cleveland_national_score(T)
                                   - 2*cleveland_national_score(T-1)
                                   + cleveland_national_score(T-2).

    Discrete second derivative of economic sentiment.
    NaN for first two meetings.
    """
    x = master_table["cleveland_national_score"].astype(float)
    series = x - 2.0 * x.shift(1) + x.shift(2)
    series.name = "cleveland_acceleration"
    return series


# ============================================================
# Divergence features
# ============================================================


def compute_nlp_vs_fedwatch_divergence(master_table: pd.DataFrame) -> pd.Series:
    """nlp_vs_fedwatch_divergence(T)
         = statement_ensemble_net(T)
           - sign(fedwatch_implied_change_bps(T)) * abs(fedwatch_implied_change_bps(T)) / 25

    Intuition: NLP score is in [-0.5, +0.5]. FedWatch implied change is in bps.
    Normalize fedwatch to comparable scale: divide by 25 (one rate move size).
    sign(fedwatch) * abs(fedwatch)/25 yields ~[-1, +1] proxy for "market-implied
    hawkishness."

    Large positive divergence = Fed more hawkish than market priced.
    Large negative divergence = Fed more dovish than market priced.

    This is a PRIOR to the surprise outcome, computed from pre-meeting features.
    """
    nlp = master_table["statement_ensemble_net"].astype(float)
    fw = master_table["fedwatch_implied_change_bps"].astype(float)
    fw_norm = np.sign(fw) * np.abs(fw) / 25.0
    series = nlp - fw_norm
    series.name = "nlp_vs_fedwatch_divergence"
    return series


def compute_statement_vs_minutes_lag_divergence(master_table: pd.DataFrame) -> pd.Series:
    """statement_vs_minutes_lag_divergence(T)
         = statement_ensemble_net(T) - minutes_lag_ensemble_net(T).

    Fed NOW (statement) vs Fed 6 WEEKS AGO (minutes from prior meeting,
    freshly released). Large positive = Fed has become more hawkish since
    previous meeting's internal discussions.
    NaN for first meeting (no minutes_lag).
    """
    statement = master_table["statement_ensemble_net"].astype(float)
    minutes_lag = master_table["minutes_lag_ensemble_net"].astype(float)
    series = statement - minutes_lag
    series.name = "statement_vs_minutes_lag_divergence"
    return series


# ============================================================
# Builder
# ============================================================


def build_features_v3_table(
    master_table_path: Path = Path("data/divergence/calibration_features.parquet"),
    rrd_path: Path = Path("data/market_pricing/real_rate_differential.parquet"),
    output_path: Path = Path("data/divergence/calibration_features_v3.parquet"),
) -> pd.DataFrame:
    """Build extended feature set: 11 original + 7 engineered = 18 features.

    Returns DataFrame indexed on meeting_date with:
      - All columns from master_table (calibration_features.parquet)
      - + 7 ENGINEERED_FEATURES columns

    Persist to output_path.
    """
    master = pd.read_parquet(master_table_path).sort_index()

    statement_mom = compute_statement_momentum(master)
    minutes_mom = compute_minutes_lag_momentum(master)
    rrd_mom = compute_real_rate_diff_momentum(master, rrd_daily_path=rrd_path)
    statement_accel = compute_statement_acceleration(master, statement_mom)
    cleveland_accel = compute_cleveland_acceleration(master)
    nlp_fw_div = compute_nlp_vs_fedwatch_divergence(master)
    stmt_minutes_div = compute_statement_vs_minutes_lag_divergence(master)

    engineered = pd.DataFrame(
        {
            "statement_momentum": statement_mom,
            "minutes_lag_momentum": minutes_mom,
            "real_rate_diff_momentum_21bd": rrd_mom,
            "statement_acceleration": statement_accel,
            "cleveland_acceleration": cleveland_accel,
            "nlp_vs_fedwatch_divergence": nlp_fw_div,
            "statement_vs_minutes_lag_divergence": stmt_minutes_div,
        },
        index=master.index,
    )

    # Order: original columns first, then 7 engineered.
    out = pd.concat([master, engineered[ENGINEERED_FEATURES]], axis=1)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path)
    logger.info(
        "Features v3 table persisted: %s (shape=%s, engineered=%d)",
        output_path,
        out.shape,
        len(ENGINEERED_FEATURES),
    )
    return out
