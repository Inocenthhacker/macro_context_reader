"""Tests for Mahalanobis Analog Detector — PRD-050 CC-2b.

Validates:
  - Distance to self is 0 (without exclude window)
  - Exclude window correctly removes nearby dates
  - Nearest analog comes from same distribution on synthetic data
  - Tikhonov regularization triggers on near-singular covariance
  - Save/load roundtrip
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.regime.analog_detector import MahalanobisAnalogDetector


@pytest.fixture(scope="module")
def synthetic_matrix() -> pd.DataFrame:
    """Monthly features with 2 distinct clusters for analog testing."""
    rng = np.random.default_rng(42)
    n = 120  # 10 years

    # First 60 months: cluster A (high values)
    a = rng.normal(loc=[2.0, 2.0, 2.0], scale=0.5, size=(60, 3))
    # Last 60 months: cluster B (low values)
    b = rng.normal(loc=[-2.0, -2.0, -2.0], scale=0.5, size=(60, 3))

    data = np.vstack([a, b])
    dates = pd.date_range("2010-01-31", periods=n, freq="ME")

    return pd.DataFrame(data, index=dates, columns=["f1", "f2", "f3"])


@pytest.fixture(scope="module")
def fitted_detector(synthetic_matrix: pd.DataFrame) -> MahalanobisAnalogDetector:
    det = MahalanobisAnalogDetector()
    det.fit(synthetic_matrix)
    return det


def test_distance_to_self_is_zero(
    fitted_detector: MahalanobisAnalogDetector, synthetic_matrix: pd.DataFrame
) -> None:
    """Mahalanobis distance from a point to itself should be 0."""
    query = synthetic_matrix.index[30]
    analogs = fitted_detector.find_analogs(
        query_date=query,
        features=synthetic_matrix,
        k=1,
        exclude_window_days=0,  # don't exclude anything
    )
    # The closest analog to a point should be itself (distance ~0)
    assert analogs[0].distance < 0.01, f"Distance to self = {analogs[0].distance}"


def test_exclude_window_removes_nearby(
    fitted_detector: MahalanobisAnalogDetector, synthetic_matrix: pd.DataFrame
) -> None:
    """Dates within exclude_window_days should not appear in results."""
    query = synthetic_matrix.index[60]  # middle of dataset
    analogs = fitted_detector.find_analogs(
        query_date=query,
        features=synthetic_matrix,
        k=5,
        exclude_window_days=365,
    )
    for a in analogs:
        diff = abs((pd.Timestamp(a.date) - query).days)
        assert diff > 365, f"Analog at {a.date} is only {diff} days from query"


def test_nearest_from_same_cluster(
    fitted_detector: MahalanobisAnalogDetector, synthetic_matrix: pd.DataFrame
) -> None:
    """Query from cluster A should find analogs in cluster A, not B."""
    # Query from cluster A (first 60 months), month 30
    query = synthetic_matrix.index[30]
    analogs = fitted_detector.find_analogs(
        query_date=query,
        features=synthetic_matrix,
        k=5,
        exclude_window_days=60,  # short window to keep enough cluster A points
    )
    # All top-5 analogs should be from cluster A (first 60 months)
    for a in analogs:
        month_idx = synthetic_matrix.index.get_loc(pd.Timestamp(a.date))
        assert month_idx < 60, (
            f"Analog at {a.date} (idx={month_idx}) is from cluster B, expected A"
        )


def test_anti_regimes_from_opposite_cluster(
    fitted_detector: MahalanobisAnalogDetector, synthetic_matrix: pd.DataFrame
) -> None:
    """Anti-regimes for cluster A query should come from cluster B."""
    query = synthetic_matrix.index[30]
    anti = fitted_detector.find_anti_regimes(
        query_date=query,
        features=synthetic_matrix,
        k=5,
        exclude_window_days=60,
    )
    for a in anti:
        month_idx = synthetic_matrix.index.get_loc(pd.Timestamp(a.date))
        assert month_idx >= 60, (
            f"Anti-regime at {a.date} (idx={month_idx}) is from cluster A, expected B"
        )


def test_tikhonov_on_singular_covariance() -> None:
    """Detector should regularize near-singular covariance without error."""
    # Create perfectly collinear features -> singular covariance
    dates = pd.date_range("2020-01-31", periods=24, freq="ME")
    x = np.linspace(0, 1, 24)
    df = pd.DataFrame({
        "f1": x,
        "f2": x * 2,  # perfectly collinear with f1
        "f3": x + 0.5,  # also collinear
    }, index=dates)

    det = MahalanobisAnalogDetector()
    det.fit(df)
    assert det.regularized is True
    assert det.cov_inv is not None


def test_save_load_roundtrip(
    fitted_detector: MahalanobisAnalogDetector, synthetic_matrix: pd.DataFrame, tmp_path
) -> None:
    cov_path = tmp_path / "cov_test.npy"
    fitted_detector.save(cov_path)

    loaded = MahalanobisAnalogDetector()
    loaded.load(cov_path)

    assert np.allclose(fitted_detector.cov, loaded.cov)
    assert np.allclose(fitted_detector.cov_inv, loaded.cov_inv)


def test_eurusd_forward_returns(
    fitted_detector: MahalanobisAnalogDetector, synthetic_matrix: pd.DataFrame
) -> None:
    """Analog matches should include EUR/USD forward returns when provided."""
    dates = synthetic_matrix.index
    eurusd = pd.Series(
        np.linspace(1.05, 1.15, len(dates)),
        index=dates,
        name="eurusd",
    )
    query = synthetic_matrix.index[30]
    analogs = fitted_detector.find_analogs(
        query_date=query,
        features=synthetic_matrix,
        k=3,
        exclude_window_days=60,
        eurusd=eurusd,
    )
    # At least some analogs should have forward returns populated
    has_fwd = [a for a in analogs if a.eurusd_forward_90d_pct is not None]
    assert len(has_fwd) > 0, "Expected at least one analog with EUR/USD forward return"
