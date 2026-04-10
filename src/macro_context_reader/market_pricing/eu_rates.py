"""EUR Rates ingestion din ECB Data Portal — orizont 5Y.

Descarcă două variante ale curbei de randament EUR 5Y:
- AAA only (G_N_C): folosit ca input principal în real_rate_diff
- All issuers (G_N_A): semnal paralel pentru cross-validation

Calculează automat credit stress spread = All - AAA.

Sursele sunt zilnice (TARGET business days), Svensson model continuous
compounding, din 2004-09-06 până în prezent. ECB Yield Curve exclude
explicit obligațiunile indexate la inflație — curba e strict nominal.

Vezi DEC-002 pentru raționamentul complet al designului dual.

Refs: PRD-200 CC-3, DEC-002
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol

import pandas as pd


DEFAULT_START_DATE = datetime(2015, 1, 1)
DEFAULT_OUTPUT_PATH = Path("data/market_pricing/eu_rates.parquet")

# G_N_A = AAA-only (triple A rated sovereigns: Germany, Netherlands, Luxembourg)
# G_N_C = All issuers (all euro area sovereigns, all ratings)
# Verified via ECB TITLE_COMPL metadata field on 2026-04-10.
ECB_SERIES_AAA = "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y"
ECB_SERIES_ALL = "YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_5Y"


class ECBClientProtocol(Protocol):
    """Protocol minimal pentru client ECB (pentru mocking în teste)."""

    def get_series(self, series_key: str, start: Optional[str] = None) -> pd.DataFrame:
        ...


def _get_ecb_client():
    """Returnează clientul ecbdata real.

    Separat ca funcție pentru a permite mocking în teste fără importul
    ecbdata real.
    """
    from ecbdata import ecbdata
    return ecbdata


def fetch_eu_rates(
    start: datetime = DEFAULT_START_DATE,
    end: Optional[datetime] = None,
    client: Optional[ECBClientProtocol] = None,
) -> pd.DataFrame:
    """Descarcă EUR 5Y nominal yields (AAA + All) și calculează spread-ul.

    Args:
        start: Data de început (default 2015-01-01)
        end: Data de final (default = present)
        client: Client ECB opțional pentru testing cu mock

    Returns:
        DataFrame cu coloanele:
        - date (datetime)
        - eu_5y_nominal_aaa (float, percent)
        - eu_5y_nominal_all (float, percent)
        - eu_credit_stress_5y (float, percent, = all - aaa)

        Frecvență zilnică (business days), sortat ascending pe dată.

    Raises:
        ValueError: dacă seriile sunt goale sau lipsesc
    """
    if client is None:
        client = _get_ecb_client()

    start_str = start.strftime("%Y-%m-%d") if start else None

    # Fetch AAA series
    aaa_df = client.get_series(ECB_SERIES_AAA, start=start_str)
    if aaa_df is None or len(aaa_df) == 0:
        raise ValueError(f"ECB series {ECB_SERIES_AAA} returned empty")

    # Fetch All issuers series
    all_df = client.get_series(ECB_SERIES_ALL, start=start_str)
    if all_df is None or len(all_df) == 0:
        raise ValueError(f"ECB series {ECB_SERIES_ALL} returned empty")

    # Normalize to (date, value) pairs
    aaa_normalized = _normalize_ecb_response(aaa_df, "eu_5y_nominal_aaa")
    all_normalized = _normalize_ecb_response(all_df, "eu_5y_nominal_all")

    # Merge on date
    merged = pd.merge(
        aaa_normalized,
        all_normalized,
        on="date",
        how="inner",
    )

    # Compute credit stress spread
    merged["eu_credit_stress_5y"] = (
        merged["eu_5y_nominal_all"] - merged["eu_5y_nominal_aaa"]
    )

    # Filter by end date if specified
    if end is not None:
        merged = merged[merged["date"] <= end]

    merged = merged.sort_values("date").reset_index(drop=True)

    return merged


def _normalize_ecb_response(df: pd.DataFrame, value_col_name: str) -> pd.DataFrame:
    """Normalizează răspunsul ECB la format (date, value).

    ecbdata returnează un DataFrame cu multe coloane (TIME_PERIOD, OBS_VALUE,
    plus 30+ atribute SDMX). Extragem doar data și valoarea.
    """
    if "TIME_PERIOD" in df.columns and "OBS_VALUE" in df.columns:
        result = pd.DataFrame({
            "date": pd.to_datetime(df["TIME_PERIOD"]),
            value_col_name: pd.to_numeric(df["OBS_VALUE"], errors="coerce"),
        })
    else:
        raise ValueError(
            f"Unexpected ECB response format. Columns: {list(df.columns)}"
        )

    result = result.dropna(subset=[value_col_name])
    return result


def save_eu_rates(
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
    required_cols = {
        "date",
        "eu_5y_nominal_aaa",
        "eu_5y_nominal_all",
        "eu_credit_stress_5y",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame-ul lipsește coloanele: {missing}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    return output_path


def run_eu_rates_pipeline(
    start: datetime = DEFAULT_START_DATE,
    end: Optional[datetime] = None,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Pipeline complet: fetch + compute spread + save.

    Returns:
        Path-ul fișierului Parquet scris
    """
    df = fetch_eu_rates(start=start, end=end)
    return save_eu_rates(df, output_path=output_path)
