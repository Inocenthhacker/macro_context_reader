"""Regime-conditional correlation analysis — PRD-300 CC-0d.

Computes real_rate_differential ↔ EUR/USD correlations stratified by
HMM-detected macro regime. Validates the regime-switching hypothesis
(DEC-009): the global r = -0.045 masks regime-specific correlations
that are individually strong but cancel out in aggregate.

Four correlation measures per regime:
  - Pearson on level (standard)
  - Pearson on monthly changes (delta)
  - Spearman rank (non-parametric, robust to outliers)
  - Kendall tau (small-sample friendly)

Bootstrap 95% CI and permutation p-values (not t-test — series are autocorrelated).

Refs: PRD-300 CC-0d, DEC-005, DEC-009
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from scipy import stats

logger = logging.getLogger(__name__)

MIN_OBS_PER_REGIME = 30


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class RegimeCorrelation(BaseModel):
    """Correlation statistics for a single regime."""

    model_config = ConfigDict(frozen=True)

    regime_label: str
    regime_state: int
    n_obs: int
    pearson_level: float
    pearson_level_ci95: tuple[float, float]
    pearson_level_pvalue: float
    pearson_diff: float
    spearman: float
    kendall: float
    best_lag_months: int
    best_lag_corr: float
    low_sample_warning: bool = Field(
        default=False,
        description=f"True if n_obs < {MIN_OBS_PER_REGIME}",
    )


class RegimeConditionalResults(BaseModel):
    """Full results from regime-conditional correlation analysis."""

    model_config = ConfigDict(frozen=True)

    global_pearson: float
    per_regime: list[RegimeCorrelation]
    comparison_vs_global: dict[str, float] = Field(
        ..., description="Effect size per regime: regime_corr - global_corr"
    )
    regime_switching_confirmed: bool = Field(
        ...,
        description="True if at least one regime has |corr| > 0.4 and "
        "statistically different from global",
    )


# ---------------------------------------------------------------------------
# Data loading and alignment
# ---------------------------------------------------------------------------

def load_aligned_data(start: str = "2001-01-01") -> pd.DataFrame:
    """Load and align real_rate_diff, EUR/USD, and regime labels on monthly index.

    Tries parquet cache first, falls back to computing fresh from FRED/ECB.
    Regime labels computed via HMM fit on full history.

    Returns:
        DataFrame with columns: date, real_rate_diff, eurusd,
        regime_state, regime_label, regime_prob_max
    """
    from macro_context_reader.market_pricing.real_rate_differential import (
        compute_real_rate_differential,
    )
    from macro_context_reader.market_pricing.fx import fetch_fx_eurusd
    from macro_context_reader.regime.indicators import build_regime_features
    from macro_context_reader.regime.hmm_classifier import HMMRegimeClassifier
    from macro_context_reader.regime.consensus import get_regime_history

    start_dt = datetime.fromisoformat(start)

    # Load real rate differential
    parquet_path = Path("data/market_pricing/real_rate_differential.parquet")
    if parquet_path.exists():
        rrd = pd.read_parquet(parquet_path)
        logger.info("Loaded real_rate_diff from cache: %d rows", len(rrd))
    else:
        logger.info("Parquet not found, computing real_rate_diff from FRED/ECB...")
        rrd = compute_real_rate_differential(start=start_dt)

    # Load EUR/USD
    fx = fetch_fx_eurusd(start=start_dt)

    # Resample both to month-end
    rrd["date"] = pd.to_datetime(rrd["date"])
    rrd_monthly = rrd.set_index("date")[["real_rate_differential"]].resample("ME").last().dropna()
    rrd_monthly.columns = ["real_rate_diff"]

    fx["date"] = pd.to_datetime(fx["date"])
    fx_monthly = fx.set_index("date")[["eurusd"]].resample("ME").last().dropna()

    # Load regime history
    features = build_regime_features(start="2000-01-01")
    hmm = HMMRegimeClassifier()
    hmm.fit(features)
    regime = get_regime_history(features, hmm)
    regime["date"] = pd.to_datetime(regime["date"])
    regime_indexed = regime.set_index("date")[["hmm_state", "hmm_label", "max_prob"]]
    regime_indexed.columns = ["regime_state", "regime_label", "regime_prob_max"]

    # Align on common monthly index
    merged = rrd_monthly.join(fx_monthly, how="inner").join(regime_indexed, how="inner")
    merged = merged.loc[start:].dropna()
    merged = merged.reset_index().rename(columns={"index": "date"})

    logger.info("Aligned dataset: %d months", len(merged))
    return merged


# ---------------------------------------------------------------------------
# Correlation computation
# ---------------------------------------------------------------------------

def _bootstrap_pearson_ci(
    x: np.ndarray,
    y: np.ndarray,
    n_resamples: int = 1000,
    random_state: int = 42,
) -> tuple[float, float]:
    """Bootstrap 95% CI for Pearson correlation."""
    rng = np.random.default_rng(random_state)
    n = len(x)
    corrs = []
    for _ in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        r = np.corrcoef(x[idx], y[idx])[0, 1]
        if not np.isnan(r):
            corrs.append(r)
    if not corrs:
        return (np.nan, np.nan)
    return (float(np.percentile(corrs, 2.5)), float(np.percentile(corrs, 97.5)))


def _permutation_pvalue(
    x: np.ndarray,
    y: np.ndarray,
    n_perm: int = 1000,
    random_state: int = 42,
) -> float:
    """Permutation test p-value for Pearson correlation.

    More appropriate than t-test for autocorrelated time series.
    """
    rng = np.random.default_rng(random_state)
    observed = np.corrcoef(x, y)[0, 1]
    if np.isnan(observed):
        return 1.0
    count = 0
    for _ in range(n_perm):
        y_perm = rng.permutation(y)
        r_perm = np.corrcoef(x, y_perm)[0, 1]
        if abs(r_perm) >= abs(observed):
            count += 1
    return count / n_perm


def compute_lead_lag(
    x: np.ndarray,
    y: np.ndarray,
    max_lag: int = 6,
) -> dict[int, float]:
    """Cross-correlation x(t) vs y(t+k) for k in [-max_lag, +max_lag].

    Negative lag: x leads y. Positive lag: y leads x.
    """
    result = {}
    n = len(x)
    for k in range(-max_lag, max_lag + 1):
        if k < 0:
            x_slice = x[-k:]
            y_slice = y[:n + k]
        elif k > 0:
            x_slice = x[:n - k]
            y_slice = y[k:]
        else:
            x_slice = x
            y_slice = y
        if len(x_slice) < 10:
            continue
        r = np.corrcoef(x_slice, y_slice)[0, 1]
        result[k] = float(r) if not np.isnan(r) else 0.0
    return result


def compute_conditional_correlations(
    df: pd.DataFrame,
    n_bootstrap: int = 1000,
    n_perm: int = 1000,
    max_lag_months: int = 6,
    random_state: int = 42,
) -> RegimeConditionalResults:
    """Compute correlations real_rate_diff ↔ EUR/USD per HMM regime.

    Args:
        df: Output of load_aligned_data() with columns:
            real_rate_diff, eurusd, regime_state, regime_label
        n_bootstrap: Bootstrap resamples for CI.
        n_perm: Permutation iterations for p-value.
        max_lag_months: Max lead/lag for cross-correlation.
        random_state: Seed for reproducibility.

    Returns:
        RegimeConditionalResults with per-regime and global statistics.
    """
    x_all = df["real_rate_diff"].values
    y_all = df["eurusd"].values
    global_r = float(np.corrcoef(x_all, y_all)[0, 1])

    per_regime: list[RegimeCorrelation] = []
    comparison: dict[str, float] = {}

    for (state, label), group in df.groupby(["regime_state", "regime_label"]):
        x = group["real_rate_diff"].values
        y = group["eurusd"].values
        n = len(x)

        low_sample = n < MIN_OBS_PER_REGIME

        # Pearson level
        pearson_r = float(np.corrcoef(x, y)[0, 1]) if n >= 3 else 0.0
        ci = _bootstrap_pearson_ci(x, y, n_bootstrap, random_state)
        pval = _permutation_pvalue(x, y, n_perm, random_state)

        # Pearson on monthly changes
        dx = np.diff(x)
        dy = np.diff(y)
        pearson_diff = float(np.corrcoef(dx, dy)[0, 1]) if len(dx) >= 3 else 0.0

        # Spearman + Kendall
        spearman_r = float(stats.spearmanr(x, y).statistic) if n >= 3 else 0.0
        kendall_r = float(stats.kendalltau(x, y).statistic) if n >= 3 else 0.0

        # Lead-lag
        lags = compute_lead_lag(x, y, max_lag_months)
        if lags:
            best_lag = max(lags, key=lambda k: abs(lags[k]))
            best_lag_corr = lags[best_lag]
        else:
            best_lag, best_lag_corr = 0, 0.0

        per_regime.append(RegimeCorrelation(
            regime_label=str(label),
            regime_state=int(state),
            n_obs=n,
            pearson_level=round(pearson_r, 4),
            pearson_level_ci95=(round(ci[0], 4), round(ci[1], 4)),
            pearson_level_pvalue=round(pval, 4),
            pearson_diff=round(pearson_diff, 4),
            spearman=round(spearman_r, 4),
            kendall=round(kendall_r, 4),
            best_lag_months=best_lag,
            best_lag_corr=round(best_lag_corr, 4),
            low_sample_warning=low_sample,
        ))

        comparison[str(label)] = round(pearson_r - global_r, 4)

    # Regime switching confirmed?
    confirmed = any(
        abs(rc.pearson_level) > 0.4 and rc.pearson_level_pvalue < 0.05
        for rc in per_regime
        if not rc.low_sample_warning
    )

    return RegimeConditionalResults(
        global_pearson=round(global_r, 4),
        per_regime=per_regime,
        comparison_vs_global=comparison,
        regime_switching_confirmed=confirmed,
    )
