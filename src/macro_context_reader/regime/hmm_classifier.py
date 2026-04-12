"""HMM Regime Classifier — PRD-050 CC-2.

Discovers latent macro regimes via Gaussian HMM on standardized
macro features. Model selection by BIC over candidate state counts.
State labels auto-generated from dominant feature z-scores.

Zero hardcoded thresholds — regimes emerge from data structure.

Refs: PRD-050 CC-2, hmmlearn docs
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

from macro_context_reader.regime.schemas import (
    HMMFitDiagnostics,
    StateProfile,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path("data/regime/hmm_model.pkl")
DEFAULT_STATES_PATH = Path("data/regime/hmm_states.parquet")


class HMMRegimeClassifier:
    """Gaussian HMM regime classifier with automatic label generation."""

    def __init__(self) -> None:
        self.model: GaussianHMM | None = None
        self.n_states: int = 0
        self.feature_names: list[str] = []
        self.state_profiles: list[StateProfile] = []
        self.diagnostics: HMMFitDiagnostics | None = None

    def fit(
        self,
        features: pd.DataFrame,
        n_states: int | None = None,
        random_state: int = 42,
        candidate_states: tuple[int, ...] = (3, 4, 5, 6),
    ) -> HMMFitDiagnostics:
        """Fit HMM on feature matrix, selecting n_states via BIC if not specified.

        Args:
            features: Standardized monthly features from build_regime_features().
            n_states: Force specific state count. If None, select by BIC.
            random_state: Random seed for reproducibility.
            candidate_states: Grid of n_states to evaluate when n_states is None.

        Returns:
            HMMFitDiagnostics with BIC scores, state profiles, convergence info.
        """
        self.feature_names = list(features.columns)
        X = features.values

        if n_states is not None:
            best_n = n_states
            bic_scores = {n_states: self._fit_and_bic(X, n_states, random_state)}
        else:
            bic_scores = {}
            for n in candidate_states:
                bic_scores[n] = self._fit_and_bic(X, n, random_state)
                logger.info("BIC(n_states=%d) = %.1f", n, bic_scores[n])
            best_n = min(bic_scores, key=bic_scores.get)
            logger.info("Selected n_states=%d (lowest BIC=%.1f)", best_n, bic_scores[best_n])

        # Final fit with best n_states
        self.model = GaussianHMM(
            n_components=best_n,
            covariance_type="full",
            n_iter=200,
            random_state=random_state,
        )
        self.model.fit(X)
        self.n_states = best_n

        # Generate state profiles
        states = self.model.predict(X)
        self.state_profiles = self._build_profiles(features, states)

        self.diagnostics = HMMFitDiagnostics(
            n_states_selected=best_n,
            bic_scores=bic_scores,
            converged=self.model.monitor_.converged,
            n_iter_used=self.model.monitor_.iter,
            log_likelihood=float(self.model.score(X)),
            state_profiles=self.state_profiles,
        )
        return self.diagnostics

    def predict(self, features: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Predict states and state probabilities.

        Returns:
            (states, probs) where states is shape (T,) and probs is (T, n_states).
        """
        if self.model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")
        X = features.values
        states = self.model.predict(X)
        probs = self.model.predict_proba(X)
        return states, probs

    def get_label(self, state_id: int) -> str:
        """Get auto-generated label for a state."""
        for p in self.state_profiles:
            if p.state_id == state_id:
                return p.label
        return f"STATE_{state_id}"

    def save(self, model_path: Path = DEFAULT_MODEL_PATH) -> None:
        """Persist fitted model to disk."""
        if self.model is None:
            raise RuntimeError("No model to save.")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "n_states": self.n_states,
            "feature_names": self.feature_names,
            "state_profiles": [p.model_dump() for p in self.state_profiles],
        }
        with open(model_path, "wb") as f:
            pickle.dump(payload, f)
        logger.info("Saved HMM model to %s", model_path)

    def load(self, model_path: Path = DEFAULT_MODEL_PATH) -> None:
        """Load a previously fitted model from disk."""
        with open(model_path, "rb") as f:
            payload = pickle.load(f)  # noqa: S301
        self.model = payload["model"]
        self.n_states = payload["n_states"]
        self.feature_names = payload["feature_names"]
        self.state_profiles = [
            StateProfile.model_validate(d) for d in payload["state_profiles"]
        ]

    def _fit_and_bic(self, X: np.ndarray, n: int, seed: int) -> float:
        """Fit HMM with n states and return BIC score."""
        model = GaussianHMM(
            n_components=n,
            covariance_type="full",
            n_iter=200,
            random_state=seed,
        )
        model.fit(X)
        log_ll = model.score(X) * len(X)
        n_features = X.shape[1]
        # Parameters: transition matrix (n*(n-1)) + means (n*d) + covariances (n*d*(d+1)/2) + startprob (n-1)
        n_params = (
            n * (n - 1)
            + n * n_features
            + n * n_features * (n_features + 1) // 2
            + (n - 1)
        )
        bic = -2 * log_ll + n_params * np.log(len(X))
        return float(bic)

    def _build_profiles(
        self, features: pd.DataFrame, states: np.ndarray
    ) -> list[StateProfile]:
        """Auto-generate state profiles with semantic labels."""
        profiles = []
        global_mean = features.mean()

        for sid in range(self.n_states):
            mask = states == sid
            state_data = features.iloc[mask]

            if len(state_data) == 0:
                continue

            mean_features = state_data.mean()
            # Dominant feature = highest |z-score| vs global mean
            deviations = (mean_features - global_mean).abs()
            dominant_feat = deviations.idxmax()
            direction = "HIGH" if mean_features[dominant_feat] > global_mean[dominant_feat] else "LOW"

            # Label from feature name
            label = f"{dominant_feat.upper()}_{direction}"

            # Compute median duration (consecutive runs)
            durations = []
            run_len = 0
            for s in states:
                if s == sid:
                    run_len += 1
                elif run_len > 0:
                    durations.append(run_len)
                    run_len = 0
            if run_len > 0:
                durations.append(run_len)

            profiles.append(StateProfile(
                state_id=sid,
                label=label,
                dominant_feature=dominant_feat,
                dominant_direction=direction,
                mean_features=dict(mean_features),
                median_duration_months=float(np.median(durations)) if durations else 0.0,
                frequency_pct=round(float(mask.sum()) / len(states) * 100, 1),
            ))

        return profiles
