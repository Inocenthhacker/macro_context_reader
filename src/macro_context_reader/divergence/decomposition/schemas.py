"""Pydantic schemas for decomposition results."""
from __future__ import annotations

from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DecompositionResult(BaseModel):
    """Result of decomposing a time series into deep current + surface wave.

    Attributes
    ----------
    method : Literal["hp_filter", "emd"]
        Which decomposition method was used
    deep_current : pd.Series
        Slow-moving structural trend (months-quarters horizon)
    surface_wave : pd.Series
        Fast-moving cyclical/noise component (days-weeks horizon)
    residual : pd.Series | None
        Residual component (only meaningful for EMD; None for HP filter)
    metadata : dict
        Method-specific parameters used
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    method: Literal["hp_filter", "emd"]
    deep_current: pd.Series
    surface_wave: pd.Series
    residual: pd.Series | None = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("deep_current", "surface_wave")
    @classmethod
    def no_nan_in_main_components(cls, v: pd.Series) -> pd.Series:
        if v.isna().any():
            raise ValueError("Decomposition output contains NaN values")
        return v
