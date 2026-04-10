"""Tests pentru us_rates.py — orizont 5Y.

Folosește mock pentru FRED client — zero network calls în suite.

Refs: PRD-200 CC-2b, DEC-001
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from macro_context_reader.market_pricing.us_rates import (
    fetch_us_rates,
    save_us_rates,
    FRED_SERIES_NOMINAL,
    FRED_SERIES_REAL,
)


@pytest.fixture
def mock_fred_client():
    """Mock FRED client care returnează serii sintetice plauzibile."""
    client = MagicMock()

    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
    nominal_values = pd.Series(
        data=[2.0 + 0.01 * i for i in range(len(dates))],
        index=dates,
    )
    real_values = pd.Series(
        data=[0.5 + 0.005 * i for i in range(len(dates))],
        index=dates,
    )

    def get_series_mock(series_id, **kwargs):
        if series_id == FRED_SERIES_NOMINAL:
            return nominal_values
        elif series_id == FRED_SERIES_REAL:
            return real_values
        return pd.Series(dtype=float)

    client.get_series.side_effect = get_series_mock
    return client


@pytest.fixture
def empty_fred_client():
    """Mock FRED client care returnează serii goale."""
    client = MagicMock()
    client.get_series.return_value = pd.Series(dtype=float)
    return client


def test_fetch_returns_dataframe(mock_fred_client):
    """fetch_us_rates returnează un DataFrame."""
    df = fetch_us_rates(client=mock_fred_client)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_fetch_has_required_columns(mock_fred_client):
    """DataFrame-ul conține toate coloanele obligatorii."""
    df = fetch_us_rates(client=mock_fred_client)
    required = {"date", "us_5y_nominal", "us_5y_real", "us_breakeven_implied"}
    assert required.issubset(set(df.columns))


def test_real_yield_calculation(mock_fred_client):
    """us_breakeven_implied = us_5y_nominal - us_5y_real."""
    df = fetch_us_rates(client=mock_fred_client)
    computed = df["us_5y_nominal"] - df["us_5y_real"]
    pd.testing.assert_series_equal(
        df["us_breakeven_implied"],
        computed,
        check_names=False,
    )


def test_fetch_date_is_datetime(mock_fred_client):
    """Coloana date e de tip datetime."""
    df = fetch_us_rates(client=mock_fred_client)
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_fetch_sorted_ascending(mock_fred_client):
    """Datele sunt sortate ascending."""
    df = fetch_us_rates(client=mock_fred_client)
    assert df["date"].is_monotonic_increasing


def test_fetch_empty_nominal_raises(empty_fred_client):
    """ValueError când seria nominal e goală."""
    with pytest.raises(ValueError, match="empty"):
        fetch_us_rates(client=empty_fred_client)


def test_save_creates_parquet(mock_fred_client, tmp_path):
    """save_us_rates scrie un Parquet valid."""
    df = fetch_us_rates(client=mock_fred_client)
    output = tmp_path / "us_rates.parquet"
    result = save_us_rates(df, output_path=output)

    assert result == output
    assert output.exists()

    df_loaded = pd.read_parquet(output)
    assert len(df_loaded) == len(df)
    assert set(df_loaded.columns) == set(df.columns)


def test_save_missing_columns_raises(tmp_path):
    """ValueError dacă DataFrame-ul nu are coloanele obligatorii."""
    bad_df = pd.DataFrame({"date": [datetime(2020, 1, 1)]})
    with pytest.raises(ValueError, match="lipsește"):
        save_us_rates(bad_df, output_path=tmp_path / "bad.parquet")


def test_save_creates_parent_directory(mock_fred_client, tmp_path):
    """save_us_rates creează directorul părinte dacă nu există."""
    df = fetch_us_rates(client=mock_fred_client)
    output = tmp_path / "nested" / "dir" / "us_rates.parquet"
    save_us_rates(df, output_path=output)
    assert output.exists()
