"""Tests for FedWatch surprise Parquet persistence.

PRD-300 / CC-1.5.2 — validates the persisted Parquet at
data/market_pricing/fedwatch_surprise.parquet.
"""
from pathlib import Path

import pandas as pd
import pytest

PARQUET_PATH = Path("data/market_pricing/fedwatch_surprise.parquet")

REQUIRED_COLUMNS = {
    "market_implied_change_bps",
    "actual_change_bps",
    "surprise_bps",
    "surprise_zscore",
}


@pytest.mark.integration
def test_parquet_exists():
    assert PARQUET_PATH.exists()


@pytest.mark.integration
def test_parquet_min_meetings():
    df = pd.read_parquet(PARQUET_PATH)
    # 2023-2026 should have ~12 past FOMC meetings with FedWatch data
    assert len(df) >= 10, f"Too few meetings: {len(df)}"


@pytest.mark.integration
def test_parquet_schema():
    df = pd.read_parquet(PARQUET_PATH)
    missing = REQUIRED_COLUMNS - set(df.columns)
    assert not missing, f"Missing columns: {missing}"


@pytest.mark.integration
def test_parquet_dtypes():
    df = pd.read_parquet(PARQUET_PATH)
    for col in REQUIRED_COLUMNS:
        assert pd.api.types.is_numeric_dtype(df[col]), f"{col} not numeric"


@pytest.mark.integration
def test_parquet_no_null_in_core_columns():
    df = pd.read_parquet(PARQUET_PATH)
    for col in ["market_implied_change_bps", "actual_change_bps", "surprise_bps"]:
        null_count = df[col].isna().sum()
        assert null_count == 0, f"{col} has {null_count} NaN"


@pytest.mark.integration
def test_surprise_is_difference():
    """surprise_bps = actual - market_implied (identity check)."""
    df = pd.read_parquet(PARQUET_PATH)
    computed = df["actual_change_bps"] - df["market_implied_change_bps"]
    pd.testing.assert_series_equal(
        df["surprise_bps"], computed, check_names=False, atol=0.01
    )


@pytest.mark.integration
def test_parquet_chronological():
    df = pd.read_parquet(PARQUET_PATH)
    if isinstance(df.index, pd.DatetimeIndex):
        assert df.index.is_monotonic_increasing, "Non-monotonic meeting_date index"


@pytest.mark.integration
def test_parquet_roundtrip():
    df1 = pd.read_parquet(PARQUET_PATH)
    tmp = PARQUET_PATH.parent / "_roundtrip_test.parquet"
    try:
        df1.to_parquet(tmp, engine="pyarrow", compression="snappy")
        df2 = pd.read_parquet(tmp)
        pd.testing.assert_frame_equal(df1, df2)
    finally:
        if tmp.exists():
            tmp.unlink()
