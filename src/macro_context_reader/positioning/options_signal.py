"""CME EUR options put/call skew signal — Layer 4B."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


def fetch_eur_putcall_ratio(
    url: str = "https://www.cmegroup.com/market-data/volume-open-interest/options-put-call-ratios.html",
    timeout: int = 10,
) -> dict[str, float]:
    """Fetch current EUR/USD (6E) put/call ratio from CME."""
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "MacroContextReader/0.1"})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("table tr")
    for row in rows:
        cells = row.find_all("td")
        if any("EURO" in (c.get_text() or "").upper() for c in cells):
            for cell in reversed(cells):
                text = cell.get_text(strip=True).replace(",", "")
                try:
                    ratio = float(text)
                    if 0 < ratio < 50:  # sanity bound for a ratio
                        return {"date": datetime.today().strftime("%Y-%m-%d"), "put_call_ratio": ratio}
                except ValueError:
                    continue

    raise ValueError(
        f"Could not extract EUR put/call ratio from {url} — page structure may have changed"
    )


def compute_options_signal(df: pd.DataFrame, window: int = 52) -> pd.DataFrame:
    """Normalise put/call ratio into a [-1, +1] signal.

    High put/call → market hedging bearish EUR → negative signal for EUR.
    """
    out = df[["date", "put_call_ratio"]].copy().sort_values("date").reset_index(drop=True)
    out["pc_percentile"] = out["put_call_ratio"].rolling(window).rank(pct=True)
    out["options_signal"] = -(out["pc_percentile"] - 0.5) * 2
    return out


def save_options_parquet(
    df: pd.DataFrame, path: str = "data/positioning/options_signal.parquet"
) -> None:
    """Persist DataFrame to parquet, creating directories as needed."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False)
    print(f"Saved {len(df)} rows to {dest}")
