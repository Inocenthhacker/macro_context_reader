"""Tests for HP filter decomposition."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.divergence.decomposition import (
    DecompositionResult,
    hp_decompose,
)


@pytest.fixture
def synthetic_signal() -> pd.Series:
    """Synthetic signal: linear trend + noise."""
    dates = pd.date_range("2020-01-01", periods=500, freq="D")
    trend = np.linspace(0, 10, 500)
    noise = np.random.RandomState(42).normal(0, 1, 500)
    return pd.Series(trend + noise, index=dates, name="signal")


class TestHPDecompose:
    def test_returns_decomposition_result(self, synthetic_signal):
        result = hp_decompose(synthetic_signal)
        assert isinstance(result, DecompositionResult)
        assert result.method == "hp_filter"

    def test_components_sum_to_original(self, synthetic_signal):
        result = hp_decompose(synthetic_signal)
        reconstructed = result.deep_current + result.surface_wave
        np.testing.assert_allclose(reconstructed.values, synthetic_signal.values, atol=1e-6)

    def test_deep_current_smoother_than_original(self, synthetic_signal):
        result = hp_decompose(synthetic_signal)
        assert result.deep_current.std() < synthetic_signal.std()

    def test_residual_is_none(self, synthetic_signal):
        result = hp_decompose(synthetic_signal)
        assert result.residual is None

    def test_metadata_contains_lambda(self, synthetic_signal):
        result = hp_decompose(synthetic_signal)
        assert "lambda" in result.metadata
        assert result.metadata["n_obs"] == 500

    def test_raises_on_short_series(self):
        short = pd.Series(
            [1.0] * 30,
            index=pd.date_range("2024-01-01", periods=30, freq="D")
        )
        with pytest.raises(ValueError, match="too short"):
            hp_decompose(short)

    def test_raises_on_nan(self, synthetic_signal):
        synthetic_signal.iloc[100] = np.nan
        with pytest.raises(ValueError, match="NaN"):
            hp_decompose(synthetic_signal)

    def test_raises_on_non_datetime_index(self):
        s = pd.Series([1.0, 2.0, 3.0] * 100)
        with pytest.raises(ValueError, match="DatetimeIndex"):
            hp_decompose(s)

    def test_custom_lambda_smoother(self, synthetic_signal):
        result_default = hp_decompose(synthetic_signal)
        result_smooth = hp_decompose(synthetic_signal, lamb=1e8)
        assert result_smooth.deep_current.std() <= result_default.deep_current.std()
