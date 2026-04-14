"""Parser for CME FedWatch Historical CSV snapshots — PRD-202.

Format:
- Row 0: meeting labels spread horizontally with padding commas
  ("History for 29 Apr 2026 Fed meeting" at the start of each block)
- Row 1: rate bucket headers, e.g. "Date,(0-25),(25-50),...,(1575-1600),(0-25),..."
- Rows 2+: daily observations, date in DD.MM.YYYY (European)
- Each block has 63 rate buckets (0-25 bps through 1550-1575 bps in 25 bps steps)
- 15 meeting blocks per file (typical)

Output: long-format DataFrame
{observation_date, meeting_date, rate_bucket_low, rate_bucket_high, probability}
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .schemas import FedWatchSnapshot

MEETING_HEADER_RE = re.compile(
    r"History for (\d{1,2})\s+(\w+)\s+(\d{4})\s+Fed meeting",
    re.IGNORECASE,
)
RATE_BUCKET_RE = re.compile(r"\((\d+)-(\d+)\)")
BUCKETS_PER_BLOCK = 63

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_meeting_date(label: str) -> date:
    """'History for 29 Apr 2026 Fed meeting' -> date(2026, 4, 29)."""
    match = MEETING_HEADER_RE.search(label)
    if not match:
        raise ValueError(f"Cannot parse meeting label: {label!r}")
    day, month_str, year = match.groups()
    month = MONTH_MAP.get(month_str[:3].lower())
    if not month:
        raise ValueError(f"Unknown month: {month_str}")
    return date(int(year), month, int(day))


def _parse_snapshot_date_from_filename(path: Path) -> date:
    """'FedMeetingHistory_20260414.csv' -> date(2026, 4, 14)."""
    match = re.search(r"(\d{8})", path.stem)
    if not match:
        raise ValueError(f"Cannot extract date from filename: {path.name}")
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def _identify_meeting_blocks(header_row: list[str]) -> list[tuple[int, date]]:
    """Find column indices where each meeting block label appears."""
    blocks: list[tuple[int, date]] = []
    for col_idx, cell in enumerate(header_row):
        text = str(cell)
        if "History for" in text and "Fed meeting" in text:
            blocks.append((col_idx, _parse_meeting_date(text)))
    return blocks


def parse_fedwatch_csv(csv_path: Path) -> pd.DataFrame:
    """Parse a CME FedWatch Historical CSV into long-format DataFrame.

    Returns columns:
        observation_date (datetime64), meeting_date (datetime64),
        rate_bucket_low (int), rate_bucket_high (int),
        probability (float in (0, 1])
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    raw = pd.read_csv(csv_path, header=None, dtype=str, keep_default_na=False)
    if len(raw) < 3:
        raise ValueError(f"CSV too short: {len(raw)} rows, expected >= 3")

    meeting_header_row = raw.iloc[0].tolist()
    bucket_header_row = raw.iloc[1].tolist()

    blocks = _identify_meeting_blocks(meeting_header_row)
    if not blocks:
        raise ValueError("No meeting blocks found in header row 0")

    records: list[dict] = []

    for block_idx, (_, meeting_date) in enumerate(blocks):
        # Buckets for block i live at columns [1 + i*63, 1 + (i+1)*63)
        # (column 0 is the Date column).
        bucket_start = 1 + block_idx * BUCKETS_PER_BLOCK
        bucket_end = bucket_start + BUCKETS_PER_BLOCK

        buckets: list[tuple[int, int, int]] = []
        for col in range(bucket_start, min(bucket_end, len(bucket_header_row))):
            m = RATE_BUCKET_RE.search(str(bucket_header_row[col]))
            if m:
                buckets.append((col, int(m.group(1)), int(m.group(2))))

        if not buckets:
            continue

        for row_idx in range(2, len(raw)):
            row = raw.iloc[row_idx]
            date_str = str(row.iloc[0]).strip()
            if not date_str:
                continue
            try:
                obs_date = datetime.strptime(date_str, "%d.%m.%Y").date()
            except ValueError:
                continue

            for col, low, high in buckets:
                if col >= len(row):
                    continue
                value_str = str(row.iloc[col]).strip()
                if value_str == "" or value_str == ",":
                    continue
                try:
                    prob = float(value_str)
                except ValueError:
                    continue
                if prob == 0.0:
                    continue

                records.append({
                    "observation_date": obs_date,
                    "meeting_date": meeting_date,
                    "rate_bucket_low": low,
                    "rate_bucket_high": high,
                    "probability": prob,
                })

    if not records:
        raise ValueError(f"No records parsed from {csv_path}")

    df = pd.DataFrame(records)
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["meeting_date"] = pd.to_datetime(df["meeting_date"])
    df = (
        df.sort_values(["observation_date", "meeting_date", "rate_bucket_low"])
          .reset_index(drop=True)
    )
    return df


def get_snapshot_metadata(csv_path: Path) -> FedWatchSnapshot:
    """Parse the CSV and return summary metadata."""
    csv_path = Path(csv_path)
    df = parse_fedwatch_csv(csv_path)
    return FedWatchSnapshot(
        snapshot_date=_parse_snapshot_date_from_filename(csv_path),
        source_file=csv_path.name,
        meeting_dates=sorted(df["meeting_date"].dt.date.unique().tolist()),
        observation_date_range=(
            df["observation_date"].min().date(),
            df["observation_date"].max().date(),
        ),
        row_count=len(df),
    )
