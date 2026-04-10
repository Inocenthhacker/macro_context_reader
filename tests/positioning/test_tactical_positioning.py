"""Tests for tactical composite score (Layer 4B aggregation)."""

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.positioning.tactical_composite import compute_tactical_score


@pytest.fixture(scope="module")
def dates() -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=10)


@pytest.fixture(scope="module")
def df_oi(dates: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({"date": dates, "oi_signal": np.linspace(-1, 1, 10)})


@pytest.fixture(scope="module")
def df_options(dates: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({"date": dates, "options_signal": np.linspace(1, -1, 10)})


@pytest.fixture(scope="module")
def df_retail(dates: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({"date": dates, "retail_signal": np.linspace(-0.5, 0.5, 10)})


def test_tactical_score_range(
    df_oi: pd.DataFrame, df_options: pd.DataFrame, df_retail: pd.DataFrame
) -> None:
    result = compute_tactical_score(df_oi, df_options, df_retail)
    valid = result["tactical_score"].dropna()
    assert (valid >= -1).all() and (valid <= 1).all()


def test_graceful_degradation_one_source_missing(
    df_oi: pd.DataFrame, df_retail: pd.DataFrame
) -> None:
    dates = df_oi["date"]
    df_options_nan = pd.DataFrame({"date": dates, "options_signal": [np.nan] * len(dates)})
    result = compute_tactical_score(df_oi, df_options_nan, df_retail)
    # Weights redistributed: oi 0.4/(0.4+0.25)=0.615385, retail 0.25/0.65=0.384615
    expected_w_oi = round(0.4 / 0.65, 6)
    expected_w_retail = round(0.25 / 0.65, 6)
    for i in range(len(result)):
        row = result.iloc[i]
        expected = expected_w_oi * df_oi.iloc[i]["oi_signal"] + expected_w_retail * df_retail.iloc[i]["retail_signal"]
        assert abs(row["tactical_score"] - expected) < 1e-5


def test_graceful_degradation_two_sources_missing(df_oi: pd.DataFrame) -> None:
    dates = df_oi["date"]
    df_options_nan = pd.DataFrame({"date": dates, "options_signal": [np.nan] * len(dates)})
    df_retail_nan = pd.DataFrame({"date": dates, "retail_signal": [np.nan] * len(dates)})
    result = compute_tactical_score(df_oi, df_options_nan, df_retail_nan)
    # Only OI available → tactical_score == oi_signal
    np.testing.assert_array_almost_equal(result["tactical_score"].values, df_oi["oi_signal"].values)


def test_sources_available_count(
    df_oi: pd.DataFrame, df_options: pd.DataFrame, df_retail: pd.DataFrame
) -> None:
    dates = df_oi["date"]
    # Make options NaN for first 3 rows, retail NaN for first 5
    df_opt = df_options.copy()
    df_opt.loc[:2, "options_signal"] = np.nan
    df_ret = df_retail.copy()
    df_ret.loc[:4, "retail_signal"] = np.nan

    result = compute_tactical_score(df_oi, df_opt, df_ret)
    # Rows 0-2: oi only → 1 source; rows 3-4: oi+options → 2; rows 5-9: all 3
    assert result.iloc[0]["sources_available"] == 1
    assert result.iloc[3]["sources_available"] == 2
    assert result.iloc[9]["sources_available"] == 3


def test_all_nan_row() -> None:
    dates = pd.date_range("2024-01-01", periods=3)
    df_oi = pd.DataFrame({"date": dates, "oi_signal": [np.nan, 1.0, np.nan]})
    df_opt = pd.DataFrame({"date": dates, "options_signal": [np.nan, -0.5, np.nan]})
    df_ret = pd.DataFrame({"date": dates, "retail_signal": [np.nan, 0.3, np.nan]})
    result = compute_tactical_score(df_oi, df_opt, df_ret)
    # Row 0 and 2: all NaN → tactical_score NaN
    assert pd.isna(result.iloc[0]["tactical_score"])
    assert pd.isna(result.iloc[2]["tactical_score"])
    # Row 1: valid
    assert not pd.isna(result.iloc[1]["tactical_score"])
