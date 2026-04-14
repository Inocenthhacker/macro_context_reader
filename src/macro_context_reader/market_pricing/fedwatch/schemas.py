"""CME FedWatch schemas — PRD-202."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class FedWatchRow(BaseModel):
    """Single probability observation.

    On `observation_date`, the market's implied probability that at
    `meeting_date` the Fed Funds target rate will fall within
    `rate_bucket_low`..`rate_bucket_high` basis points.
    """

    model_config = ConfigDict(frozen=True)

    observation_date: date
    meeting_date: date
    rate_bucket_low: int
    rate_bucket_high: int
    probability: float = Field(ge=0.0, le=1.0)


class FedWatchSnapshot(BaseModel):
    """Metadata for a parsed snapshot file."""

    model_config = ConfigDict(frozen=True)

    snapshot_date: date
    source_file: str
    meeting_dates: list[date]
    observation_date_range: tuple[date, date]
    row_count: int
