"""Schemas for synthetic FedWatch reconstruction (Atlanta Fed MPT + FRED interpolation)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FedWatchSyntheticRow(BaseModel):
    """Single row of synthetic FedWatch output (matches manual schema)."""
    observation_date: date
    meeting_date: date
    rate_bucket_low: float = Field(..., description="Lower bound in percent (e.g., 4.75)")
    rate_bucket_high: float = Field(..., description="Upper bound in percent (e.g., 5.00)")
    probability: float = Field(..., ge=0.0, le=1.0)
    source: Literal["atlanta_fed_mpt", "fred_fedfunds_interpolated", "manual_cme_snapshot"]

    model_config = ConfigDict(frozen=True)
