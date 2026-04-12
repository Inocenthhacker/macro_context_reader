"""Tests for regime-conditional correlation analysis — PRD-300 CC-0d.

Validates correlation computation, bootstrap CI, permutation p-values,
lead-lag analysis, and regime_switching_confirmed logic on synthetic data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.divergence.regime_conditional import (
    RegimeConditionalResults,
    _bootstrap_pearson_ci,
    _permutation_pvalue,
    compute_conditional_correlations,
    compute_lead_lag,
)


def _make_synthetic_df(
    n_per_regime: int = 60,
    corrs: dict[str, float] | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Create synthetic regime-stratified data with known correlations.

    Default: 3 regimes with correlations {-0.7, 0.0, +0.7}.
    """
    if corrs is None:
        corrs = {"STRESS_HIGH": -0.7, "NEUTRAL": 0.0, "INFLATION_HIGH": 0.7}

    rng = np.random.default_rng(seed)
    rows = []
    state_id = 0

    for label, target_corr in corrs.items():
        # Generate correlated pairs via Cholesky
        cov = [[1.0, target_corr], [target_corr, 1.0]]
        data = rng.multivariate_normal([0, 0], cov, size=n_per_regime)
        dates = pd.date_range(
            f"{2000 + state_id * 5}-01-31",
            periods=n_per_regime,
            freq="ME",
        )
        for i, d in enumerate(dates):
            rows.append({
                "date": d,
                "real_rate_diff": data[i, 0],
                "eurusd": 1.10 + data[i, 1] * 0.05,
                "regime_state": state_id,
                "regime_label": label,
                "regime_prob_max": 0.95,
            })
        state_id += 1

    return pd.DataFrame(rows)


class TestConditionalCorrelations:
    """Test compute_conditional_correlations on synthetic data."""

    @pytest.fixture(scope="class")
    def results(self) -> RegimeConditionalResults:
        df = _make_synthetic_df()
        return compute_conditional_correlations(
            df, n_bootstrap=500, n_perm=500, random_state=42
        )

    def test_detects_strong_correlations(self, results: RegimeConditionalResults) -> None:
        """Should detect strong correlations in STRESS and INFLATION regimes."""
        by_label = {r.regime_label: r for r in results.per_regime}
        # STRESS_HIGH should have strong negative correlation
        assert by_label["STRESS_HIGH"].pearson_level < -0.4
        # INFLATION_HIGH should have strong positive correlation
        assert by_label["INFLATION_HIGH"].pearson_level > 0.4
        # NEUTRAL should be near zero
        assert abs(by_label["NEUTRAL"].pearson_level) < 0.3

    def test_n_obs_match(self, results: RegimeConditionalResults) -> None:
        """Total observations across regimes should match input size."""
        total = sum(r.n_obs for r in results.per_regime)
        assert total == 180  # 60 * 3

    def test_bootstrap_ci_not_degenerate(self, results: RegimeConditionalResults) -> None:
        """Bootstrap CI should have low != high."""
        for r in results.per_regime:
            low, high = r.pearson_level_ci95
            assert low < high, f"{r.regime_label}: CI is degenerate ({low}, {high})"

    def test_permutation_pvalue_reproducible(self) -> None:
        """Same random_state should give same p-value."""
        rng_data = np.random.default_rng(99)
        x = rng_data.normal(size=50)
        y = rng_data.normal(size=50)
        p1 = _permutation_pvalue(x, y, n_perm=200, random_state=42)
        p2 = _permutation_pvalue(x, y, n_perm=200, random_state=42)
        assert p1 == p2

    def test_regime_switching_confirmed(self, results: RegimeConditionalResults) -> None:
        """With corrs {-0.7, 0.0, +0.7}, regime_switching should be True."""
        assert results.regime_switching_confirmed is True

    def test_regime_switching_not_confirmed_weak_corrs(self) -> None:
        """All correlations near zero → regime_switching_confirmed = False."""
        df = _make_synthetic_df(
            corrs={"A": 0.1, "B": -0.05, "C": 0.15}, n_per_regime=60
        )
        res = compute_conditional_correlations(
            df, n_bootstrap=200, n_perm=200, random_state=42
        )
        assert res.regime_switching_confirmed is False


class TestLeadLag:
    def test_identical_series_lag_zero(self) -> None:
        """Cross-correlation of identical series should peak at lag=0."""
        x = np.sin(np.linspace(0, 4 * np.pi, 100))
        lags = compute_lead_lag(x, x, max_lag=6)
        best = max(lags, key=lambda k: abs(lags[k]))
        assert best == 0
        assert abs(lags[0] - 1.0) < 0.01

    def test_lead_lag_symmetry(self) -> None:
        """Lag dict should have entries for [-max_lag, +max_lag]."""
        x = np.random.default_rng(42).normal(size=50)
        y = np.random.default_rng(43).normal(size=50)
        lags = compute_lead_lag(x, y, max_lag=3)
        assert set(lags.keys()) == {-3, -2, -1, 0, 1, 2, 3}


class TestBootstrapAndPermutation:
    def test_bootstrap_ci_contains_true_corr(self) -> None:
        """For strong correlation, CI should not contain zero."""
        rng = np.random.default_rng(42)
        cov = [[1, 0.8], [0.8, 1]]
        data = rng.multivariate_normal([0, 0], cov, size=100)
        low, high = _bootstrap_pearson_ci(data[:, 0], data[:, 1], n_resamples=500)
        assert low > 0.3, f"CI lower bound {low} too low for r~0.8"
        assert high > 0.5

    def test_permutation_significant_for_strong_corr(self) -> None:
        """Permutation p-value should be small for truly correlated data."""
        rng = np.random.default_rng(42)
        cov = [[1, 0.8], [0.8, 1]]
        data = rng.multivariate_normal([0, 0], cov, size=100)
        p = _permutation_pvalue(data[:, 0], data[:, 1], n_perm=500, random_state=42)
        assert p < 0.05

    def test_low_sample_warning(self) -> None:
        """Regime with <30 obs should have low_sample_warning=True."""
        df = _make_synthetic_df(corrs={"SMALL": 0.5}, n_per_regime=20)
        res = compute_conditional_correlations(
            df, n_bootstrap=100, n_perm=100, random_state=42
        )
        assert res.per_regime[0].low_sample_warning is True
        assert res.per_regime[0].n_obs == 20


class TestStartDateAlignment:
    def test_default_start_respects_t5yie(self) -> None:
        """Default start date should be >= 2003-01-01 (T5YIE availability)."""
        import inspect
        from macro_context_reader.divergence.regime_conditional import load_aligned_data

        sig = inspect.signature(load_aligned_data)
        default_start = sig.parameters["start"].default
        assert default_start >= "2003-01-01", (
            f"Default start is {default_start}, expected >= 2003-01-01 "
            "(T5YIE starts 2003-01-02)"
        )
