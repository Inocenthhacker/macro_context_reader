"""Myfxbook retail sentiment signal — Layer 4B (contrarian)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import requests


def fetch_retail_sentiment(
    url: str = "https://www.myfxbook.com/api/get-community-outlook.json",
    timeout: int = 10,
) -> dict[str, float]:
    """Fetch current EUR/USD retail long/short percentages from Myfxbook."""
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "MacroContextReader/0.1"})
    resp.raise_for_status()

    data = resp.json()
    try:
        symbols = data["symbols"]
    except KeyError:
        raise KeyError(f"Myfxbook response missing 'symbols' key — structure: {list(data.keys())}")

    for sym in symbols:
        if sym.get("name", "").upper() == "EURUSD":
            return {
                "date": datetime.today().strftime("%Y-%m-%d"),
                "retail_long_pct": float(sym["longPercentage"]) / 100,
                "retail_short_pct": float(sym["shortPercentage"]) / 100,
            }

    raise KeyError(f"EURUSD not found in Myfxbook symbols — available: {[s.get('name') for s in symbols]}")


def compute_retail_signal(df: pd.DataFrame) -> pd.DataFrame:
    """Convert retail long percentage into a contrarian signal in [-1, +1]."""
    out = df[["date", "retail_long_pct", "retail_short_pct"]].copy()
    # CONTRARIAN: retail majority is typically wrong-way
    out["retail_signal"] = -(out["retail_long_pct"] - 0.5) * 2
    return out


def save_retail_parquet(
    df: pd.DataFrame, path: str = "data/positioning/retail_signal.parquet"
) -> None:
    """Persist DataFrame to parquet, creating directories as needed."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False)
    print(f"Saved {len(df)} rows to {dest}")
