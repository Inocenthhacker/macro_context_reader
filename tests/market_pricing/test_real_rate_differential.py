"""Tests pentru real_rate_differential.py.

Unit tests cu DataFrames sintetice — zero network calls.
Integration test cu @pytest.mark.integration.

Refs: PRD-200 CC-6
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from pydantic import ValidationError

from macro_context_reader.market_pricing.real_rate_differential import (
    compute_real_rate_differential,
    save_real_rate_differential_parquet,
    _validate_rows,
)
from macro_context_reader.market_pricing.schemas import RealRateDifferentialRow


# ─── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def daily_dates():
    """100 business days for synthetic tests."""
    return pd.date_range("2024-01-01", periods=100, freq="B")


@pytest.fixture
def synthetic_us_rates(daily_dates):
    """Synthetic US rates DataFrame."""
    return pd.DataFrame({
        "date": daily_dates,
        "us_5y_nominal": [3.5] * len(daily_dates),
        "us_5y_real": [1.5] * len(daily_dates),
        "us_5y_breakeven": [2.0] * len(daily_dates),
    })


@pytest.fixture
def synthetic_eu_rates(daily_dates):
    """Synthetic EU rates DataFrame."""
    return pd.DataFrame({
        "date": daily_dates,
        "eu_5y_nominal_aaa": [2.5] * len(daily_dates),
        "eu_5y_nominal_all": [2.8] * len(daily_dates),
        "eu_credit_stress_5y": [0.3] * len(daily_dates),
    })


@pytest.fixture
def synthetic_eu_inflation(daily_dates):
    """Synthetic quarterly SPF DataFrame that covers the daily range."""
    # 2 quarterly observations that bracket the 100 business days
    return pd.DataFrame({
        "date": [
            datetime(2023, 12, 31),  # before range — will forward-fill into Jan
            datetime(2024, 3, 31),   # covers mid-range
            datetime(2024, 6, 30),   # covers tail
        ],
        "eu_inflation_expectations_5y": [2.0, 2.1, 2.05],
    })


# ─── Schema tests ──────────────────────────────────────────────────

def test_schema_validation_valid_row():
    """RealRateDifferentialRow acceptă un rând valid."""
    row = RealRateDifferentialRow(
        date=datetime(2024, 3, 15),
        us_5y_real=1.5,
        eu_5y_nominal_aaa=2.5,
        eu_inflation_expectations_5y=2.0,
        eu_5y_real=0.5,
        real_rate_differential=1.0,
    )
    assert row.real_rate_differential == 1.0


def test_schema_validation_rejects_nan():
    """RealRateDifferentialRow rejectează NaN."""
    with pytest.raises(ValidationError):
        RealRateDifferentialRow(
            date=datetime(2024, 3, 15),
            us_5y_real=float("nan"),
            eu_5y_nominal_aaa=2.5,
            eu_inflation_expectations_5y=2.0,
            eu_5y_real=0.5,
            real_rate_differential=1.0,
        )


def test_validate_rows_catches_invalid():
    """_validate_rows raise pe DataFrame cu NaN."""
    bad_df = pd.DataFrame({
        "date": [datetime(2024, 3, 15)],
        "us_5y_real": [float("nan")],
        "eu_5y_nominal_aaa": [2.5],
        "eu_inflation_expectations_5y": [2.0],
        "eu_5y_real": [0.5],
        "real_rate_differential": [float("nan")],
    })
    with pytest.raises(ValidationError):
        _validate_rows(bad_df)


# ─── Logic tests ───────────────────────────────────────────────────

def test_eu_real_yield_computation(
    synthetic_us_rates, synthetic_eu_rates, synthetic_eu_inflation
):
    """eu_5y_real == eu_5y_nominal_aaa - eu_inflation_expectations_5y."""
    df = compute_real_rate_differential(
        us_rates_df=synthetic_us_rates,
        eu_rates_df=synthetic_eu_rates,
        eu_inflation_df=synthetic_eu_inflation,
    )
    computed = df["eu_5y_nominal_aaa"] - df["eu_inflation_expectations_5y"]
    pd.testing.assert_series_equal(
        df["eu_5y_real"], computed, check_names=False
    )


def test_real_rate_differential_computation(
    synthetic_us_rates, synthetic_eu_rates, synthetic_eu_inflation
):
    """real_rate_differential == us_5y_real - eu_5y_real."""
    df = compute_real_rate_differential(
        us_rates_df=synthetic_us_rates,
        eu_rates_df=synthetic_eu_rates,
        eu_inflation_df=synthetic_eu_inflation,
    )
    computed = df["us_5y_real"] - df["eu_5y_real"]
    pd.testing.assert_series_equal(
        df["real_rate_differential"], computed, check_names=False
    )


def test_forward_fill_within_limit(daily_dates):
    """SPF at 30-day gap: daily rows in between are forward-filled."""
    us_df = pd.DataFrame({
        "date": daily_dates[:60],
        "us_5y_real": [1.5] * 60,
        "us_5y_nominal": [3.5] * 60,
        "us_5y_breakeven": [2.0] * 60,
    })
    eu_df = pd.DataFrame({
        "date": daily_dates[:60],
        "eu_5y_nominal_aaa": [2.5] * 60,
        "eu_5y_nominal_all": [2.8] * 60,
        "eu_credit_stress_5y": [0.3] * 60,
    })
    # Two SPF obs 30 business days apart — well within 95-day limit
    spf_df = pd.DataFrame({
        "date": [daily_dates[0], daily_dates[30]],
        "eu_inflation_expectations_5y": [2.0, 2.1],
    })
    df = compute_real_rate_differential(
        us_rates_df=us_df,
        eu_rates_df=eu_df,
        eu_inflation_df=spf_df,
        forward_fill_limit_days=95,
    )
    # All 60 rows should survive (both SPF obs cover the range with ffill)
    assert len(df) == 60
    assert df["eu_inflation_expectations_5y"].notna().all()


def test_forward_fill_exceeds_limit():
    """Gap >95 days in SPF → trailing rows dropped."""
    dates = pd.date_range("2024-01-01", periods=150, freq="B")
    us_df = pd.DataFrame({
        "date": dates,
        "us_5y_real": [1.5] * 150,
        "us_5y_nominal": [3.5] * 150,
        "us_5y_breakeven": [2.0] * 150,
    })
    eu_df = pd.DataFrame({
        "date": dates,
        "eu_5y_nominal_aaa": [2.5] * 150,
        "eu_5y_nominal_all": [2.8] * 150,
        "eu_credit_stress_5y": [0.3] * 150,
    })
    # Single SPF obs at the start only — 150 business days ≈ 210 calendar days
    spf_df = pd.DataFrame({
        "date": [dates[0]],
        "eu_inflation_expectations_5y": [2.0],
    })
    df = compute_real_rate_differential(
        us_rates_df=us_df,
        eu_rates_df=eu_df,
        eu_inflation_df=spf_df,
        forward_fill_limit_days=95,
    )
    # Should have fewer than 150 rows — those beyond 95 days dropped
    assert len(df) < 150
    assert len(df) > 0
    assert df["eu_inflation_expectations_5y"].notna().all()


def test_alignment_us_eu_daily():
    """Inner join with slightly different US/EU date sets."""
    us_dates = pd.date_range("2024-01-01", periods=50, freq="B")
    eu_dates = pd.date_range("2024-01-03", periods=50, freq="B")  # offset by 2 days
    us_df = pd.DataFrame({
        "date": us_dates,
        "us_5y_real": [1.5] * 50,
        "us_5y_nominal": [3.5] * 50,
        "us_5y_breakeven": [2.0] * 50,
    })
    eu_df = pd.DataFrame({
        "date": eu_dates,
        "eu_5y_nominal_aaa": [2.5] * 50,
        "eu_5y_nominal_all": [2.8] * 50,
        "eu_credit_stress_5y": [0.3] * 50,
    })
    spf_df = pd.DataFrame({
        "date": [datetime(2023, 12, 31)],
        "eu_inflation_expectations_5y": [2.0],
    })
    df = compute_real_rate_differential(
        us_rates_df=us_df,
        eu_rates_df=eu_df,
        eu_inflation_df=spf_df,
    )
    # Inner join: only overlapping dates
    overlap = set(us_dates) & set(eu_dates)
    assert len(df) == len(overlap)


def test_pre_validation_range_warning():
    """Warning logged when SPF doesn't cover full daily range."""
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    us_df = pd.DataFrame({
        "date": dates,
        "us_5y_real": [1.5] * 50,
        "us_5y_nominal": [3.5] * 50,
        "us_5y_breakeven": [2.0] * 50,
    })
    eu_df = pd.DataFrame({
        "date": dates,
        "eu_5y_nominal_aaa": [2.5] * 50,
        "eu_5y_nominal_all": [2.8] * 50,
        "eu_credit_stress_5y": [0.3] * 50,
    })
    # SPF starts later than daily data
    spf_df = pd.DataFrame({
        "date": [dates[20]],  # starts 20 business days in
        "eu_inflation_expectations_5y": [2.0],
    })
    with pytest.warns(UserWarning, match="SPF starts at"):
        compute_real_rate_differential(
            us_rates_df=us_df,
            eu_rates_df=eu_df,
            eu_inflation_df=spf_df,
        )


