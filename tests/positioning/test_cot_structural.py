"""Tests for COT structural positioning pipeline (Layer 4A)."""

from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from macro_context_reader.positioning.cot_structural import (
    compute_cot_signals,
    fetch_cot_eur,
    save_cot_parquet,
)


@pytest.fixture(scope="module")
def synthetic_tff() -> pd.DataFrame:
    """60-row synthetic TFF DataFrame with minimal required columns."""
    n = 60
    # Dates: weekly from 2023-01-03 onward, format YYMMDD
    dates = pd.date_range("2023-01-03", periods=n, freq="7D")
    yymmdd = dates.strftime("%y%m%d")

    return pd.DataFrame(
        {
            "Market_and_Exchange_Names": ["EURO FX - CHICAGO MERCANTILE EXCHANGE"] * n,
            "As_of_Date_In_Form_YYMMDD": yymmdd,
            "Lev_Money_Positions_Long_All": range(1000, 1000 + n),
            "Lev_Money_Positions_Short_All": range(500, 500 + n),
            "Asset_Mgr_Positions_Long_All": range(2000, 2000 + n),
            "Asset_Mgr_Positions_Short_All": range(800, 800 + n),
        }
    )


@pytest.fixture(scope="module")
def signals(synthetic_tff: pd.DataFrame) -> pd.DataFrame:
    return compute_cot_signals(synthetic_tff)


def test_compute_cot_signals_columns(signals: pd.DataFrame) -> None:
    expected = ["date", "lev_net", "am_net", "lev_delta_wow", "lev_percentile_52w"]
    assert signals.columns.tolist() == expected


def test_lev_net_calculation(synthetic_tff: pd.DataFrame) -> None:
    result = compute_cot_signals(synthetic_tff)
    # long - short: (1000+i) - (500+i) = 500 for every row
    assert (result["lev_net"] == 500).all()
    # am_net: (2000+i) - (800+i) = 1200 for every row
    assert (result["am_net"] == 1200).all()


def test_lev_percentile_range(signals: pd.DataFrame) -> None:
    valid = signals["lev_percentile_52w"].dropna()
    assert (valid >= 0.0).all()
    assert (valid <= 1.0).all()


def test_date_dtype(signals: pd.DataFrame) -> None:
    assert signals["date"].dtype == "datetime64[ns]"


def test_sorted_ascending(signals: pd.DataFrame) -> None:
    assert signals["date"].is_monotonic_increasing


def test_save_parquet() -> None:
    df = pd.DataFrame({"date": [pd.Timestamp("2024-01-01")], "lev_net": [100]})
    with patch.object(pd.DataFrame, "to_parquet") as mock_parquet, \
         patch("macro_context_reader.positioning.cot_structural.Path") as mock_path_cls:
        mock_path_inst = MagicMock()
        mock_path_cls.return_value = mock_path_inst
        save_cot_parquet(df, path="data/positioning/cot_eur.parquet")
        mock_path_cls.assert_called_once_with("data/positioning/cot_eur.parquet")
        mock_path_inst.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_parquet.assert_called_once_with(mock_path_inst, index=False)


def test_fetch_skips_on_error() -> None:
    good_data = pd.DataFrame(
        {
            "Market_and_Exchange_Names": ["EURO FX - CME"] * 5,
            "As_of_Date_In_Form_YYMMDD": ["230103", "230110", "230117", "230124", "230131"],
            "Lev_Money_Positions_Long_All": [100] * 5,
            "Lev_Money_Positions_Short_All": [50] * 5,
            "Asset_Mgr_Positions_Long_All": [200] * 5,
            "Asset_Mgr_Positions_Short_All": [80] * 5,
        }
    )

    def side_effect(year, cot_report_type):
        if year == 2023:
            raise RuntimeError("Simulated failure")
        return good_data

    with patch("macro_context_reader.positioning.cot_structural.cot_year", side_effect=side_effect):
        result = fetch_cot_eur(start_year=2023, end_year=2024)
        assert len(result) == 5
