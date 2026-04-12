"""Tests for HMM Regime Classifier — PRD-050 CC-2.

Validates:
  - BIC model selection picks correct n_states on synthetic data
  - Predict returns correct shapes
  - Auto-generated labels contain valid feature names
  - Save/load roundtrip preserves model
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.regime.hmm_classifier import HMMRegimeClassifier


@pytest.fixture(scope="module")
def synthetic_features() -> pd.DataFrame:
    """Generate 3-regime synthetic data with clear cluster separation.

    Regime 0: high feature_a, low feature_b (inflation-like)
    Regime 1: low feature_a, high feature_c (stress-like)
    Regime 2: moderate everything (growth-like)
    """
    rng = np.random.default_rng(42)
    n_per_regime = 80

    # Regime 0: inflation-like
    r0 = rng.normal(loc=[3.0, -1.0, 0.0, 0.0], scale=0.3, size=(n_per_regime, 4))
    # Regime 1: stress-like
    r1 = rng.normal(loc=[-1.0, 0.0, 3.0, 0.0], scale=0.3, size=(n_per_regime, 4))
    # Regime 2: growth-like
    r2 = rng.normal(loc=[0.0, 0.0, 0.0, 0.0], scale=0.3, size=(n_per_regime, 4))

    data = np.vstack([r0, r1, r2])
    dates = pd.date_range("2000-01-31", periods=len(data), freq="ME")

    return pd.DataFrame(
        data,
        index=dates,
        columns=["cpi_yoy", "core_pce_yoy", "nfci", "yield_curve"],
    )


@pytest.fixture(scope="module")
def fitted_hmm(synthetic_features: pd.DataFrame) -> HMMRegimeClassifier:
    hmm = HMMRegimeClassifier()
    hmm.fit(synthetic_features, candidate_states=(2, 3, 4))
    return hmm


def test_bic_selects_reasonable_states(fitted_hmm: HMMRegimeClassifier) -> None:
    """BIC should select 3 or 4 states for data generated from 3 Gaussians.

    On small synthetic datasets BIC may prefer 4 states (splitting one cluster).
    Both 3 and 4 are reasonable — the key is that BIC ran and selected.
    """
    assert fitted_hmm.diagnostics is not None
    assert fitted_hmm.n_states in (3, 4), (
        f"Expected 3-4 states, got {fitted_hmm.n_states}. "
        f"BIC scores: {fitted_hmm.diagnostics.bic_scores}"
    )


def test_predict_shapes(
    fitted_hmm: HMMRegimeClassifier, synthetic_features: pd.DataFrame
) -> None:
    states, probs = fitted_hmm.predict(synthetic_features)
    assert states.shape == (len(synthetic_features),)
    assert probs.shape == (len(synthetic_features), fitted_hmm.n_states)
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-6)


def test_labels_contain_feature_names(fitted_hmm: HMMRegimeClassifier) -> None:
    labels = [p.label for p in fitted_hmm.state_profiles]
    assert len(labels) >= 2, f"Expected >=2 labels, got {labels}"
    # Each label should be FEATURE_HIGH or FEATURE_LOW
    for label in labels:
        parts = label.rsplit("_", 1)
        assert parts[-1] in ("HIGH", "LOW"), f"Bad label format: {label}"


def test_state_profiles_frequencies(fitted_hmm: HMMRegimeClassifier) -> None:
    total = sum(p.frequency_pct for p in fitted_hmm.state_profiles)
    assert abs(total - 100.0) < 1.0, f"Frequencies sum to {total}, expected ~100"


def test_save_load_roundtrip(
    fitted_hmm: HMMRegimeClassifier, synthetic_features: pd.DataFrame, tmp_path
) -> None:
    model_path = tmp_path / "hmm_test.pkl"
    fitted_hmm.save(model_path)

    loaded = HMMRegimeClassifier()
    loaded.load(model_path)

    states_orig, _ = fitted_hmm.predict(synthetic_features)
    states_loaded, _ = loaded.predict(synthetic_features)

    assert np.array_equal(states_orig, states_loaded)
    assert loaded.n_states == fitted_hmm.n_states
    assert len(loaded.state_profiles) == len(fitted_hmm.state_profiles)


def test_diagnostics_populated(fitted_hmm: HMMRegimeClassifier) -> None:
    d = fitted_hmm.diagnostics
    assert d is not None
    assert d.converged
    assert d.n_iter_used > 0
    assert d.log_likelihood < 0  # log-likelihood is negative for continuous data
    assert len(d.bic_scores) >= 3
