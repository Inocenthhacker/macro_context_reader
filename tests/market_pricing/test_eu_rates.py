"""Tests pentru eu_rates.py.

Folosește mock pentru ECB client — zero network calls în suite.

Refs: PRD-200 CC-3, DEC-002
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from macro_context_reader.market_pricing.eu_rates import (
    ECB_SERIES_AAA,
    ECB_SERIES_ALL,
    fetch_eu_rates,
    save_eu_rates,
)


def _make_ecb_response(dates, values):
    """Construiește un răspuns ECB sintetic în format SDMX."""
    return pd.DataFrame({
        "TIME_PERIOD": [d.strftime("%Y-%m-%d") for d in dates],
        "OBS_VALUE": values,
        "FREQ": ["B"] * len(dates),
        "REF_AREA": ["U2"] * len(dates),
    })


@pytest.fixture
def mock_ecb_client():
    """Mock ECB client cu serii sintetice plauzibile."""
    client = MagicMock()

    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B").tolist()

    # AAA: yield-uri mai mici (Germany, Netherlands)
    aaa_values = [1.0 + 0.001 * i for i in range(len(dates))]

    # All: yield-uri puțin mai mari (include Italy, Spain)
    # Spread tipic 20-50bp = 0.2-0.5 percent
    all_values = [1.3 + 0.001 * i for i in range(len(dates))]

    def get_series_mock(series_key, start=None):
        if series_key == ECB_SERIES_AAA:
            return _make_ecb_response(dates, aaa_values)
        elif series_key == ECB_SERIES_ALL:
            return _make_ecb_response(dates, all_values)
        return pd.DataFrame()

    client.get_series.side_effect = get_series_mock
    return client


@pytest.fixture
def empty_ecb_client():
    """Mock ECB client care returnează serii goale."""
    client = MagicMock()
    client.get_series.return_value = pd.DataFrame()
    return client


def test_fetch_returns_dataframe(mock_ecb_client):
    """fetch_eu_rates returnează un DataFrame nevid."""
    df = fetch_eu_rates(client=mock_ecb_client)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_fetch_has_required_columns(mock_ecb_client):
    """DataFrame-ul conține toate cele 4 coloane obligatorii."""
    df = fetch_eu_rates(client=mock_ecb_client)
    required = {
        "date",
        "eu_5y_nominal_aaa",
        "eu_5y_nominal_all",
        "eu_credit_stress_5y",
    }
    assert required.issubset(set(df.columns))


def test_fetch_calls_both_series(mock_ecb_client):
    """Verifică că fetch face request pentru ambele serii."""
    fetch_eu_rates(client=mock_ecb_client)
    called_series = [call.args[0] for call in mock_ecb_client.get_series.call_args_list]
    assert ECB_SERIES_AAA in called_series
    assert ECB_SERIES_ALL in called_series


def test_credit_stress_calculation(mock_ecb_client):
    """eu_credit_stress_5y = eu_5y_nominal_all - eu_5y_nominal_aaa."""
    df = fetch_eu_rates(client=mock_ecb_client)
    computed = df["eu_5y_nominal_all"] - df["eu_5y_nominal_aaa"]
    pd.testing.assert_series_equal(
        df["eu_credit_stress_5y"],
        computed,
        check_names=False,
    )


def test_credit_stress_typically_positive(mock_ecb_client):
    """În condiții normale, all issuers > AAA → spread pozitiv."""
    df = fetch_eu_rates(client=mock_ecb_client)
    assert (df["eu_credit_stress_5y"] >= 0).all()


def test_fetch_date_is_datetime(mock_ecb_client):
    """Coloana date e de tip datetime."""
    df = fetch_eu_rates(client=mock_ecb_client)
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_fetch_sorted_ascending(mock_ecb_client):
    """Datele sunt sortate ascending."""
    df = fetch_eu_rates(client=mock_ecb_client)
    assert df["date"].is_monotonic_increasing


def test_fetch_empty_aaa_raises(empty_ecb_client):
    """ValueError când seria AAA e goală."""
    with pytest.raises(ValueError, match="empty"):
        fetch_eu_rates(client=empty_ecb_client)


def test_save_creates_parquet(mock_ecb_client, tmp_path):
    """save_eu_rates scrie un Parquet valid."""
    df = fetch_eu_rates(client=mock_ecb_client)
    output = tmp_path / "eu_rates.parquet"
    result = save_eu_rates(df, output_path=output)

    assert result == output
    assert output.exists()

    df_loaded = pd.read_parquet(output)
    assert len(df_loaded) == len(df)
    assert set(df_loaded.columns) == set(df.columns)


def test_save_missing_columns_raises(tmp_path):
    """ValueError dacă DataFrame-ul nu are coloanele obligatorii."""
    bad_df = pd.DataFrame({"date": [datetime(2020, 1, 1)]})
    with pytest.raises(ValueError, match="lipsește"):
        save_eu_rates(bad_df, output_path=tmp_path / "bad.parquet")


def test_save_creates_parent_directory(mock_ecb_client, tmp_path):
    """save_eu_rates creează directorul părinte dacă nu există."""
    df = fetch_eu_rates(client=mock_ecb_client)
    output = tmp_path / "nested" / "dir" / "eu_rates.parquet"
    save_eu_rates(df, output_path=output)
    assert output.exists()
