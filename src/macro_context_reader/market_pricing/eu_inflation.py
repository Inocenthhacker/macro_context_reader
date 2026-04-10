"""EU Inflation Expectations ingestion din ECB SPF — orizont 5Y.

Descarcă longer-term HICP inflation forecast din ECB Survey of Professional
Forecasters (SPF). Aceasta este media (average) a estimărilor punctuale
(point forecasts) ale profesioniștilor pentru inflația HICP pe termen lung.

Serie: SPF.Q.U2.HICP.POINT.LT.Q.AVG
Frecvență: quarterly (Q1-Q4)
Orizont: 5 calendar years ahead în Q3/Q4, 4 calendar years ahead în Q1/Q2.

IMPORTANT: Acest modul păstrează datele la frecvența nativă quarterly.
Forward-fill la daily e responsabilitatea CC-6 (real_rate_diff composite).

ILS (Inflation-Linked Swap) rates NU sunt disponibile pe ECB free Data Portal.
Vezi DEC-004 pentru raționamentul complet al alegerii SPF.

Refs: PRD-200 CC-5, DEC-004
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol

import pandas as pd

from macro_context_reader.market_pricing.schemas import EUInflationRow


DEFAULT_START_DATE = datetime(2015, 1, 1)
DEFAULT_OUTPUT_PATH = Path("data/market_pricing/eu_inflation_5y.parquet")

ECB_SPF_SERIES = "SPF.Q.U2.HICP.POINT.LT.Q.AVG"


class ECBClientProtocol(Protocol):
    """Protocol minimal pentru client ECB (pentru mocking în teste)."""

    def get_series(self, series_key: str, start: Optional[str] = None) -> pd.DataFrame:
        ...


def _get_ecb_client():
    """Returnează clientul ecbdata real."""
    from ecbdata import ecbdata
    return ecbdata


def fetch_eu_inflation_5y(
    start: datetime = DEFAULT_START_DATE,
    end: Optional[datetime] = None,
    client: Optional[ECBClientProtocol] = None,
) -> pd.DataFrame:
    """Descarcă EU 5Y inflation expectations din ECB SPF.

    Args:
        start: Data de început (default 2015-01-01)
        end: Data de final (default = present)
        client: Client ECB opțional pentru testing cu mock

    Returns:
        DataFrame cu coloanele:
        - date (datetime)
        - eu_inflation_expectations_5y (float, percent)

        Frecvență quarterly, sortat ascending pe dată.

    Raises:
        ValueError: dacă seria e goală
    """
    if client is None:
        client = _get_ecb_client()

    start_str = start.strftime("%Y-%m-%d") if start else None

    raw_df = client.get_series(ECB_SPF_SERIES, start=start_str)
    if raw_df is None or len(raw_df) == 0:
        raise ValueError(f"ECB series {ECB_SPF_SERIES} returned empty")

    df = _normalize_spf_response(raw_df)

    # Filter by end date if specified
    if end is not None:
        df = df[df["date"] <= end]

    df = df.sort_values("date").reset_index(drop=True)

    _validate_rows(df)

    return df


def _normalize_spf_response(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizează răspunsul ECB SPF la format (date, value).

    SPF returnează TIME_PERIOD în format "YYYY-QN" (ex: "2024-Q3").
    Convertim la datetime folosind sfârșitul trimestrului.
    """
    if "TIME_PERIOD" not in df.columns or "OBS_VALUE" not in df.columns:
        raise ValueError(
            f"Unexpected ECB SPF response format. Columns: {list(df.columns)}"
        )

    result = pd.DataFrame({
        "date": pd.PeriodIndex(df["TIME_PERIOD"], freq="Q").to_timestamp(how="end"),
        "eu_inflation_expectations_5y": pd.to_numeric(
            df["OBS_VALUE"], errors="coerce"
        ),
    })

    result = result.dropna(subset=["eu_inflation_expectations_5y"])
    return result


def _validate_rows(df: pd.DataFrame) -> None:
    """Validează fiecare rând prin EUInflationRow Pydantic model.

    Raises:
        pydantic.ValidationError: dacă orice rând e invalid
    """
    for row in df.to_dict(orient="records"):
        EUInflationRow.model_validate(row)


def save_eu_inflation_parquet(
    df: pd.DataFrame,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Salvează DataFrame-ul în format Parquet.

    Args:
        df: DataFrame cu coloanele așteptate
        output_path: Calea către fișierul .parquet

    Returns:
        Path-ul fișierului scris

    Raises:
        ValueError: dacă lipsesc coloane obligatorii
    """
    required_cols = {"date", "eu_inflation_expectations_5y"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame-ul lipsește coloanele: {missing}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    return output_path


def run_eu_inflation_pipeline(
    start: datetime = DEFAULT_START_DATE,
    end: Optional[datetime] = None,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Pipeline complet: fetch + validate + save.

    Returns:
        Path-ul fișierului Parquet scris
    """
    df = fetch_eu_inflation_5y(start=start, end=end)
    return save_eu_inflation_parquet(df, output_path=output_path)
