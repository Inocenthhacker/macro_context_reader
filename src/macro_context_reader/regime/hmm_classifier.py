"""HMM Regime Classifier — PRD-050 CC-1b.

Discovers latent macro regimes via Gaussian HMM on standardized
macro features. Model selection by BIC + ARI stability over extended
grid. State labels auto-generated from dominant feature z-scores
with duplicate prevention.

Selection logic:
  1. For each n_states in grid, fit 10 seeds and compute BIC, AIC, ARI
  2. Filter candidates with ARI mean >= 0.70 (cluster stability threshold)
  3. Among stable candidates, pick min BIC
  4. Fallback: if nothing passes ARI threshold, pick max ARI with warning

Refs: PRD-050 CC-1b, Steinley (2004) ARI stability threshold
"""

from __future__ import annotations

import logging
import pickle
import warnings
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from sklearn.metrics import adjusted_rand_score

from macro_context_reader.regime.schemas import (
    HMMFitDiagnostics,
    StateProfile,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path("data/regime/hmm_model.pkl")
DEFAULT_STATES_PATH = Path("data/regime/hmm_states.parquet")

ARI_STABILITY_THRESHOLD = 0.70


class HMMRegimeClassifier:
    """Gaussian HMM regime classifier with BIC+ARI model selection."""

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
        n_states_grid: list[int] | None = None,
        covariance_type: str = "diag",
        n_seeds: int = 10,
    ) -> HMMFitDiagnostics:
        """Fit HMM with extended grid search + ARI stability check.

        Args:
            features: Standardized monthly features from build_regime_features().
            n_states: Force specific state count. If None, select by BIC+ARI.
            random_state: Random seed for final fit.
            n_states_grid: Grid of candidates. Default [2,3,4,5,6,7,8].
            covariance_type: HMM covariance type. Default 'diag'.
            n_seeds: Number of random seeds for stability evaluation.

        Returns:
            HMMFitDiagnostics with BIC/AIC/ARI scores and selection reason.
        """
        if n_states_grid is None:
            n_states_grid = [2, 3, 4, 5, 6, 7, 8]

        self.feature_names = list(features.columns)
        X = features.values

        if n_states is not None:
            # Forced n_states — skip grid search
            bic_m, bic_s, aic_m, aic_s, ari_m, ari_s = self._evaluate_n(
                X, n_states, covariance_type, n_seeds
            )
            best_n = n_states
            grid = [n_states]
            bic_mean = {n_states: bic_m}
            bic_std = {n_states: bic_s}
            aic_mean = {n_states: aic_m}
            aic_std = {n_states: aic_s}
            ari_mean_d = {n_states: ari_m}
            ari_std_d = {n_states: ari_s}
            reason = "forced n_states"
        else:
            grid = n_states_grid
            bic_mean: dict[int, float] = {}
            bic_std: dict[int, float] = {}
            aic_mean: dict[int, float] = {}
            aic_std: dict[int, float] = {}
            ari_mean_d: dict[int, float] = {}
            ari_std_d: dict[int, float] = {}

            for n in grid:
                bm, bs, am, as_, arm, ars = self._evaluate_n(
                    X, n, covariance_type, n_seeds
                )
                bic_mean[n] = bm
                bic_std[n] = bs
                aic_mean[n] = am
                aic_std[n] = as_
                ari_mean_d[n] = arm
                ari_std_d[n] = ars
                logger.info(
                    "n=%d: BIC=%.0f±%.0f, AIC=%.0f±%.0f, ARI=%.3f±%.3f",
                    n, bm, bs, am, as_, arm, ars,
                )

            # Selection: stable candidates first, then min BIC
            stable = [n for n in grid if ari_mean_d[n] >= ARI_STABILITY_THRESHOLD]
            if stable:
                best_n = min(stable, key=lambda n: bic_mean[n])
                reason = "min BIC among stable (ARI >= 0.70)"
            else:
                best_n = max(grid, key=lambda n: ari_mean_d[n])
                reason = "fallback to max ARI (no candidate >= 0.70)"
                warnings.warn(
                    f"No n_states has ARI >= {ARI_STABILITY_THRESHOLD}. "
                    f"Selected n={best_n} with ARI={ari_mean_d[best_n]:.3f}.",
                    stacklevel=2,
                )

            logger.info("Selected n_states=%d (%s)", best_n, reason)

        # Final fit with best n_states
        self.model = GaussianHMM(
            n_components=best_n,
            covariance_type=covariance_type,
            n_iter=200,
            random_state=random_state,
        )
        self.model.fit(X)
        self.n_states = best_n

        # Generate state profiles with unique labels
        states = self.model.predict(X)
        self.state_profiles = self._build_profiles(features, states)

        self.diagnostics = HMMFitDiagnostics(
            grid=grid,
            bic_mean=bic_mean,
            bic_std=bic_std,
            aic_mean=aic_mean,
            aic_std=aic_std,
            ari_mean=ari_mean_d,
            ari_std=ari_std_d,
            selected_n_states=best_n,
            selection_reason=reason,
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate_n(
        self,
        X: np.ndarray,
        n: int,
        covariance_type: str,
        n_seeds: int,
    ) -> tuple[float, float, float, float, float, float]:
        """Fit n_seeds HMMs for a given n_states and return mean/std BIC, AIC, ARI."""
        bics: list[float] = []
        aics: list[float] = []
        all_states: list[np.ndarray] = []

        for seed in range(n_seeds):
            model = GaussianHMM(
                n_components=n,
                covariance_type=covariance_type,
                n_iter=200,
                random_state=seed,
            )
            model.fit(X)
            bic, aic = self._compute_bic_aic(model, X, n, covariance_type)
            bics.append(bic)
            aics.append(aic)
            all_states.append(model.predict(X))

        # Pairwise ARI across all seed pairs
        ari_scores: list[float] = []
        for i, j in combinations(range(n_seeds), 2):
            ari_scores.append(adjusted_rand_score(all_states[i], all_states[j]))

        bic_mean = float(np.mean(bics))
        bic_std = float(np.std(bics))
        aic_mean = float(np.mean(aics))
        aic_std = float(np.std(aics))
        ari_mean = float(np.mean(ari_scores)) if ari_scores else 0.0
        ari_std = float(np.std(ari_scores)) if ari_scores else 0.0

        return bic_mean, bic_std, aic_mean, aic_std, ari_mean, ari_std

    @staticmethod
    def _compute_bic_aic(
        model: GaussianHMM,
        X: np.ndarray,
        n: int,
        covariance_type: str,
    ) -> tuple[float, float]:
        """Compute BIC and AIC for a fitted HMM."""
        log_ll = model.score(X) * len(X)
        n_features = X.shape[1]

        # Count free parameters based on covariance type
        if covariance_type == "full":
            cov_params = n * n_features * (n_features + 1) // 2
        elif covariance_type == "diag":
            cov_params = n * n_features
        elif covariance_type == "spherical":
            cov_params = n
        else:  # tied
            cov_params = n_features * (n_features + 1) // 2

        n_params = (
            n * (n - 1)       # transition matrix
            + n * n_features  # means
            + cov_params      # covariances
            + (n - 1)         # start probabilities
        )

        bic = -2 * log_ll + n_params * np.log(len(X))
        aic = -2 * log_ll + 2 * n_params
        return float(bic), float(aic)

    def _build_profiles(
        self, features: pd.DataFrame, states: np.ndarray
    ) -> list[StateProfile]:
        """Auto-generate state profiles with unique semantic labels."""
        profiles = []
        global_mean = features.mean()
        used_labels: list[str] = []

        for sid in range(self.n_states):
            mask = states == sid
            state_data = features.iloc[mask]

            if len(state_data) == 0:
                continue

            mean_features = state_data.mean()
            deviations = (mean_features - global_mean).abs()
            sorted_feats = deviations.sort_values(ascending=False)

            # Primary label from dominant feature
            dominant_feat = sorted_feats.index[0]
            direction = "HIGH" if mean_features[dominant_feat] > global_mean[dominant_feat] else "LOW"
            label = f"{dominant_feat.upper()}_{direction}"

            # Duplicate prevention: add secondary feature if label already used
            if label in used_labels and len(sorted_feats) > 1:
                sec_feat = sorted_feats.index[1]
                sec_dir = "HIGH" if mean_features[sec_feat] > global_mean[sec_feat] else "LOW"
                label = f"{dominant_feat.upper()}_{direction}_{sec_feat.upper()}_{sec_dir}"

            # Final fallback: append suffix if still duplicate
            if label in used_labels:
                suffix = "A"
                while f"{label}_{suffix}" in used_labels:
                    suffix = chr(ord(suffix) + 1)
                label = f"{label}_{suffix}"
                logger.warning("Duplicate label resolved with suffix: %s", label)

            used_labels.append(label)

            # Compute median duration (consecutive runs)
            durations: list[int] = []
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
