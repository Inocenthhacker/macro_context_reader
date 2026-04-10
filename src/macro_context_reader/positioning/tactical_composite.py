"""Tactical composite score — Layer 4B aggregation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_WEIGHTS = {"oi": 0.4, "options": 0.35, "retail": 0.25}

SIGNAL_COLS = {
    "oi": "oi_signal",
    "options": "options_signal",
    "retail": "retail_signal",
}


def load_signals() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the three tactical signal parquets."""
    paths = {
        "oi": "data/positioning/oi_signal.parquet",
        "options": "data/positioning/options_signal.parquet",
        "retail": "data/positioning/retail_signal.parquet",
    }
    frames = []
    for name, p in paths.items():
        if not Path(p).exists():
            raise FileNotFoundError(f"Missing {name} signal file: {p}")
        frames.append(pd.read_parquet(p))
    return frames[0], frames[1], frames[2]


def compute_tactical_score(
    df_oi: pd.DataFrame,
    df_options: pd.DataFrame,
    df_retail: pd.DataFrame,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
) -> pd.DataFrame:
    """Aggregate OI, options, and retail signals with adaptive weighting.

    When a source is NaN for a row, redistribute its weight proportionally
    among the available sources.
    """
    oi = df_oi[["date", "oi_signal"]].copy()
    options = df_options[["date", "options_signal"]].copy()
    retail = df_retail[["date", "retail_signal"]].copy()

    merged = oi.merge(options, on="date", how="outer").merge(retail, on="date", how="outer")
    merged = merged.sort_values("date").reset_index(drop=True)

    signals = merged[["oi_signal", "options_signal", "retail_signal"]]
    available = signals.notna()

    merged["sources_available"] = available.sum(axis=1).astype(int)

    w = np.array([weights["oi"], weights["options"], weights["retail"]])
    sig_values = signals.values  # shape (n, 3)
    mask = available.values      # shape (n, 3)

    scores = np.full(len(merged), np.nan)
    for i in range(len(merged)):
        row_mask = mask[i]
        if not row_mask.any():
            continue
        row_w = w * row_mask
        row_w = np.round(row_w / row_w.sum(), 6)
        vals = np.where(row_mask, sig_values[i], 0.0)
        scores[i] = np.dot(row_w, vals)

    merged["tactical_score"] = scores

    return merged[["date", "oi_signal", "options_signal", "retail_signal", "tactical_score", "sources_available"]]


def run_tactical_pipeline() -> pd.DataFrame:
    """Entry point: load → compute → save → return."""
    df_oi, df_options, df_retail = load_signals()
    result = compute_tactical_score(df_oi, df_options, df_retail)
    dest = Path("data/positioning/tactical_composite.parquet")
    dest.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(dest, index=False)
    print(f"Saved {len(result)} rows to {dest}")
    return result
