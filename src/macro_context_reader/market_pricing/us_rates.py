"""US Rates ingestion din FRED.

Descarcă US Treasury 2Y nominal yield și 5Y breakeven inflation din FRED API:
- DGS2: 2-Year Treasury Constant Maturity Rate (nominal)
- T5YIE: 5-Year Breakeven Inflation Rate (market-based inflation expectation)

Nota: FRED nu publică DFII2 (2Y TIPS real yield) — US Treasury nu emite 2Y TIPS.
Cel mai scurt orizont TIPS disponibil e 5Y (DFII5). Folosim T5YIE (5Y breakeven)
ca proxy standard pentru inflația așteptată US. Real yield implicit:
  us_2y_real = DGS2 - T5YIE (aproximare — maturity mismatch 2Y vs 5Y)

Aceasta este practica standard în literatura academică și rapoartele Fed/ECB.

Refs: PRD-200 CC-2, FRED https://fred.stlouisfed.org/
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred


DEFAULT_START_DATE = datetime(2015, 1, 1)
DEFAULT_OUTPUT_PATH = Path("data/market_pricing/us_rates.parquet")

FRED_SERIES_NOMINAL = "DGS2"
FRED_SERIES_BREAKEVEN = "T5YIE"


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
    """Descarcă US 2Y nominal și real yields din FRED.

    Args:
        start: Data de început (default 2015-01-01)
        end: Data de final (default = azi)
        client: Client FRED opțional (pentru testing cu mock)

    Returns:
        DataFrame cu coloanele: date, us_2y_nominal, us_2y_real, us_breakeven_implied
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
    breakeven = client.get_series(
        FRED_SERIES_BREAKEVEN,
        observation_start=start,
        observation_end=end,
    )

    if nominal.empty:
        raise ValueError(f"FRED series {FRED_SERIES_NOMINAL} returned empty")
    if breakeven.empty:
        raise ValueError(f"FRED series {FRED_SERIES_BREAKEVEN} returned empty")

    df = pd.DataFrame({
        "us_2y_nominal": nominal,
        "us_breakeven_implied": breakeven,
    })
    df.index.name = "date"
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"])

    # Real yield implicit = nominal - breakeven
    df["us_2y_real"] = df["us_2y_nominal"] - df["us_breakeven_implied"]

    # Drop rânduri unde ambele sunt NaN
    df = df.dropna(subset=["us_2y_nominal", "us_breakeven_implied"], how="all")
    df = df.sort_values("date").reset_index(drop=True)

    return df


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
    required_cols = {"date", "us_2y_nominal", "us_2y_real", "us_breakeven_implied"}
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
