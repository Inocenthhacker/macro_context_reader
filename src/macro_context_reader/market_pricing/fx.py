"""FX ingestion din FRED — EUR/USD spot (DEXUSEU).

Descarcă cursul spot EUR/USD din FRED API:
- DEXUSEU: U.S. Dollars to Euro Spot Exchange Rate, noon buying rates
  in NY, business days.

Seria e folosită de Layer 2 (real_rate_differential visualization) și
de orice analiză Layer 3/4 care compară semnale macro cu mișcarea
EUR/USD. Frecvență zilnică (business days), valori lipsă pentru
holidays sunt filtrate la ingestie.

Fiecare rând e validat prin FXRow (Pydantic) înainte de return.

Refs: PRD-200 CC-8, REQ-4, FRED https://fred.stlouisfed.org/series/DEXUSEU
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

from macro_context_reader.market_pricing.schemas import FXRow


DEFAULT_START_DATE = datetime(2015, 1, 1)
DEFAULT_OUTPUT_PATH = Path("data/market_pricing/fx.parquet")

FRED_SERIES_EURUSD = "DEXUSEU"


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


def fetch_fx_eurusd(
    start: datetime = DEFAULT_START_DATE,
    end: Optional[datetime] = None,
    client: Optional[Fred] = None,
) -> pd.DataFrame:
    """Descarcă EUR/USD spot rate din FRED (DEXUSEU).

    Args:
        start: Data de început (default 2015-01-01)
        end: Data de final (default = azi)
        client: Client FRED opțional (pentru testing cu mock)

    Returns:
        DataFrame cu coloanele: date, eurusd
        Frecvență zilnică (business days), sortat ascending pe dată.
        Rândurile cu NaN (holidays, missing) sunt eliminate.

    Raises:
        ValueError: dacă seria e goală
    """
    if client is None:
        client = _get_fred_client()

    series = client.get_series(
        FRED_SERIES_EURUSD,
        observation_start=start,
        observation_end=end,
    )

    if series.empty:
        raise ValueError(f"FRED series {FRED_SERIES_EURUSD} returned empty")

    df = pd.DataFrame({"eurusd": series})
    df.index.name = "date"
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"])

    # FRED returnează NaN pentru holidays / missing observations
    df = df.dropna(subset=["eurusd"])
    df = df.sort_values("date").reset_index(drop=True)

    # Pydantic row-by-row validation
    _validate_rows(df)

    return df


def _validate_rows(df: pd.DataFrame) -> None:
    """Validează fiecare rând prin FXRow Pydantic model.

    Raises:
        pydantic.ValidationError: dacă orice rând e invalid
    """
    for row in df.to_dict(orient="records"):
        FXRow.model_validate(row)


def save_fx(
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
    required_cols = {"date", "eurusd"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame-ul lipsește coloanele: {missing}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False, compression="snappy")
    return output_path


def run_fx_pipeline(
    start: datetime = DEFAULT_START_DATE,
    end: Optional[datetime] = None,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Pipeline complet: fetch + save.

    Returns:
        Path-ul fișierului Parquet scris
    """
    df = fetch_fx_eurusd(start=start, end=end)
    return save_fx(df, output_path=output_path)


# Repo-root absolute path (fx.py is 4 levels deep under repo root):
# fx.py -> market_pricing -> macro_context_reader -> src -> repo_root
FX_PARQUET = Path(__file__).resolve().parents[3] / "data" / "market_pricing" / "fx.parquet"
FX_HISTORY_DEFAULT_START = "2015-04-01"  # aligned with real_rate_diff coverage


def load_fx_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    rebuild: bool = False,
) -> pd.DataFrame:
    """Load EUR/USD historical data from Parquet (fast) or rebuild from FRED.

    Persisted at data/market_pricing/fx.parquet. If rebuild=True or file missing,
    fetches fresh from FRED (DEXUSEU) and overwrites Parquet.

    Parameters
    ----------
    start_date : str, optional
        ISO date "YYYY-MM-DD" filter. Default uses persisted full range.
    end_date : str, optional
        ISO date "YYYY-MM-DD" filter. Default uses persisted full range.
    rebuild : bool
        If True, refetch from FRED and overwrite Parquet. Default False.

    Returns
    -------
    pd.DataFrame
        DatetimeIndex (name='date'), single column 'eurusd' with daily close prices.
        Forward-filled for non-trading days, with leading NaN dropped.
    """
    if rebuild or not FX_PARQUET.exists():
        raw = fetch_fx_eurusd()
        df = raw.set_index(pd.DatetimeIndex(raw["date"], name="date"))[["eurusd"]]
        df = df.ffill().dropna()
        df = df[df.index >= pd.Timestamp(FX_HISTORY_DEFAULT_START)]
        FX_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(FX_PARQUET, index=True)

    df = pd.read_parquet(FX_PARQUET)

    if start_date:
        df = df[df.index >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df.index <= pd.Timestamp(end_date)]

    return df
