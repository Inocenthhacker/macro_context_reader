"""Tests pentru eu_inflation.py.

Folosește mock pentru ECB client — zero network calls în unit tests.

Refs: PRD-200 CC-5, DEC-004
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pydantic import ValidationError

from macro_context_reader.market_pricing.eu_inflation import (
    ECB_SPF_SERIES,
    fetch_eu_inflation_5y,
    save_eu_inflation_parquet,
    _validate_rows,
)
from macro_context_reader.market_pricing.schemas import EUInflationRow


def _make_spf_response(periods, values):
    """Construiește un răspuns ECB SPF sintetic în format SDMX."""
    return pd.DataFrame({
        "TIME_PERIOD": periods,
        "OBS_VALUE": values,
        "FREQ": ["Q"] * len(periods),
        "REF_AREA": ["U2"] * len(periods),
    })


@pytest.fixture
def mock_ecb_client():
    """Mock ECB client cu serii SPF sintetice plauzibile."""
    client = MagicMock()

    # 40 trimestre: 2015-Q1 → 2024-Q4
    periods = [f"{y}-Q{q}" for y in range(2015, 2025) for q in range(1, 5)]
    # Valori în jurul targetului ECB ~2%, cu ușoară variație
    values = [1.85 + 0.005 * i for i in range(len(periods))]

    def get_series_mock(series_key, start=None):
        if series_key == ECB_SPF_SERIES:
            return _make_spf_response(periods, values)
        return pd.DataFrame()

    client.get_series.side_effect = get_series_mock
    return client


@pytest.fixture
def empty_ecb_client():
    """Mock ECB client care returnează serie goală."""
    client = MagicMock()
    client.get_series.return_value = pd.DataFrame()
    return client


def test_schema_validation_valid_row():
    """EUInflationRow acceptă un rând valid."""
    row = EUInflationRow(
        date=datetime(2024, 3, 31),
        eu_inflation_expectations_5y=2.01,
    )
    assert row.eu_inflation_expectations_5y == 2.01


def test_schema_validation_rejects_nan():
    """EUInflationRow rejectează NaN prin _reject_nan validator."""
    with pytest.raises(ValidationError):
        EUInflationRow(
            date=datetime(2024, 3, 31),
            eu_inflation_expectations_5y=float("nan"),
        )


def test_validate_rows_catches_invalid():
    """_validate_rows raise ValidationError pe DataFrame cu NaN."""
    bad_df = pd.DataFrame({
        "date": [datetime(2024, 3, 31)],
        "eu_inflation_expectations_5y": [float("nan")],
    })
    with pytest.raises(ValidationError):
        _validate_rows(bad_df)


def test_validate_rows_passes_valid_df():
    """_validate_rows trece fără excepție pe DataFrame curat."""
    good_df = pd.DataFrame({
        "date": [datetime(2024, 3, 31), datetime(2024, 6, 30)],
        "eu_inflation_expectations_5y": [2.01, 1.98],
    })
    _validate_rows(good_df)  # nu trebuie să ridice excepție


def test_fetch_returns_dataframe_structure(mock_ecb_client):
    """fetch_eu_inflation_5y returnează DataFrame cu coloanele corecte."""
    df = fetch_eu_inflation_5y(client=mock_ecb_client)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    required = {"date", "eu_inflation_expectations_5y"}
    assert required.issubset(set(df.columns))
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert df["date"].is_monotonic_increasing


def test_fetch_empty_raises(empty_ecb_client):
    """ValueError când seria SPF e goală."""
    with pytest.raises(ValueError, match="empty"):
        fetch_eu_inflation_5y(client=empty_ecb_client)


def test_save_parquet_roundtrip(mock_ecb_client, tmp_path):
    """save + read roundtrip păstrează datele."""
    df = fetch_eu_inflation_5y(client=mock_ecb_client)
    output = tmp_path / "eu_inflation.parquet"
    result = save_eu_inflation_parquet(df, output_path=output)

    assert result == output
    assert output.exists()

    df_loaded = pd.read_parquet(output)
    assert len(df_loaded) == len(df)
    assert set(df_loaded.columns) == set(df.columns)


def test_save_parquet_creates_parent_directory(mock_ecb_client, tmp_path):
    """save creează directorul părinte dacă nu există."""
    df = fetch_eu_inflation_5y(client=mock_ecb_client)
    output = tmp_path / "nested" / "dir" / "inflation.parquet"
    save_eu_inflation_parquet(df, output_path=output)
    assert output.exists()


def test_save_missing_columns_raises(tmp_path):
    """ValueError dacă DataFrame-ul nu are coloanele obligatorii."""
    bad_df = pd.DataFrame({"date": [datetime(2024, 3, 31)]})
    with pytest.raises(ValueError, match="lipsește"):
        save_eu_inflation_parquet(bad_df, output_path=tmp_path / "bad.parquet")


@pytest.mark.integration
def test_fetch_real_ecb_spf_data():
    """Integration: fetch real din ECB SPF, validare range-uri plauzibile."""
    df = fetch_eu_inflation_5y(
        start=datetime(2015, 1, 1),
        end=datetime(2024, 12, 31),
    )
    assert len(df) >= 35
    assert df["eu_inflation_expectations_5y"].notna().all()
    assert df["eu_inflation_expectations_5y"].between(0.5, 4.0).all()
    assert df["date"].is_monotonic_increasing
