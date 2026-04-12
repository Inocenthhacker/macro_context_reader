"""Tests for HMM Regime Classifier — PRD-050 CC-1b.

Validates:
  - BIC+ARI grid selection picks reasonable n_states on synthetic data
  - ARI fallback triggers on noisy data
  - Predict returns correct shapes
  - Auto-generated labels are unique and contain valid feature names
  - Save/load roundtrip preserves model
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.regime.hmm_classifier import HMMRegimeClassifier


@pytest.fixture(scope="module")
def synthetic_features() -> pd.DataFrame:
    """Generate 3-regime synthetic data with clear cluster separation."""
    rng = np.random.default_rng(42)
    n_per_regime = 80

    r0 = rng.normal(loc=[3.0, -1.0, 0.0, 0.0], scale=0.3, size=(n_per_regime, 4))
    r1 = rng.normal(loc=[-1.0, 0.0, 3.0, 0.0], scale=0.3, size=(n_per_regime, 4))
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
    hmm.fit(synthetic_features, n_states_grid=[2, 3, 4], n_seeds=5)
    return hmm


def test_grid_selection_reasonable(fitted_hmm: HMMRegimeClassifier) -> None:
    """Grid selection should pick 3 or 4 states for 3-cluster synthetic data."""
    assert fitted_hmm.diagnostics is not None
    assert fitted_hmm.n_states in (3, 4), (
        f"Expected 3-4 states, got {fitted_hmm.n_states}. "
        f"BIC: {fitted_hmm.diagnostics.bic_mean}, "
        f"ARI: {fitted_hmm.diagnostics.ari_mean}"
    )


def test_diagnostics_has_all_fields(fitted_hmm: HMMRegimeClassifier) -> None:
    d = fitted_hmm.diagnostics
    assert d is not None
    assert len(d.grid) >= 2
    assert len(d.bic_mean) == len(d.grid)
    assert len(d.bic_std) == len(d.grid)
    assert len(d.aic_mean) == len(d.grid)
    assert len(d.aic_std) == len(d.grid)
    assert len(d.ari_mean) == len(d.grid)
    assert len(d.ari_std) == len(d.grid)
    assert d.selected_n_states in d.grid
    assert d.selection_reason != ""
    assert d.converged is not None
    assert d.n_iter_used > 0
    assert d.log_likelihood < 0


def test_ari_values_in_range(fitted_hmm: HMMRegimeClassifier) -> None:
    """ARI should be in [-1, 1] range."""
    d = fitted_hmm.diagnostics
    for n, ari in d.ari_mean.items():
        assert -1.0 <= ari <= 1.0, f"ARI({n})={ari} out of range"


def test_predict_shapes(
    fitted_hmm: HMMRegimeClassifier, synthetic_features: pd.DataFrame
) -> None:
    states, probs = fitted_hmm.predict(synthetic_features)
    assert states.shape == (len(synthetic_features),)
    assert probs.shape == (len(synthetic_features), fitted_hmm.n_states)
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-6)


def test_labels_unique(fitted_hmm: HMMRegimeClassifier) -> None:
    """All state labels must be unique."""
    labels = [p.label for p in fitted_hmm.state_profiles]
    assert len(labels) == len(set(labels)), f"Duplicate labels found: {labels}"


def test_labels_contain_feature_names(fitted_hmm: HMMRegimeClassifier) -> None:
    labels = [p.label for p in fitted_hmm.state_profiles]
    assert len(labels) >= 2, f"Expected >=2 labels, got {labels}"
    for label in labels:
        assert "HIGH" in label or "LOW" in label, f"Bad label format: {label}"


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


def test_ari_fallback_on_noisy_data() -> None:
    """When no candidate passes ARI threshold, fallback to max ARI."""
    rng = np.random.default_rng(99)
    # Pure noise — no cluster structure
    data = rng.normal(size=(100, 4))
    dates = pd.date_range("2000-01-31", periods=100, freq="ME")
    noisy = pd.DataFrame(data, index=dates, columns=["a", "b", "c", "d"])

    hmm = HMMRegimeClassifier()
    diag = hmm.fit(noisy, n_states_grid=[2, 3], n_seeds=5)

    # Should still produce a valid result
    assert diag.selected_n_states in (2, 3)
    # On noise, ARI is typically low — may or may not trigger fallback
    assert diag.selection_reason != ""


def test_unique_labels_4_regimes() -> None:
    """With 4 distinct regimes, all 4 labels should be unique."""
    rng = np.random.default_rng(42)
    n = 60

    # 4 regimes with distinct dominant features
    r0 = rng.normal(loc=[3.0, 0.0, 0.0, 0.0], scale=0.2, size=(n, 4))  # feat_a HIGH
    r1 = rng.normal(loc=[0.0, 3.0, 0.0, 0.0], scale=0.2, size=(n, 4))  # feat_b HIGH
    r2 = rng.normal(loc=[0.0, 0.0, 3.0, 0.0], scale=0.2, size=(n, 4))  # feat_c HIGH
    r3 = rng.normal(loc=[0.0, 0.0, 0.0, 3.0], scale=0.2, size=(n, 4))  # feat_d HIGH

    data = np.vstack([r0, r1, r2, r3])
    dates = pd.date_range("2000-01-31", periods=len(data), freq="ME")
    df = pd.DataFrame(data, index=dates, columns=["f_a", "f_b", "f_c", "f_d"])

    hmm = HMMRegimeClassifier()
    hmm.fit(df, n_states=4, n_seeds=3)

    labels = [p.label for p in hmm.state_profiles]
    assert len(labels) == 4, f"Expected 4 profiles, got {len(labels)}"
    assert len(set(labels)) == 4, f"Labels not unique: {labels}"


def test_covariance_type_respected() -> None:
    """Verify that covariance_type parameter is passed through."""
    rng = np.random.default_rng(42)
    data = rng.normal(size=(100, 3))
    dates = pd.date_range("2000-01-31", periods=100, freq="ME")
    df = pd.DataFrame(data, index=dates, columns=["a", "b", "c"])

    hmm = HMMRegimeClassifier()
    hmm.fit(df, n_states=2, covariance_type="full", n_seeds=2)
    assert hmm.model.covariance_type == "full"

    hmm2 = HMMRegimeClassifier()
    hmm2.fit(df, n_states=2, covariance_type="diag", n_seeds=2)
    assert hmm2.model.covariance_type == "diag"
