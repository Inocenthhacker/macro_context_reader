"""Pydantic schemas for Macro Regime Classifier — PRD-050.

Defines validation models for HMM states, analog matches,
regime classifications, and diagnostic outputs.

Refs: PRD-050 CC-1+2+3
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StateProfile(BaseModel):
    """Profile of a single HMM-discovered regime state."""

    model_config = ConfigDict(frozen=True)

    state_id: int
    label: str = Field(
        ..., description="Auto-generated label, e.g. 'INFLATION_HIGH'"
    )
    dominant_feature: str
    dominant_direction: Literal["HIGH", "LOW"]
    mean_features: dict[str, float] = Field(
        ..., description="Mean z-scored feature values in this state"
    )
    median_duration_months: float
    frequency_pct: float = Field(
        ..., ge=0.0, le=100.0, description="% of total observations in this state"
    )


class HMMFitDiagnostics(BaseModel):
    """Diagnostics from HMM model selection and fitting."""

    model_config = ConfigDict(frozen=True)

    n_states_selected: int
    bic_scores: dict[int, float] = Field(
        ..., description="BIC score per candidate n_states"
    )
    converged: bool
    n_iter_used: int
    log_likelihood: float
    state_profiles: list[StateProfile]


class AnalogMatch(BaseModel):
    """A single historical analog found by Mahalanobis distance."""

    model_config = ConfigDict(frozen=True)

    date: datetime
    distance: float = Field(..., ge=0.0)
    rank: int = Field(..., ge=1)
    hmm_state: Optional[int] = None
    hmm_label: Optional[str] = None
    eurusd_forward_90d_pct: Optional[float] = Field(
        None, description="EUR/USD % change in 90 days after this analog date"
    )


class RegimeClassification(BaseModel):
    """Final consensus regime output combining HMM + Analog signals."""

    model_config = ConfigDict(frozen=True)

    date: datetime
    hmm_state: int
    hmm_label: str
    hmm_state_probs: list[float]
    top_analogs: list[AnalogMatch]
    analog_consensus_label: Optional[str] = None
    final_confidence: Literal["HIGH", "MEDIUM", "LOW"]
    conflicting_signals: bool
