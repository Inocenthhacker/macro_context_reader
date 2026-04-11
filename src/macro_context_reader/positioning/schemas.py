"""Pydantic schemas for positioning module.

Mirrors the pattern used in market_pricing/schemas.py:
row-by-row validation with explicit NaN rejection via model_validator.
"""

from __future__ import annotations

from datetime import datetime
import math

from pydantic import BaseModel, ConfigDict, Field, model_validator


class COTStructuralRow(BaseModel):
    """Single row of CFTC COT TFF Futures-only structural signals for EUR.

    Source: CFTC Commitment of Traders, Traders in Financial Futures (TFF),
    Futures-only, EURO FX - CHICAGO MERCANTILE EXCHANGE contract.
    Frequency: weekly (published Friday for Tuesday positions, 3-day lag).

    Refs: PRD-400 CC-1
    """

    model_config = ConfigDict(frozen=True)

    date: datetime = Field(description="Tuesday of the reporting week")
    lev_net: int = Field(
        description="Leveraged Funds net positions (long - short)"
    )
    am_net: int = Field(
        description="Asset Managers net positions (long - short)"
    )
    lev_delta_wow: float | None = Field(
        description="Week-over-week delta of lev_net (None for first row)"
    )
    lev_percentile_52w: float | None = Field(
        description="Rolling 52-week percentile of lev_net (None until week 52)"
    )

    @model_validator(mode="after")
    def _reject_nan(self) -> COTStructuralRow:
        """Reject NaN in required numeric fields (lev_net, am_net).

        lev_delta_wow and lev_percentile_52w are Optional and allowed NaN
        for leading rows (first row / first 51 rows respectively).
        """
        for name in ("lev_net", "am_net"):
            value = getattr(self, name)
            if isinstance(value, float) and math.isnan(value):
                raise ValueError(f"{name} must not be NaN")
        return self
