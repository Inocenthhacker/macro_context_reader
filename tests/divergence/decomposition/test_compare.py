"""Tests for decomposition comparison helper."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.divergence.decomposition import (
    compare_methods,
    compare_metadata,
)


@pytest.fixture
def synthetic_signal() -> pd.Series:
    dates = pd.date_range("2020-01-01", periods=500, freq="D")
    trend = np.linspace(0, 10, 500)
    noise = np.random.RandomState(42).normal(0, 0.5, 500)
    return pd.Series(trend + noise, index=dates, name="signal")


class TestCompareMethods:
    def test_returns_dataframe(self, synthetic_signal):
        df = compare_methods(synthetic_signal)
        assert isinstance(df, pd.DataFrame)

    def test_has_expected_columns(self, synthetic_signal):
        df = compare_methods(synthetic_signal)
        expected = ["original", "hp_deep", "hp_surface", "emd_deep", "emd_surface"]
        assert list(df.columns) == expected

    def test_index_matches_input(self, synthetic_signal):
        df = compare_methods(synthetic_signal)
        pd.testing.assert_index_equal(df.index, synthetic_signal.index)

    def test_no_nan_in_output(self, synthetic_signal):
        df = compare_methods(synthetic_signal)
        assert not df.isna().any().any()


class TestCompareMetadata:
    def test_returns_dict(self, synthetic_signal):
        meta = compare_metadata(synthetic_signal)
        assert isinstance(meta, dict)
        assert "hp_filter" in meta
        assert "emd" in meta

    def test_metadata_completeness(self, synthetic_signal):
        meta = compare_metadata(synthetic_signal)
        assert "lambda" in meta["hp_filter"]
        assert "n_imfs" in meta["emd"]
