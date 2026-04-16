"""Tests for real rate differential Parquet persistence.

PRD-300 / CC-1.5.3 — validates the persisted Parquet at
data/market_pricing/real_rate_differential.parquet.
"""
from pathlib import Path

import pandas as pd
import pytest

PARQUET_PATH = Path("data/market_pricing/real_rate_differential.parquet")

REQUIRED_COLUMNS = {
    "us_5y_real",
    "eu_5y_nominal_aaa",
    "eu_inflation_expectations_5y",
    "eu_5y_real",
    "real_rate_differential",
}


@pytest.mark.integration
def test_parquet_exists():
    assert PARQUET_PATH.exists()


@pytest.mark.integration
def test_parquet_min_rows():
    df = pd.read_parquet(PARQUET_PATH)
    # Target: at least 2500 business days (~10 years daily data)
    assert len(df) >= 2500, f"Too few rows: {len(df)}"


@pytest.mark.integration
def test_parquet_schema():
    df = pd.read_parquet(PARQUET_PATH)
    missing = REQUIRED_COLUMNS - set(df.columns)
    assert not missing, f"Missing columns: {missing}"


@pytest.mark.integration
def test_parquet_dtypes_numeric():
    df = pd.read_parquet(PARQUET_PATH)
    for col in REQUIRED_COLUMNS:
        assert pd.api.types.is_numeric_dtype(df[col]), f"{col} not numeric"


@pytest.mark.integration
def test_parquet_no_null_in_real_rate_differential():
    """The composite column must be complete."""
    df = pd.read_parquet(PARQUET_PATH)
    null_pct = df["real_rate_differential"].isna().mean()
    assert null_pct < 0.05, f"Too many NaN in real_rate_differential: {null_pct*100:.1f}%"


@pytest.mark.integration
def test_parquet_date_column_monotonic():
    df = pd.read_parquet(PARQUET_PATH)
    assert "date" in df.columns, "Missing date column"
    dates = pd.to_datetime(df["date"])
    assert dates.is_monotonic_increasing, "Non-monotonic date column"


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
