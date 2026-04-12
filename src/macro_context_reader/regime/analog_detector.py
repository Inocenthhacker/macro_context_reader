"""Mahalanobis Historical Analog Detector — PRD-050 CC-2b.

Finds historical periods most similar to the current macro environment
using Mahalanobis distance on the standardized feature matrix.

Methodology:
  d_M(v_t, v_tau) = sqrt[(v_t - v_tau)^T * Sigma^-1 * (v_t - v_tau)]
  where Sigma is the sample covariance with Tikhonov regularization
  if near-singular (det < 1e-10).

Anti-leakage: exclude_window_days=365 prevents temporal autocorrelation
from contaminating analog selection.

Refs:
  Mulliner, Harvey, Xia & Fang (2025), "Regimes", SSRN 5164863
  Chiapparoli (2025), "Macroeconomic Factor Timing", SSRN 5287108
  PRD-050 CC-2b
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import mahalanobis

from macro_context_reader.regime.schemas import AnalogMatch

logger = logging.getLogger(__name__)

DEFAULT_COV_PATH = Path("data/regime/mahalanobis_cov.npy")
TIKHONOV_EPSILON = 1e-6


class MahalanobisAnalogDetector:
    """Historical analog detector using Mahalanobis distance."""

    def __init__(self) -> None:
        self.cov: np.ndarray | None = None
        self.cov_inv: np.ndarray | None = None
        self.regularized: bool = False

    def fit(self, features: pd.DataFrame) -> None:
        """Compute sample covariance and its inverse.

        Applies Tikhonov regularization (cov + epsilon*I) if the
        covariance matrix determinant is below 1e-10.
        """
        X = features.values
        self.cov = np.cov(X, rowvar=False)

        det = np.linalg.det(self.cov)
        if abs(det) < 1e-10:
            logger.warning(
                "Covariance near-singular (det=%.2e), applying Tikhonov regularization",
                det,
            )
            self.cov = self.cov + TIKHONOV_EPSILON * np.eye(self.cov.shape[0])
            self.regularized = True
        else:
            self.regularized = False

        self.cov_inv = np.linalg.inv(self.cov)
        logger.info(
            "Fitted covariance: shape=%s, det=%.4e, regularized=%s",
            self.cov.shape, np.linalg.det(self.cov), self.regularized,
        )

    def find_analogs(
        self,
        query_date: pd.Timestamp,
        features: pd.DataFrame,
        k: int = 5,
        exclude_window_days: int = 365,
        eurusd: pd.Series | None = None,
    ) -> list[AnalogMatch]:
        """Find top-k historical analogs by Mahalanobis distance.

        Args:
            query_date: The date to find analogs for.
            features: Full historical feature matrix (DatetimeIndex).
            k: Number of analogs to return.
            exclude_window_days: Days around query_date to exclude (anti-leakage).
            eurusd: Optional EUR/USD series for forward-90d performance.

        Returns:
            List of AnalogMatch sorted by distance ascending.
        """
        if self.cov_inv is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        if query_date not in features.index:
            # Find nearest date
            idx = features.index.get_indexer([query_date], method="nearest")[0]
            query_date = features.index[idx]

        query_vec = features.loc[query_date].values

        # Compute distances, excluding temporal window around query
        distances = {}

        for date, row in features.iterrows():
            if exclude_window_days > 0:
                window_start = query_date - pd.Timedelta(days=exclude_window_days)
                window_end = query_date + pd.Timedelta(days=exclude_window_days)
                if window_start <= date <= window_end:
                    continue
            dist = mahalanobis(query_vec, row.values, self.cov_inv)
            distances[date] = dist

        if not distances:
            raise RuntimeError(
                f"No valid analogs found outside ±{exclude_window_days}d window "
                f"around {query_date.date()}"
            )

        sorted_dates = sorted(distances, key=distances.get)
        top_k = sorted_dates[:k]

        analogs = []
        for rank, date in enumerate(top_k, start=1):
            fwd_90d = None
            if eurusd is not None:
                fwd_date = date + pd.Timedelta(days=90)
                if date in eurusd.index:
                    future = eurusd.loc[eurusd.index >= fwd_date]
                    if not future.empty:
                        fwd_90d = round(
                            (future.iloc[0] - eurusd.loc[date]) / eurusd.loc[date] * 100,
                            2,
                        )
            analogs.append(AnalogMatch(
                date=date.to_pydatetime(),
                distance=round(distances[date], 4),
                rank=rank,
                eurusd_forward_90d_pct=fwd_90d,
            ))

        return analogs

    def find_anti_regimes(
        self,
        query_date: pd.Timestamp,
        features: pd.DataFrame,
        k: int = 5,
        exclude_window_days: int = 365,
    ) -> list[AnalogMatch]:
        """Find top-k anti-regimes (most DIFFERENT historical periods).

        Anti-regimes have predictive power: what happened in anti-regimes
        is unlikely to happen now (Mulliner et al. 2025).
        """
        if self.cov_inv is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        if query_date not in features.index:
            idx = features.index.get_indexer([query_date], method="nearest")[0]
            query_date = features.index[idx]

        query_vec = features.loc[query_date].values

        distances = {}

        for date, row in features.iterrows():
            if exclude_window_days > 0:
                window_start = query_date - pd.Timedelta(days=exclude_window_days)
                window_end = query_date + pd.Timedelta(days=exclude_window_days)
                if window_start <= date <= window_end:
                    continue
            dist = mahalanobis(query_vec, row.values, self.cov_inv)
            distances[date] = dist

        # Sort descending — farthest first
        sorted_dates = sorted(distances, key=distances.get, reverse=True)
        top_k = sorted_dates[:k]

        return [
            AnalogMatch(
                date=date.to_pydatetime(),
                distance=round(distances[date], 4),
                rank=rank,
            )
            for rank, date in enumerate(top_k, start=1)
        ]

    def save(self, path: Path = DEFAULT_COV_PATH) -> None:
        """Persist covariance matrix to disk."""
        if self.cov is None:
            raise RuntimeError("No covariance to save.")
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, self.cov)
        logger.info("Saved covariance to %s", path)

    def load(self, path: Path = DEFAULT_COV_PATH) -> None:
        """Load covariance from disk and recompute inverse."""
        self.cov = np.load(path)
        self.cov_inv = np.linalg.inv(self.cov)
        logger.info("Loaded covariance from %s, shape=%s", path, self.cov.shape)
