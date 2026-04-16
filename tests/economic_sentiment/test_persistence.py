"""Tests for Cleveland Fed economic sentiment Parquet persistence layer.

PRD-300 / CC-1.5.4 — validates the persisted Parquet at
data/economic_sentiment/cleveland_fed_indices.parquet.
"""
from pathlib import Path

import pandas as pd
import pytest

PARQUET_PATH = Path("data/economic_sentiment/cleveland_fed_indices.parquet")

CORE_COLUMNS = ["national_score", "consensus_score", "national_consensus_divergence"]


@pytest.mark.integration
def test_parquet_exists():
    """The persisted Parquet file must exist after CC-1.5.4 runs."""
    assert PARQUET_PATH.exists(), f"Missing: {PARQUET_PATH}"


@pytest.mark.integration
def test_parquet_has_min_rows():
    """Cleveland Fed has multi-year history; expect substantial row count."""
    df = pd.read_parquet(PARQUET_PATH)
    assert len(df) >= 100, f"Too few rows: {len(df)}"


@pytest.mark.integration
def test_parquet_no_null_core_columns():
    """Core sentiment columns (national, consensus, divergence) must have zero NaN.

    District columns may have sparse NaN for months where a district
    report was missing — that is legitimate and not tested here.
    """
    df = pd.read_parquet(PARQUET_PATH)
    for col in CORE_COLUMNS:
        assert col in df.columns, f"Missing core column: {col}"
        null_count = df[col].isna().sum()
        assert null_count == 0, f"{col} has {null_count} NaN values"


@pytest.mark.integration
def test_parquet_chronological():
    """publication_date must be strictly monotonic increasing."""
    df = pd.read_parquet(PARQUET_PATH)
    assert "publication_date" in df.columns, "Missing publication_date column"
    dates = pd.to_datetime(df["publication_date"])
    assert dates.is_monotonic_increasing, "Non-monotonic publication_date"


@pytest.mark.integration
def test_parquet_roundtrip():
    """Read -> write -> read must produce identical DataFrame."""
    df1 = pd.read_parquet(PARQUET_PATH)
    tmp = PARQUET_PATH.parent / "_roundtrip_test.parquet"
    try:
        df1.to_parquet(tmp, engine="pyarrow", compression="snappy")
        df2 = pd.read_parquet(tmp)
        pd.testing.assert_frame_equal(df1, df2)
    finally:
        if tmp.exists():
            tmp.unlink()