# ─── Persistence tests ────────────────────────────────────────────

def test_save_parquet_roundtrip(
    synthetic_us_rates, synthetic_eu_rates, synthetic_eu_inflation, tmp_path
):
    """save + read roundtrip păstrează datele."""
    df = compute_real_rate_differential(
        us_rates_df=synthetic_us_rates,
        eu_rates_df=synthetic_eu_rates,
        eu_inflation_df=synthetic_eu_inflation,
    )
    output = tmp_path / "rrd.parquet"
    result = save_real_rate_differential_parquet(df, output_path=output)
    assert result == output
    assert output.exists()

    df_loaded = pd.read_parquet(output)
    assert len(df_loaded) == len(df)
    assert set(df_loaded.columns) == set(df.columns)


def test_save_missing_columns_raises(tmp_path):
    """ValueError dacă DataFrame-ul nu are coloanele obligatorii."""
    bad_df = pd.DataFrame({"date": [datetime(2024, 1, 1)]})
    with pytest.raises(ValueError, match="lipsește"):
        save_real_rate_differential_parquet(bad_df, output_path=tmp_path / "bad.parquet")


# ─── Integration test ─────────────────────────────────────────────

@pytest.mark.integration
def test_compute_real_rate_differential_integration():
    """Integration: compute real cu date reale, validare range-uri plauzibile."""
    df = compute_real_rate_differential(
        start=datetime(2015, 1, 1),
        end=datetime(2024, 12, 31),
    )
    assert len(df) > 2000
    assert df["real_rate_differential"].between(-4.0, 5.0).all()
    assert df["us_5y_real"].notna().all()
    assert df["eu_5y_real"].notna().all()
    assert df["real_rate_differential"].notna().all()
    assert df["date"].is_monotonic_increasing

    # Sanity check: 2022-2024 US was hawkish vs EU → mean RRD > 0
    recent = df[df["date"] >= "2022-01-01"]
    assert recent["real_rate_differential"].mean() > 0, (
        "Expected positive real_rate_differential in 2022-2024 (US hawkish vs EU)"
    )

    # TODO: enable EUR/USD correlation check when REQ-4 (fx.py) is implemented
