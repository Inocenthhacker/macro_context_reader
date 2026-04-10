"""US Rates ingestion din FRED — orizont 5Y.

Descarcă US Treasury 5Y nominal și real yields din FRED API:
- DGS5: 5-Year Treasury Constant Maturity Rate (nominal)
- DFII5: 5-Year Treasury Inflation-Indexed Security (real yield, TIPS)

Breakeven inflation implicit = DGS5 - DFII5 (forward-looking inflation
expectation pe 5 ani, conform metodologiei standard Fed).

IMPORTANT: Acest modul folosește orizont 5Y, nu 2Y.
Motivul: US Treasury nu emite TIPS pe 2Y — DFII2 nu există în FRED.
Vezi decisions/DEC-001-switch-to-5y-horizon.md pentru context complet.

Fiecare rând e validat prin USRatesRow (Pydantic) înainte de return.

Refs: PRD-200 CC-2b/CC-4, DEC-001, FRED https://fred.stlouisfed.org/
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

from macro_context_reader.market_pricing.schemas import USRatesRow


DEFAULT_START_DATE = datetime(2015, 1, 1)
DEFAULT_OUTPUT_PATH = Path("data/market_pricing/us_rates.parquet")

FRED_SERIES_NOMINAL = "DGS5"
FRED_SERIES_REAL = "DFII5"


def _get_fred_client() -> Fred:
    """Creează client FRED folosind API key din .env.

    Raises:
        ValueError: dacă FRED_API_KEY lipsește sau e gol
    """
    load_dotenv()
    api_key = os.getenv("FRED_API_KEY")
    if not api_key or api_key.startswith("REPLACE_") or api_key == "your_fred_api_key_here":
        raise ValueError(
            "FRED_API_KEY nu e configurat în .env. "
            "Vezi .env.example pentru template."
        )
    return Fred(api_key=api_key)


def fetch_us_rates(
    start: datetime = DEFAULT_START_DATE,
    end: Optional[datetime] = None,
    client: Optional[Fred] = None,
) -> pd.DataFrame:
    """Descarcă US 5Y nominal și real yields din FRED.

    Args:
        start: Data de început (default 2015-01-01)
        end: Data de final (default = azi)
        client: Client FRED opțional (pentru testing cu mock)

    Returns:
        DataFrame cu coloanele: date, us_5y_nominal, us_5y_real, us_5y_breakeven
        Frecvență zilnică (business days), sortat ascending pe dată.

    Raises:
        ValueError: dacă seriile lipsesc sau sunt goale
    """
    if client is None:
        client = _get_fred_client()

    nominal = client.get_series(
        FRED_SERIES_NOMINAL,
        observation_start=start,
        observation_end=end,
    )
    real = client.get_series(
        FRED_SERIES_REAL,
        observation_start=start,
        observation_end=end,
    )

    if nominal.empty:
        raise ValueError(f"FRED series {FRED_SERIES_NOMINAL} returned empty")
    if real.empty:
        raise ValueError(f"FRED series {FRED_SERIES_REAL} returned empty")

    df = pd.DataFrame({
        "us_5y_nominal": nominal,
        "us_5y_real": real,
    })
    df.index.name = "date"
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"])

    # Breakeven inflation implicit = nominal - real
    df["us_5y_breakeven"] = df["us_5y_nominal"] - df["us_5y_real"]

    # Drop rânduri unde ambele sunt NaN
    df = df.dropna(subset=["us_5y_nominal", "us_5y_real"], how="all")
    df = df.sort_values("date").reset_index(drop=True)

    # Pydantic row-by-row validation
    _validate_rows(df)

    return df


def _validate_rows(df: pd.DataFrame) -> None:
    """Validează fiecare rând prin USRatesRow Pydantic model.

    Raises:
        pydantic.ValidationError: dacă orice rând e invalid
    """
    for row in df.to_dict(orient="records"):
        USRatesRow.model_validate(row)


def save_us_rates(
    df: pd.DataFrame,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Salvează DataFrame-ul în format Parquet.

    Args:
        df: DataFrame cu coloanele așteptate
        output_path: Calea către fișierul .parquet

    Returns:
        Path-ul fișierului scris
    """
    required_cols = {"date", "us_5y_nominal", "us_5y_real", "us_5y_breakeven"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame-ul lipsește coloanele: {missing}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    return output_path


def run_us_rates_pipeline(
    start: datetime = DEFAULT_START_DATE,
    end: Optional[datetime] = None,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Pipeline complet: fetch + save.

    Returns:
        Path-ul fișierului Parquet scris
    """
    df = fetch_us_rates(start=start, end=end)
    return save_us_rates(df, output_path=output_path)
