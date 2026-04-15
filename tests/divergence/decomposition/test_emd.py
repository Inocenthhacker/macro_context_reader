"""Tests for EMD decomposition."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.divergence.decomposition import (
    DecompositionResult,
    emd_decompose,
)


@pytest.fixture
def synthetic_signal() -> pd.Series:
    """Synthetic: sine wave + linear trend."""
    dates = pd.date_range("2020-01-01", periods=500, freq="D")
    trend = np.linspace(0, 10, 500)
    oscillation = 2 * np.sin(2 * np.pi * np.arange(500) / 50)
    return pd.Series(trend + oscillation, index=dates, name="signal")


class TestEMDDecompose:
    def test_returns_decomposition_result(self, synthetic_signal):
        result = emd_decompose(synthetic_signal)
        assert isinstance(result, DecompositionResult)
        assert result.method == "emd"

    def test_components_approximately_sum_to_original(self, synthetic_signal):
        result = emd_decompose(synthetic_signal)
        reconstructed = result.deep_current + result.surface_wave + result.residual
        np.testing.assert_allclose(reconstructed.values, synthetic_signal.values, atol=1e-6)

    def test_residual_is_small(self, synthetic_signal):
        result = emd_decompose(synthetic_signal)
        assert result.metadata["residual_max_abs"] < 1e-6

    def test_deep_current_captures_trend(self, synthetic_signal):
        result = emd_decompose(synthetic_signal)
        linear_trend = np.linspace(0, 10, 500)
        correlation = np.corrcoef(result.deep_current.values, linear_trend)[0, 1]
        assert correlation > 0.9

    def test_metadata_contains_n_imfs(self, synthetic_signal):
        result = emd_decompose(synthetic_signal)
        assert "n_imfs" in result.metadata
        assert result.metadata["n_imfs"] >= 2

    def test_raises_on_short_series(self):
        short = pd.Series(
            np.random.randn(20),
            index=pd.date_range("2024-01-01", periods=20, freq="D")
        )
        with pytest.raises(ValueError, match="too short"):
            emd_decompose(short)

    def test_raises_on_nan(self, synthetic_signal):
        synthetic_signal.iloc[100] = np.nan
        with pytest.raises(ValueError, match="NaN"):
            emd_decompose(synthetic_signal)

    def test_handles_smooth_signal(self):
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        linear = pd.Series(np.linspace(0, 1, 100), index=dates)
        result = emd_decompose(linear)
        assert isinstance(result, DecompositionResult)
