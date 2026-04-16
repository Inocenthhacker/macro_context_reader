"""Tests for ZQ futures ingestion module."""
from pathlib import Path

import pandas as pd
import pytest

from macro_context_reader.market_pricing.fedwatch.zq_futures import (
    EARLIEST_AVAILABLE,
    FRONT_MONTHS,
    OUTPUT_DIR,
    _continuous_symbol,
    implied_rate_from_price,
    load_zq_chain,
)


class TestSymbolFormatting:
    def test_front_month(self):
        assert _continuous_symbol(0) == "ZQ.c.0"

    def test_last_chain(self):
        assert _continuous_symbol(FRONT_MONTHS - 1) == f"ZQ.c.{FRONT_MONTHS - 1}"

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            _continuous_symbol(FRONT_MONTHS)
        with pytest.raises(ValueError):
            _continuous_symbol(-1)


class TestImpliedRate:
    def test_zirp_era_price(self):
        # ZIRP: price ~99.80 → rate ~0.20%
        assert abs(implied_rate_from_price(99.80) - 0.20) < 0.01

    def test_hiking_cycle_price(self):
        # 2024 peak: price ~94.67 → rate ~5.33%
        assert abs(implied_rate_from_price(94.67) - 5.33) < 0.01

    def test_zero_rate_edge(self):
        assert implied_rate_from_price(100.0) == 0.0


@pytest.mark.integration
class TestPersistenceRoundtrip:
    """Tests that require the parquet cache to exist (post-ingestion)."""

    def test_all_parquets_exist(self):
        for n in range(FRONT_MONTHS):
            path = OUTPUT_DIR / f"{_continuous_symbol(n)}.parquet"
            assert path.exists(), f"Missing: {path}"

    def test_front_month_has_min_rows(self):
        df = load_zq_chain(0)
        # 2010-06-07 → present is ~15+ years × 250 business days ≈ 3750+ rows
        assert len(df) >= 3500, f"Too few rows in front-month: {len(df)}"

    def test_schema_consistent_across_chains(self):
        required_cols = {"open", "high", "low", "close", "volume"}
        for n in range(FRONT_MONTHS):
            df = load_zq_chain(n)
            assert set(df.columns) == required_cols, f"Chain {n} schema mismatch"

    def test_date_index_monotonic(self):
        for n in range(FRONT_MONTHS):
            df = load_zq_chain(n)
            assert df.index.is_monotonic_increasing, f"Chain {n} non-monotonic"

    def test_no_null_in_close(self):
        for n in range(FRONT_MONTHS):
            df = load_zq_chain(n)
            null_pct = df["close"].isna().mean()
            assert null_pct < 0.02, f"Chain {n} has {null_pct*100:.1f}% null close"

    def test_prices_in_plausible_range(self):
        """ZQ prices should be in [94, 100] range for 2010-2026 (rates 0-6%)."""
        for n in range(FRONT_MONTHS):
            df = load_zq_chain(n)
            assert df["close"].min() >= 93.0, f"Chain {n} has price < 93 (implies rate > 7%)"
            assert df["close"].max() <= 100.2, f"Chain {n} has price > 100.2 (negative rates?)"

    def test_front_month_starts_near_expected_date(self):
        df = load_zq_chain(0)
        first_date = df.index.min()
        expected = pd.Timestamp(EARLIEST_AVAILABLE)
        assert abs((first_date - expected).days) <= 7

    def test_roundtrip(self):
        df1 = load_zq_chain(0)
        tmp = OUTPUT_DIR / "_roundtrip_test.parquet"
        try:
            df1.to_parquet(tmp, engine="pyarrow", compression="snappy")
            df2 = pd.read_parquet(tmp)
            pd.testing.assert_frame_equal(df1, df2)
        finally:
            if tmp.exists():
                tmp.unlink()
