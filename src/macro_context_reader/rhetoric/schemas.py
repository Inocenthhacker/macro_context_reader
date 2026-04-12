"""Pydantic schemas for FOMC Rhetoric Pipeline — PRD-101 CC-1.

Defines validation models for documents, sentence scores,
document-level scores, and ensemble outputs.

Refs: PRD-101 CC-1
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class FOMCDocument(BaseModel):
    """A single FOMC communication document."""

    model_config = ConfigDict(frozen=True)

    date: datetime
    doc_type: Literal["statement", "minutes", "press_conference", "speech"]
    url: str
    title: str
    raw_text: str
    source_file: Optional[Path] = None


class SentenceScore(BaseModel):
    """Classification result for a single sentence."""

    model_config = ConfigDict(frozen=True)

    sentence: str
    sentence_idx: int
    score_hawkish: float = Field(..., ge=0.0, le=1.0)
    score_dovish: float = Field(..., ge=0.0, le=1.0)
    score_neutral: float = Field(..., ge=0.0, le=1.0)
    label: Literal["hawkish", "dovish", "neutral"]
    confidence: float = Field(..., ge=0.0, le=1.0)


class DocumentScore(BaseModel):
    """Aggregate score for a full document from one scorer."""

    model_config = ConfigDict(frozen=True)

    doc_date: datetime
    doc_type: str
    scorer_name: str
    n_sentences: int
    n_hawkish: int
    n_dovish: int
    n_neutral: int
    net_score: float = Field(
        ..., ge=-1.0, le=1.0,
        description="(n_hawkish - n_dovish) / n_total",
    )
    mean_confidence: float = Field(..., ge=0.0, le=1.0)


class EnsembleScore(BaseModel):
    """Combined score from multiple scorers + matched-filter weighting."""

    model_config = ConfigDict(frozen=True)

    doc_date: datetime
    doc_type: str
    doc_url: str
    doc_title: str
    n_sentences: int
    scores_per_model: dict[str, float] = Field(
        ..., description="net_score per scorer name"
    )
    ensemble_net_score: float = Field(
        ..., description="Mean net_score across all scorers"
    )
    cosine_similarity: float = Field(..., ge=0.0, le=1.0)
    weighted_net_score: float = Field(
        ..., description="ensemble_net_score * cosine_similarity"
    )
    agreement_rate: float = Field(
        ..., ge=0.0, le=1.0,
        description="Fraction of sentences where all scorers agree on label"
    )
    agreement_confidence: Literal["HIGH", "MEDIUM", "LOW"]
