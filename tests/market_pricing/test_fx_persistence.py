"""Tests for EUR/USD persistence layer (FX backfill)."""
from __future__ import annotations

import pandas as pd
import pytest

from macro_context_reader.market_pricing.fx import (
    FX_PARQUET,
    load_fx_history,
)


@pytest.fixture(scope="module")
def ensure_parquet():
    """Ensure fx.parquet exists (single rebuild per test module).

    FRED API is occasionally flaky; tests that need Parquet use this fixture
    instead of each calling rebuild=True. If Parquet already persisted (e.g. by
    smoke test), no network call is made.
    """
    if not FX_PARQUET.exists():
        load_fx_history(rebuild=True)
    return FX_PARQUET


@pytest.mark.integration
def test_rebuild_from_fred_creates_parquet():
    """Integration: forces fresh FRED fetch. Deselected with -m 'not integration'."""
    load_fx_history(rebuild=True)
    assert FX_PARQUET.exists()
    assert FX_PARQUET.stat().st_size > 1000


class TestLoadFxHistory:
    def test_returns_dataframe(self, ensure_parquet):
        df = load_fx_history()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 1000

    def test_has_datetime_index(self, ensure_parquet):
        df = load_fx_history()
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_eurusd_column_present(self, ensure_parquet):
        df = load_fx_history()
        assert "eurusd" in df.columns

    def test_no_nan_after_load(self, ensure_parquet):
        df = load_fx_history()
        assert not df["eurusd"].isna().any()

    def test_eurusd_in_reasonable_range(self, ensure_parquet):
        df = load_fx_history()
        assert df["eurusd"].min() > 0.5
        assert df["eurusd"].max() < 2.0

    def test_date_range_filter_start(self, ensure_parquet):
        df = load_fx_history(start_date="2020-01-01")
        assert df.index.min() >= pd.Timestamp("2020-01-01")

    def test_date_range_filter_end(self, ensure_parquet):
        df = load_fx_history(end_date="2020-12-31")
        assert df.index.max() <= pd.Timestamp("2020-12-31")

    def test_date_range_filter_both(self, ensure_parquet):
        df = load_fx_history(start_date="2020-01-01", end_date="2020-12-31")
        assert df.index.min() >= pd.Timestamp("2020-01-01")
        assert df.index.max() <= pd.Timestamp("2020-12-31")

    def test_starts_at_or_after_2015_04(self, ensure_parquet):
        df = load_fx_history()
        assert df.index.min() >= pd.Timestamp("2015-04-01")

    def test_parquet_file_exists_and_nontrivial(self, ensure_parquet):
        assert FX_PARQUET.exists()
        assert FX_PARQUET.stat().st_size > 1000

    def test_load_uses_cache(self, ensure_parquet):
        df = load_fx_history()
        assert len(df) > 0
