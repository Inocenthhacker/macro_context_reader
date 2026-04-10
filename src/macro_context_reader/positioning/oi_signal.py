"""CME EUR Open Interest signal pipeline — Layer 4B."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup


def fetch_eur_oi(
    date: str | None = None,
    url: str = "https://www.cmegroup.com/market-data/volume-open-interest/fx-volume.html",
    timeout: int = 10,
) -> dict[str, int]:
    """Fetch daily EUR/USD futures (6E) Open Interest from CME."""
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")

    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "MacroContextReader/0.1"})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("table tr")
    for row in rows:
        cells = row.find_all("td")
        if any("EURO FX" in (c.get_text() or "") for c in cells):
            # OI is typically the last numeric column
            for cell in reversed(cells):
                text = cell.get_text(strip=True).replace(",", "")
                if text.isdigit():
                    return {"date": date, "open_interest": int(text)}

    raise ValueError(
        f"Could not extract EURO FX Open Interest from {url} — page structure may have changed"
    )


def compute_oi_signal(df_oi: pd.DataFrame, df_price: pd.DataFrame) -> pd.DataFrame:
    """Compute OI confirmation signal from OI and price series.

    oi_signal: +1 = trend confirmed, -1 = divergence (squeeze/distribution), 0 = flat.
    """
    merged = pd.merge(df_oi, df_price, on="date", how="inner").sort_values("date").reset_index(drop=True)
    merged["oi_change"] = merged["open_interest"].diff(1)
    merged["price_change"] = merged["close"].diff(1)
    merged["oi_signal"] = (np.sign(merged["price_change"]) * np.sign(merged["oi_change"])).fillna(0).astype("int8")
    return merged[["date", "open_interest", "oi_change", "price_change", "oi_signal"]]


def save_oi_parquet(
    df: pd.DataFrame, path: str = "data/positioning/oi_signal.parquet"
) -> None:
    """Persist DataFrame to parquet, creating directories as needed."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False)
    print(f"Saved {len(df)} rows to {dest}")
