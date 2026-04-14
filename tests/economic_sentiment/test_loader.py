"""Tests for Cleveland Fed sentiment indices loader."""
import pandas as pd
import pytest

from macro_context_reader.economic_sentiment import (
    DISTRICT_NAMES,
    get_district_score,
    load_cleveland_fed_indices,
)


def test_loader_returns_dataframe():
    df = load_cleveland_fed_indices()
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 400


def test_all_districts_present():
    df = load_cleveland_fed_indices()
    for district in DISTRICT_NAMES:
        col = f"{district.replace(' ', '_').replace('.', '')}_score"
        assert col in df.columns, f"Missing column for {district}"


def test_scores_in_valid_range():
    df = load_cleveland_fed_indices()
    score_cols = [c for c in df.columns if c.endswith("_score")]
    for col in score_cols:
        assert df[col].dropna().between(-1.0, 1.0).all(), (
            f"{col} has values outside [-1, 1]"
        )


def test_national_score_exists():
    df = load_cleveland_fed_indices()
    assert "national_score" in df.columns
    assert df["national_score"].notna().sum() > 400


def test_consensus_score_exists():
    df = load_cleveland_fed_indices()
    assert "consensus_score" in df.columns


def test_divergence_computed():
    df = load_cleveland_fed_indices()
    assert "national_consensus_divergence" in df.columns
    expected = df["national_score"] - df["consensus_score"]
    pd.testing.assert_series_equal(
        df["national_consensus_divergence"],
        expected,
        check_names=False,
    )


def test_date_filter_start():
    df = load_cleveland_fed_indices(start_date="2020-01")
    assert df["publication_date"].min() >= pd.Timestamp("2020-01-01")


def test_date_filter_end():
    df = load_cleveland_fed_indices(end_date="2020-12")
    assert df["publication_date"].max() <= pd.Timestamp("2020-12-31")


def test_covid_recession_shows_negative_sentiment():
    df = load_cleveland_fed_indices(start_date="2020-03", end_date="2020-07")
    assert (df["consensus_score"] < -0.3).any(), (
        "COVID period should show strong negative sentiment"
    )


def test_get_district_score_returns_float():
    df = load_cleveland_fed_indices()
    first_date = df["publication_date"].iloc[0]
    score = get_district_score(df, "Boston", first_date)
    assert score is None or (-1.0 <= score <= 1.0)


def test_get_district_score_invalid_district_raises():
    df = load_cleveland_fed_indices()
    first_date = df["publication_date"].iloc[0]
    with pytest.raises(KeyError):
        get_district_score(df, "Invalid District", first_date)


def test_missing_csv_raises_helpful_error(tmp_path):
    fake_path = tmp_path / "nonexistent.csv"
    with pytest.raises(FileNotFoundError, match="openicpsr"):
        load_cleveland_fed_indices(csv_path=fake_path)
