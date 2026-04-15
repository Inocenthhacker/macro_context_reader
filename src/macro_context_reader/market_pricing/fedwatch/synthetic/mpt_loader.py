"""Atlanta Fed Market Probability Tracker (MPT) loader.

Downloads MPT historical Excel file, reshapes to fedwatch-compatible schema.
Coverage: 2023-03-29 -> present (Atlanta Fed publishes daily).

References
----------
- Atlanta Fed CenFIS Market Probability Tracker:
  https://www.atlantafed.org/cenfis/market-probability-tracker
- Methodology: 3-month SOFR options, daily probability distributions
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


MPT_URL = "https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/cenfis/market-probability-tracker/mpt_histdata.xlsx"

# builder.py -> synthetic -> fedwatch -> market_pricing -> macro_context_reader -> src -> repo_root
CACHE_DIR = (
    Path(__file__).resolve().parents[5]
    / "data"
    / "market_pricing"
    / "fedwatch_synthetic_cache"
)
RAW_XLSX_PATH = CACHE_DIR / "mpt_histdata.xlsx"

OUTPUT_PARQUET = (
    Path(__file__).resolve().parents[5]
    / "data"
    / "market_pricing"
    / "fedwatch_mpt.parquet"
)

PROB_BUCKET_RE = re.compile(r"Prob:\s*(-?\d+)bps\s*-\s*(-?\d+)bps")


def download_mpt_xlsx(force: bool = False) -> Path:
    """Download MPT Excel file to cache. Skip if exists and not force."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if RAW_XLSX_PATH.exists() and not force:
        logger.info(f"Using cached MPT file: {RAW_XLSX_PATH}")
        return RAW_XLSX_PATH

    logger.info(f"Downloading MPT from {MPT_URL}")
    r = requests.get(
        MPT_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; macro-context-reader/1.0)"},
        timeout=120,
    )
    r.raise_for_status()

    RAW_XLSX_PATH.write_bytes(r.content)
    logger.info(f"Saved {len(r.content)} bytes to {RAW_XLSX_PATH}")
    return RAW_XLSX_PATH


def parse_bucket_field(field_str: str) -> Optional[tuple[int, int]]:
    """Parse 'Prob: 475bps - 500bps' -> (475, 500). Returns None if not a bucket field."""
    m = PROB_BUCKET_RE.match(field_str.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def load_mpt_raw(force_download: bool = False) -> pd.DataFrame:
    """Load raw MPT data from Excel (DATA sheet)."""
    xlsx_path = download_mpt_xlsx(force=force_download)
    df = pd.read_excel(xlsx_path, sheet_name="DATA", engine="openpyxl")
    return df


def reshape_mpt_to_fedwatch_schema(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Reshape MPT raw data to fedwatch-compatible schema.

    Input columns: date, reference_start, target_range, field, value
    Output columns: observation_date, meeting_date, rate_bucket_low, rate_bucket_high,
                    probability, source
    - Filters to bucket probability rows only
    - Converts bps to percent (divide by 100)
    - Converts probability percent to fraction (divide by 100)
    """
    raw_df = raw_df.copy()
    bucket_parsed = raw_df["field"].astype(str).apply(parse_bucket_field)

    mask = bucket_parsed.notna()
    bucket_rows = raw_df[mask].copy()
    bucket_rows[["bucket_low_bps", "bucket_high_bps"]] = pd.DataFrame(
        bucket_parsed[mask].tolist(),
        index=bucket_rows.index,
    )

    output = pd.DataFrame({
        "observation_date": pd.to_datetime(bucket_rows["date"]),
        "meeting_date": pd.to_datetime(bucket_rows["reference_start"]),
        "rate_bucket_low": bucket_rows["bucket_low_bps"].astype(float) / 100.0,
        "rate_bucket_high": bucket_rows["bucket_high_bps"].astype(float) / 100.0,
        "probability": bucket_rows["value"].astype(float) / 100.0,
        "source": "atlanta_fed_mpt",
    })

    output = output[output["probability"] > 0].reset_index(drop=True)
    output = output.sort_values(
        ["observation_date", "meeting_date", "rate_bucket_low"]
    ).reset_index(drop=True)

    return output


def build_mpt_dataset(
    force_download: bool = False,
    output_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Full pipeline: download MPT -> reshape -> persist Parquet."""
    raw = load_mpt_raw(force_download=force_download)
    logger.info(f"Loaded raw MPT: {len(raw)} rows, {raw['date'].nunique()} unique dates")

    final = reshape_mpt_to_fedwatch_schema(raw)
    logger.info(f"Reshaped to fedwatch schema: {len(final)} rows")

    output = Path(output_path) if output_path else OUTPUT_PARQUET
    output.parent.mkdir(parents=True, exist_ok=True)
    final.to_parquet(output, index=False)
    logger.info(f"Persisted to {output}")

    return final


def load_mpt_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    rebuild: bool = False,
) -> pd.DataFrame:
    """Public interface: load MPT FedWatch history from Parquet, rebuild if needed."""
    if rebuild or not OUTPUT_PARQUET.exists():
        build_mpt_dataset(force_download=rebuild)

    df = pd.read_parquet(OUTPUT_PARQUET)

    if start_date:
        df = df[df["observation_date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["observation_date"] <= pd.Timestamp(end_date)]

    return df.reset_index(drop=True)
