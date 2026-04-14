"""Surprise signal — divergence between NLP Fed stance and market-implied path.

Three methods implemented simultaneously (selection deferred to PRD-300 backtesting):

1. binary: surprise = nlp_score - prob_hike. Naive baseline; loses magnitude.

2. expected_change (Gürkaynak, Sack, Swanson 2005): difference of expected rate
   changes in basis points. Market expected change = Σ (bucket_midpoint - current_rate)
   × probability. NLP expected change = nlp_score × calibration_bps.

3. kl_divergence (Kullback-Leibler): full-distribution distance. Market distribution
   from buckets; NLP distribution synthesized as discretized Gaussian centered on
   current_rate + nlp_score × calibration_bps with fixed sigma.

Refs:
- Gürkaynak, Sack, Swanson (2005). Int. J. Central Banking 1(1):55-93.
- Kullback & Leibler (1951). Annals Math. Stat. 22:79-86.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Literal, Optional

import numpy as np
import pandas as pd

from .loader import load_fedwatch_history

SurpriseMethod = Literal["binary", "expected_change", "kl_divergence"]

# 1 unit of NLP hawkish ≈ 25bps (one standard FOMC move).
# Will be replaced with OLS-calibrated value in PRD-300 from ~80 historical events.
DEFAULT_NLP_CALIBRATION_BPS = 25.0
DEFAULT_NLP_SIGMA_BPS = 12.5


def _get_fred_client(api_key: Optional[str] = None):
    from dotenv import load_dotenv
    from fredapi import Fred

    load_dotenv()
    key = api_key or os.environ.get("FRED_API_KEY")
    if not key or key.startswith("REPLACE_") or key == "your_fred_api_key_here":
        raise ValueError(
            "FRED_API_KEY not configured. Required for Fed Funds target rate lookup."
        )
    return Fred(api_key=key)


def _fetch_current_fed_funds_midpoint(
    as_of_date: date, api_key: Optional[str] = None
) -> float:
    """Fetch Fed Funds target rate midpoint (bps) from FRED for a given date.

    Uses DFEDTARU/DFEDTARL (upper/lower bounds, daily, 2008-present), forward-filled
    since the target rate is stepped (constant between FOMC meetings).
    """
    fred = _get_fred_client(api_key)
    target_iso = as_of_date.strftime("%Y-%m-%d")
    lookback_start = (pd.Timestamp(as_of_date) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")

    upper = fred.get_series("DFEDTARU", observation_start=lookback_start, observation_end=target_iso)
    lower = fred.get_series("DFEDTARL", observation_start=lookback_start, observation_end=target_iso)

    if len(upper.dropna()) == 0 or len(lower.dropna()) == 0:
        raise ValueError(f"No Fed Funds target data available for {target_iso}")

    upper_val = upper.dropna().iloc[-1]
    lower_val = lower.dropna().iloc[-1]
    return float((upper_val + lower_val) / 2 * 100)


def _get_buckets_for_date(
    fedwatch_df: pd.DataFrame,
    observation_date: date,
    meeting_date: Optional[date] = None,
) -> pd.DataFrame:
    """Slice fedwatch_df to one (observation_date, meeting_date) pair.

    If meeting_date is None, picks the nearest upcoming FOMC meeting strictly after
    observation_date.
    """
    obs_ts = pd.Timestamp(observation_date)
    filtered = fedwatch_df[fedwatch_df["observation_date"] == obs_ts].copy()
    if len(filtered) == 0:
        raise ValueError(f"No FedWatch data for observation_date={observation_date}")

    if meeting_date is None:
        upcoming = filtered[filtered["meeting_date"] > obs_ts]
        if len(upcoming) == 0:
            raise ValueError(f"No upcoming meetings after {observation_date}")
        meeting_ts = upcoming["meeting_date"].min()
    else:
        meeting_ts = pd.Timestamp(meeting_date)

    result = filtered[filtered["meeting_date"] == meeting_ts].copy()
    if len(result) == 0:
        raise ValueError(
            f"No data for meeting_date={meeting_ts.date()} on observation_date={observation_date}"
        )
    return result


def _market_expected_change_bps(buckets_df: pd.DataFrame, current_rate_bps: float) -> float:
    """Σ (bucket_midpoint - current_rate) × probability. Positive = hike expected."""
    midpoints = (buckets_df["rate_bucket_low"] + buckets_df["rate_bucket_high"]) / 2
    changes = midpoints - current_rate_bps
    return float((changes * buckets_df["probability"]).sum())


def _market_prob_hike(buckets_df: pd.DataFrame, current_rate_bps: float) -> float:
    """Sum of probability mass in buckets strictly above current rate (+1bps buffer)."""
    above_mask = buckets_df["rate_bucket_low"] >= current_rate_bps + 1
    return float(buckets_df.loc[above_mask, "probability"].sum())


def _compute_nlp_distribution(
    nlp_score: float,
    current_rate_bps: float,
    buckets_df: pd.DataFrame,
    calibration_bps: float = DEFAULT_NLP_CALIBRATION_BPS,
    sigma_bps: float = DEFAULT_NLP_SIGMA_BPS,
) -> np.ndarray:
    """Discretize a Gaussian centered on the NLP-implied rate onto market buckets.

    Mass per bucket = CDF(high) - CDF(low). Renormalized to sum to 1 (edge buckets
    may otherwise lose mass to tails).
    """
    from scipy.stats import norm

    implied_rate_bps = current_rate_bps + nlp_score * calibration_bps
    highs = buckets_df["rate_bucket_high"].values
    lows = buckets_df["rate_bucket_low"].values

    nlp_dist = norm.cdf(highs, loc=implied_rate_bps, scale=sigma_bps) - norm.cdf(
        lows, loc=implied_rate_bps, scale=sigma_bps
    )

    total = nlp_dist.sum()
    if total < 1e-6:
        raise ValueError(
            f"NLP distribution has near-zero mass on bucket grid. "
            f"Implied rate {implied_rate_bps}bps is too far from bucket range "
            f"[{lows.min()}, {highs.max()}]."
        )
    return nlp_dist / total


def _surprise_binary(nlp_score: float, prob_hike: float) -> float:
    return nlp_score - prob_hike


def _surprise_expected_change(
    nlp_score: float,
    market_expected_change_bps: float,
    calibration_bps: float = DEFAULT_NLP_CALIBRATION_BPS,
) -> float:
    """Difference of expected rate changes (bps). Positive = NLP more hawkish."""
    nlp_implied_change = nlp_score * calibration_bps
    return nlp_implied_change - market_expected_change_bps


def _surprise_kl_divergence(
    nlp_dist: np.ndarray, market_dist: np.ndarray, eps: float = 1e-10
) -> float:
    """D_KL(P_nlp || P_market). Always non-negative; 0 iff distributions are identical."""
    p = np.asarray(nlp_dist) + eps
    q = (market_dist.values if hasattr(market_dist, "values") else np.asarray(market_dist)) + eps
    p = p / p.sum()
    q = q / q.sum()
    return float(np.sum(p * np.log(p / q)))


def compute_surprise_signal(
    nlp_score: float,
    as_of_date: date,
    method: SurpriseMethod = "expected_change",
    meeting_date: Optional[date] = None,
    fedwatch_df: Optional[pd.DataFrame] = None,
    current_rate_bps: Optional[float] = None,
    calibration_bps: float = DEFAULT_NLP_CALIBRATION_BPS,
) -> float:
    """Single-event surprise.

    Parameters
    ----------
    nlp_score : float in [-1, +1]. Positive = hawkish.
    as_of_date : observation date (when NLP signal was produced).
    method : "binary" | "expected_change" | "kl_divergence".
    meeting_date : target FOMC; None → nearest upcoming after as_of_date.
    fedwatch_df : pre-loaded history; None → load_fedwatch_history().
    current_rate_bps : pre-fetched midpoint; None → fetch from FRED.
    calibration_bps : NLP→bps factor (default 25; refined in PRD-300).

    Returns
    -------
    float — units depend on method:
        binary: dimensionless (≈ [-1, +1])
        expected_change: basis points
        kl_divergence: nats (≥ 0)
    """
    if fedwatch_df is None:
        fedwatch_df = load_fedwatch_history()
    if current_rate_bps is None:
        current_rate_bps = _fetch_current_fed_funds_midpoint(as_of_date)

    buckets_df = _get_buckets_for_date(fedwatch_df, as_of_date, meeting_date)

    if method == "binary":
        prob_hike = _market_prob_hike(buckets_df, current_rate_bps)
        return _surprise_binary(nlp_score, prob_hike)
    if method == "expected_change":
        mkt_change = _market_expected_change_bps(buckets_df, current_rate_bps)
        return _surprise_expected_change(nlp_score, mkt_change, calibration_bps)
    if method == "kl_divergence":
        nlp_dist = _compute_nlp_distribution(nlp_score, current_rate_bps, buckets_df, calibration_bps)
        return _surprise_kl_divergence(nlp_dist, buckets_df["probability"].values)
    raise ValueError(
        f"Unknown method: {method!r}. Use: binary, expected_change, kl_divergence"
    )


def compute_surprise_timeseries(
    nlp_df: pd.DataFrame,
    fedwatch_df: Optional[pd.DataFrame] = None,
    method: SurpriseMethod = "expected_change",
    calibration_bps: float = DEFAULT_NLP_CALIBRATION_BPS,
) -> pd.DataFrame:
    """Batch surprise over a time series of NLP scores.

    Optimization: FedWatch loaded once; FRED target rate fetched in one call covering
    the full date range (forward-filled between FOMC moves).

    Parameters
    ----------
    nlp_df : columns {date (datetime), nlp_score (float)}.

    Returns
    -------
    pd.DataFrame: date, nlp_score, meeting_date, current_rate_bps,
        market_expected_change_bps, surprise, method.
    """
    if fedwatch_df is None:
        fedwatch_df = load_fedwatch_history()

    required = {"date", "nlp_score"}
    missing = required - set(nlp_df.columns)
    if missing:
        raise ValueError(f"nlp_df missing columns: {missing}")

    fred = _get_fred_client()
    start = pd.Timestamp(nlp_df["date"].min()).strftime("%Y-%m-%d")
    end = pd.Timestamp(nlp_df["date"].max()).strftime("%Y-%m-%d")

    upper = fred.get_series("DFEDTARU", observation_start=start, observation_end=end)
    lower = fred.get_series("DFEDTARL", observation_start=start, observation_end=end)
    target_df = pd.DataFrame({"upper": upper, "lower": lower})
    target_df["midpoint_bps"] = (target_df["upper"] + target_df["lower"]) / 2 * 100
    target_df = target_df.ffill()

    results: list[dict] = []
    for _, row in nlp_df.iterrows():
        as_of = row["date"]
        as_of_date = as_of.date() if hasattr(as_of, "date") else as_of
        nlp_score = float(row["nlp_score"])

        target_slice = target_df.loc[:as_of]
        if len(target_slice.dropna(subset=["midpoint_bps"])) == 0:
            continue
        current_rate_bps = float(target_slice["midpoint_bps"].dropna().iloc[-1])

        try:
            surprise = compute_surprise_signal(
                nlp_score=nlp_score,
                as_of_date=as_of_date,
                method=method,
                fedwatch_df=fedwatch_df,
                current_rate_bps=current_rate_bps,
                calibration_bps=calibration_bps,
            )
            buckets = _get_buckets_for_date(fedwatch_df, as_of_date)
            mkt_change = _market_expected_change_bps(buckets, current_rate_bps)
            meeting_date = buckets["meeting_date"].iloc[0]
        except ValueError:
            continue

        results.append({
            "date": as_of,
            "nlp_score": nlp_score,
            "meeting_date": meeting_date,
            "current_rate_bps": current_rate_bps,
            "market_expected_change_bps": mkt_change,
            "surprise": surprise,
            "method": method,
        })

    return pd.DataFrame(results)
