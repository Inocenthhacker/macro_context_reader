"""Loader for Cleveland Fed Beige Book sentiment indices.

Source: Filippou, Garciga, Mitchell, Nguyen (2024), Cleveland Fed.
ICPSR DOI: 10.3886/E205881
Method: FinBERT on Beige Book sentences, tone = (n_pos - n_neg)/(n_pos + n_neg).
License: CC BY-NC 4.0
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from .schemas import CSV_COLUMN_TO_DISTRICT, DISTRICT_NAMES

DEFAULT_CSV_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "economic_sentiment"
    / "cleveland_fed_indices.csv"
)


def _district_col(district: str) -> str:
    return f"{district.replace(' ', '_').replace('.', '')}_score"


def load_cleveland_fed_indices(
    csv_path: Path | str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Load Cleveland Fed Beige Book sentiment indices."""
    path = Path(csv_path) if csv_path else DEFAULT_CSV_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Cleveland Fed indices CSV not found at {path}. "
            f"Download latest version from "
            f"https://www.openicpsr.org/openicpsr/project/205881/ "
            f"and place at {DEFAULT_CSV_PATH}"
        )

    df = pd.read_csv(path)

    expected_cols = {"date", "National", "Consensus"} | set(CSV_COLUMN_TO_DISTRICT.keys())
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing expected columns: {missing}")

    df["publication_date"] = pd.to_datetime(df["date"] + "-01")

    rename_map = {"National": "national_score", "Consensus": "consensus_score"}
    for csv_col, district in CSV_COLUMN_TO_DISTRICT.items():
        rename_map[csv_col] = _district_col(district)
    df = df.rename(columns=rename_map)

    df["national_consensus_divergence"] = df["national_score"] - df["consensus_score"]

    df = df.drop(columns=["date"])

    district_cols = [_district_col(d) for d in DISTRICT_NAMES]
    ordered_cols = (
        ["publication_date", "national_score", "consensus_score", "national_consensus_divergence"]
        + district_cols
    )
    df = df[ordered_cols]

    if start_date:
        df = df[df["publication_date"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["publication_date"] <= pd.to_datetime(end_date)]

    df = df.sort_values("publication_date").reset_index(drop=True)

    return df


def get_district_score(
    df: pd.DataFrame, district: str, publication_date: datetime
) -> float | None:
    """Get score for a specific district on a specific publication date."""
    col_name = _district_col(district)
    if col_name not in df.columns:
        raise KeyError(f"District {district} not in DataFrame columns")

    mask = df["publication_date"] == pd.to_datetime(publication_date)
    if not mask.any():
        return None
    val = df.loc[mask, col_name].iloc[0]
    if pd.isna(val):
        return None
    return float(val)
