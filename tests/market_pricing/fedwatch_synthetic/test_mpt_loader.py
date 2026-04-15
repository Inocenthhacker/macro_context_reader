"""Tests for Atlanta Fed MPT loader."""
from __future__ import annotations

import pandas as pd
import pytest

from macro_context_reader.market_pricing.fedwatch.synthetic.mpt_loader import (
    OUTPUT_PARQUET,
    build_mpt_dataset,
    load_mpt_history,
    parse_bucket_field,
    reshape_mpt_to_fedwatch_schema,
)


class TestParseBucketField:
    def test_standard_format(self):
        assert parse_bucket_field("Prob: 475bps - 500bps") == (475, 500)

    def test_extra_whitespace(self):
        assert parse_bucket_field("Prob:  475bps  -  500bps") == (475, 500)

    def test_zero_lower_bound(self):
        assert parse_bucket_field("Prob: 0bps - 25bps") == (0, 25)

    def test_returns_none_for_percentile(self):
        assert parse_bucket_field("Rate: 25th percentile") is None

    def test_returns_none_for_mean(self):
        assert parse_bucket_field("Rate: mean") is None

    def test_returns_none_for_summary_hike(self):
        assert parse_bucket_field("Prob: hike") is None

    def test_returns_none_for_summary_cut(self):
        assert parse_bucket_field("Prob: cut") is None

    def test_returns_none_for_garbage(self):
        assert parse_bucket_field("not a bucket field") is None


class TestReshape:
    @pytest.fixture
    def sample_raw(self):
        return pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01"] * 4),
            "reference_start": pd.to_datetime(["2024-03-01"] * 4),
            "target_range": ["475bps - 500bps"] * 4,
            "field": [
                "Prob: 475bps - 500bps",
                "Prob: 500bps - 525bps",
                "Rate: mean",
                "Prob: hike",
            ],
            "value": [80.0, 15.0, 4.85, 18.0],
        })

    def test_filters_non_bucket_fields(self, sample_raw):
        out = reshape_mpt_to_fedwatch_schema(sample_raw)
        assert len(out) == 2

    def test_schema_columns(self, sample_raw):
        out = reshape_mpt_to_fedwatch_schema(sample_raw)
        expected_cols = {
            "observation_date", "meeting_date",
            "rate_bucket_low", "rate_bucket_high",
            "probability", "source",
        }
        assert set(out.columns) == expected_cols

    def test_bps_to_percent(self, sample_raw):
        out = reshape_mpt_to_fedwatch_schema(sample_raw)
        assert out["rate_bucket_low"].iloc[0] == 4.75
        assert out["rate_bucket_high"].iloc[0] == 5.00

    def test_probability_fraction(self, sample_raw):
        out = reshape_mpt_to_fedwatch_schema(sample_raw)
        assert out["probability"].iloc[0] == 0.80

    def test_source_constant(self, sample_raw):
        out = reshape_mpt_to_fedwatch_schema(sample_raw)
        assert (out["source"] == "atlanta_fed_mpt").all()

    def test_drops_zero_probability(self):
        raw = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "reference_start": pd.to_datetime(["2024-03-01", "2024-03-01"]),
            "target_range": ["475bps - 500bps"] * 2,
            "field": ["Prob: 475bps - 500bps", "Prob: 100bps - 125bps"],
            "value": [100.0, 0.0],
        })
        out = reshape_mpt_to_fedwatch_schema(raw)
        assert len(out) == 1

    def test_sorted_output(self, sample_raw):
        out = reshape_mpt_to_fedwatch_schema(sample_raw)
        assert out["rate_bucket_low"].is_monotonic_increasing


@pytest.mark.integration
class TestBuildMPTDataset:
    """Integration tests — require network access to Atlanta Fed."""

    def test_build_returns_dataframe(self):
        df = build_mpt_dataset(force_download=True)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 1000

    def test_persisted_parquet_exists(self):
        build_mpt_dataset(force_download=False)
        assert OUTPUT_PARQUET.exists()
        assert OUTPUT_PARQUET.stat().st_size > 10000

    def test_date_range_2023_to_present(self):
        df = build_mpt_dataset(force_download=False)
        assert df["observation_date"].min() >= pd.Timestamp("2023-01-01")
        assert df["observation_date"].max() >= pd.Timestamp("2025-01-01")

    def test_schema_superset_of_manual(self):
        from macro_context_reader.market_pricing.fedwatch import load_fedwatch_history
        synthetic = build_mpt_dataset(force_download=False)
        manual = load_fedwatch_history(rebuild=False)

        manual_core = set(manual.columns) - {"source", "source_snapshot_date"}
        synth_core = set(synthetic.columns) - {"source"}
        assert manual_core.issubset(synth_core)

    def test_probabilities_sum_validation(self):
        df = build_mpt_dataset(force_download=False)
        sums = df.groupby(["observation_date", "meeting_date"])["probability"].sum()
        within_tolerance = (sums >= 0.95).mean()
        assert within_tolerance > 0.9


@pytest.mark.integration
class TestLoadMPTHistory:
    def test_loads_after_build(self):
        build_mpt_dataset(force_download=False)
        df = load_mpt_history()
        assert len(df) > 0

    def test_date_filter_start(self):
        df = load_mpt_history(start_date="2024-01-01")
        assert df["observation_date"].min() >= pd.Timestamp("2024-01-01")

    def test_date_filter_end(self):
        df = load_mpt_history(end_date="2024-06-30")
        assert df["observation_date"].max() <= pd.Timestamp("2024-06-30")
