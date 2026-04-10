"""COT structural positioning pipeline — Layer 4A."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from cot_reports import cot_year


def fetch_cot_eur(
    start_year: int = 2020, end_year: int | None = None
) -> pd.DataFrame:
    """Download TFF Futures-only COT data and filter to EURO FX."""
    if end_year is None:
        end_year = datetime.now().year

    frames: list[pd.DataFrame] = []
    for year in range(start_year, end_year + 1):
        try:
            df_year = cot_year(
                year, cot_report_type="traders_in_financial_futures_fut"
            )
            frames.append(df_year)
            print(f"Fetched COT {year}: {len(df_year)} rows")
        except Exception as e:
            print(f"Skip {year}: {e}")

    if not frames:
        raise RuntimeError("No COT data fetched for any year")

    df = pd.concat(frames, ignore_index=True)
    df = df[df["Market_and_Exchange_Names"].str.contains("EURO FX", case=False)]
    print(f"Filtered to EURO FX: {len(df)} rows")
    return df


def compute_cot_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Compute net positioning, weekly delta, and 52-week percentile."""
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df["As_of_Date_In_Form_YYMMDD"], format="%y%m%d")
    out["lev_net"] = (
        df["Lev_Money_Positions_Long_All"].values
        - df["Lev_Money_Positions_Short_All"].values
    )
    out["am_net"] = (
        df["Asset_Mgr_Positions_Long_All"].values
        - df["Asset_Mgr_Positions_Short_All"].values
    )
    out = out.sort_values("date").reset_index(drop=True)
    out["lev_delta_wow"] = out["lev_net"].diff(1)
    out["lev_percentile_52w"] = out["lev_net"].rolling(52).rank(pct=True)
    return out


def save_cot_parquet(
    df: pd.DataFrame, path: str = "data/positioning/cot_eur.parquet"
) -> None:
    """Persist DataFrame to parquet, creating directories as needed."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False)
    print(f"Saved {len(df)} rows to {dest}")


def run_cot_pipeline(start_year: int = 2020) -> pd.DataFrame:
    """Entry point: fetch → compute → save → return."""
    print("=== COT Pipeline Start ===")
    raw = fetch_cot_eur(start_year=start_year)
    signals = compute_cot_signals(raw)
    save_cot_parquet(signals)
    print("=== COT Pipeline Done ===")
    return signals
