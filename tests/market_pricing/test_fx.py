"""Tests pentru fx.py — EUR/USD ingestion din FRED.

Folosește mock pentru FRED client — zero network calls în unit tests.
Testele cu @pytest.mark.integration necesită FRED_API_KEY în env.

Refs: PRD-200 CC-8, REQ-4
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from pydantic import ValidationError

from macro_context_reader.market_pricing.fx import (
    FRED_SERIES_EURUSD,
    _get_fred_client,
    _validate_rows,
    fetch_fx_eurusd,
    save_fx,
)
from macro_context_reader.market_pricing.schemas import FXRow


@pytest.fixture
def mock_fred_client():
    """Mock FRED client care returnează o serie EUR/USD sintetică plauzibilă."""
    client = MagicMock()

    dates = pd.date_range("2020-01-01", "2024-12-31", freq="B")
    # Valori plauzibile în range-ul istoric EUR/USD
    values = pd.Series(
        data=[1.05 + 0.0001 * i for i in range(len(dates))],
        index=dates,
    )

    def get_series_mock(series_id, **kwargs):
        if series_id == FRED_SERIES_EURUSD:
            return values
        return pd.Series(dtype=float)

    client.get_series.side_effect = get_series_mock
    return client


@pytest.fixture
def mock_fred_client_with_nans():
    """Mock FRED client care returnează serie cu NaN-uri (holidays)."""
    client = MagicMock()

    dates = pd.date_range("2020-01-01", "2020-01-31", freq="B")
    values = [1.10 if i % 5 != 0 else float("nan") for i in range(len(dates))]
    series = pd.Series(data=values, index=dates)

    client.get_series.return_value = series
    return client


@pytest.fixture
def empty_fred_client():
    """Mock FRED client care returnează serie goală."""
    client = MagicMock()
    client.get_series.return_value = pd.Series(dtype=float)
    return client


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


def test_schema_validation_valid_row():
    """FXRow acceptă un rând valid."""
    row = FXRow(date=datetime(2020, 1, 2), eurusd=1.1234)
    assert row.eurusd == 1.1234
    assert row.date == datetime(2020, 1, 2)


def test_schema_validation_rejects_nan():
    """FXRow._reject_nan respinge eurusd = NaN."""
    with pytest.raises(ValidationError):
        FXRow(date=datetime(2020, 1, 2), eurusd=float("nan"))


def test_validate_rows_catches_invalid():
    """_validate_rows ridică ValidationError pe DataFrame cu NaN."""
    bad_df = pd.DataFrame({
        "date": [datetime(2020, 1, 1)],
        "eurusd": [float("nan")],
    })
    with pytest.raises(ValidationError):
        _validate_rows(bad_df)


def test_validate_rows_passes_valid_df():
    """_validate_rows nu ridică excepție pe DataFrame curat."""
    good_df = pd.DataFrame({
        "date": [datetime(2020, 1, 1), datetime(2020, 1, 2)],
        "eurusd": [1.10, 1.11],
    })
    # Zero excepții
    _validate_rows(good_df)


# ---------------------------------------------------------------------------
# fetch_fx_eurusd tests
# ---------------------------------------------------------------------------


def test_fetch_returns_dataframe(mock_fred_client):
    """fetch_fx_eurusd returnează un DataFrame non-gol."""
    df = fetch_fx_eurusd(client=mock_fred_client)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_fetch_has_required_columns(mock_fred_client):
    """DataFrame-ul conține date și eurusd."""
    df = fetch_fx_eurusd(client=mock_fred_client)
    assert set(df.columns) == {"date", "eurusd"}


def test_fetch_date_is_datetime(mock_fred_client):
    """Coloana date e de tip datetime."""
    df = fetch_fx_eurusd(client=mock_fred_client)
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_fetch_sorted_ascending(mock_fred_client):
    """Datele sunt sortate ascending."""
    df = fetch_fx_eurusd(client=mock_fred_client)
    assert df["date"].is_monotonic_increasing


def test_fetch_drops_nan_rows(mock_fred_client_with_nans):
    """Rândurile cu NaN (holidays) sunt eliminate."""
    df = fetch_fx_eurusd(client=mock_fred_client_with_nans)
    assert df["eurusd"].notna().all()


def test_fetch_empty_series_raises(empty_fred_client):
    """ValueError când seria FRED e goală."""
    with pytest.raises(ValueError, match="empty"):
        fetch_fx_eurusd(client=empty_fred_client)


def test_fetch_fx_missing_api_key_raises(monkeypatch):
    """_get_fred_client ridică ValueError când FRED_API_KEY lipsește."""
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    # Neutralizează load_dotenv() — să nu recitească .env de pe disc
    with patch("macro_context_reader.market_pricing.fx.load_dotenv"):
        with pytest.raises(ValueError, match="FRED_API_KEY"):
            _get_fred_client()


# ---------------------------------------------------------------------------
# save_fx tests
# ---------------------------------------------------------------------------


def test_save_parquet_roundtrip(mock_fred_client, tmp_path):
    """save_fx scrie un Parquet care se reîncarcă identic."""
    df = fetch_fx_eurusd(client=mock_fred_client)
    output = tmp_path / "fx.parquet"
    result = save_fx(df, output_path=output)

    assert result == output
    assert output.exists()

    df_loaded = pd.read_parquet(output)
    assert len(df_loaded) == len(df)
    assert set(df_loaded.columns) == set(df.columns)
    pd.testing.assert_series_equal(
        df_loaded["eurusd"].reset_index(drop=True),
        df["eurusd"].reset_index(drop=True),
    )


def test_save_parquet_default_path(mock_fred_client, tmp_path, monkeypatch):
    """save_fx folosește DEFAULT_OUTPUT_PATH când output_path nu e specificat.

    DEFAULT_OUTPUT_PATH e path relativ ("data/market_pricing/fx.parquet").
    Folosim chdir pe tmp_path pentru a nu murdări repo-ul.
    """
    from macro_context_reader.market_pricing.fx import DEFAULT_OUTPUT_PATH

    monkeypatch.chdir(tmp_path)
    df = fetch_fx_eurusd(client=mock_fred_client)
    result = save_fx(df)

    expected = tmp_path / DEFAULT_OUTPUT_PATH
    assert result.resolve() == expected.resolve()
    assert expected.exists()
    # Verifică că directorul părinte a fost creat
    assert expected.parent.is_dir()


def test_save_missing_columns_raises(tmp_path):
    """ValueError dacă DataFrame-ul nu are coloanele obligatorii."""
    bad_df = pd.DataFrame({"date": [datetime(2020, 1, 1)]})
    with pytest.raises(ValueError, match="lipsește"):
        save_fx(bad_df, output_path=tmp_path / "bad.parquet")


# ---------------------------------------------------------------------------
# Integration test — necesită FRED_API_KEY
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_fetch_fx_eurusd_integration():
    """Integration: fetch real din FRED, range istoric plauzibil."""
    if not os.getenv("FRED_API_KEY"):
        pytest.skip("FRED_API_KEY not set")

    df = fetch_fx_eurusd(
        start=datetime(2015, 1, 1),
        end=datetime(2024, 12, 31),
    )
    assert len(df) > 2400
    assert df["eurusd"].notna().all()
    assert df["eurusd"].between(0.85, 1.40).all()
    assert df["date"].is_monotonic_increasing
