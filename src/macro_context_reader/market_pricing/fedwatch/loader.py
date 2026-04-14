"""Multi-snapshot loader with dedup + Parquet persistence — PRD-202 CC-2.

Reads all CME FedWatch CSV snapshots from data/market_pricing/fedwatch_snapshots/,
merges them with dedup on (observation_date, meeting_date, rate_bucket_low),
keeping rows from the LATEST snapshot when duplicates exist (CME may revise
historical probabilities).

Master persisted at data/market_pricing/fedwatch_history.parquet.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from .parser import _parse_snapshot_date_from_filename, parse_fedwatch_csv

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
SNAPSHOTS_DIR = _REPO_ROOT / "data" / "market_pricing" / "fedwatch_snapshots"
MASTER_PARQUET = _REPO_ROOT / "data" / "market_pricing" / "fedwatch_history.parquet"


def list_available_snapshots(snapshots_dir: Optional[Path] = None) -> list[Path]:
    """Return FedMeetingHistory_*.csv files with valid date stamps, ascending by date.

    Emits logging.warning for any CSV in the folder that doesn't match
    the expected pattern (FedMeetingHistory_YYYYMMDD.csv) — surfaces
    accidental renames or misplaced files instead of silently dropping them.
    """
    folder = Path(snapshots_dir) if snapshots_dir else SNAPSHOTS_DIR
    if not folder.exists():
        return []

    valid: list[tuple] = []
    for f in sorted(folder.glob("*.csv")):
        if not f.name.startswith("FedMeetingHistory_"):
            logger.warning(
                "Ignoring CSV with unexpected name: %s. "
                "Expected pattern: FedMeetingHistory_YYYYMMDD.csv",
                f.name,
            )
            continue
        try:
            d = _parse_snapshot_date_from_filename(f)
        except ValueError as e:
            logger.warning(
                "Cannot parse snapshot date from filename %s: %s. Skipping.",
                f.name,
                str(e),
            )
            continue
        valid.append((d, f))

    valid.sort(key=lambda t: t[0])
    return [f for _, f in valid]


def load_all_snapshots(
    snapshots_dir: Optional[Path] = None,
    verbose: bool = False,
) -> pd.DataFrame:
    """Load all snapshots, merge with dedup (latest snapshot wins).

    Returns DataFrame with columns:
      observation_date, meeting_date, rate_bucket_low, rate_bucket_high,
      probability, source_snapshot_date
    """
    files = list_available_snapshots(snapshots_dir)
    if not files:
        target = snapshots_dir or SNAPSHOTS_DIR
        raise FileNotFoundError(
            f"No snapshots found in {target}. "
            f"Place FedMeetingHistory_YYYYMMDD.csv files there."
        )

    parts: list[pd.DataFrame] = []
    for f in files:
        snapshot_date = _parse_snapshot_date_from_filename(f)
        df = parse_fedwatch_csv(f)
        df["source_snapshot_date"] = pd.Timestamp(snapshot_date)
        parts.append(df)
        if verbose:
            print(f"Loaded {f.name}: {len(df)} rows, snapshot_date={snapshot_date}")

    combined = pd.concat(parts, ignore_index=True)
    combined = combined.sort_values(
        ["observation_date", "meeting_date", "rate_bucket_low", "source_snapshot_date"]
    )
    combined = combined.drop_duplicates(
        subset=["observation_date", "meeting_date", "rate_bucket_low"],
        keep="last",
    )
    return combined.reset_index(drop=True)


def build_master_dataset(
    snapshots_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
    verbose: bool = False,
) -> pd.DataFrame:
    """Rebuild master Parquet from all available snapshots. Overwrites existing."""
    df = load_all_snapshots(snapshots_dir, verbose=verbose)
    output = Path(output_path) if output_path else MASTER_PARQUET
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False)
    if verbose:
        print(f"Master dataset written: {output} ({len(df)} rows)")
    return df


def load_fedwatch_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    rebuild: bool = False,
) -> pd.DataFrame:
    """Public interface: load FedWatch history from master Parquet.

    If master is missing or rebuild=True, rebuilds from snapshots folder.
    `start_date` / `end_date` filter on observation_date (ISO YYYY-MM-DD), inclusive.
    """
    if rebuild or not MASTER_PARQUET.exists():
        df = build_master_dataset()
    else:
        df = pd.read_parquet(MASTER_PARQUET)

    if start_date:
        df = df[df["observation_date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["observation_date"] <= pd.Timestamp(end_date)]

    return df.reset_index(drop=True)
