"""Pydantic schemas for Economic Sentiment module — PRD-102 CC-1.

Beige Book: national summary + 12 district reports scored independently.
Sentiment is economic condition (positive/negative/neutral), NOT policy stance.

Refs: PRD-102 CC-1
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DISTRICTS = Literal[
    "Boston", "New York", "Philadelphia", "Cleveland", "Richmond",
    "Atlanta", "Chicago", "St. Louis", "Minneapolis", "Kansas City",
    "Dallas", "San Francisco",
]

SECTION_TYPE = Literal["national_summary", "district_report"]


class BeigeBookDocument(BaseModel):
    """One section of a Beige Book publication (national or one district)."""
    publication_date: datetime
    section_type: SECTION_TYPE
    district: str | None = None  # None for national_summary
    url: str
    raw_text: str
    source_file: Path | None = None

    model_config = {"arbitrary_types_allowed": True}


class SentenceSentiment(BaseModel):
    """Sentence-level economic sentiment classification."""
    sentence: str
    sentence_idx: int
    score_positive: float = Field(ge=0.0, le=1.0)
    score_negative: float = Field(ge=0.0, le=1.0)
    score_neutral: float = Field(ge=0.0, le=1.0)
    label: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)


class SectionSentiment(BaseModel):
    """Aggregate sentiment for one Beige Book section (national or district)."""
    publication_date: datetime
    section_type: SECTION_TYPE
    district: str | None = None
    n_sentences: int
    n_positive: int
    n_negative: int
    n_neutral: int
    # Economic sentiment score: range [-1, +1]
    # +1 = all positive (economy strong), -1 = all negative (economy weak)
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    mean_confidence: float = Field(ge=0.0, le=1.0)


class BeigeBookAggregateSentiment(BaseModel):
    """Aggregated sentiment per Beige Book publication -- both perspectives."""
    publication_date: datetime
    national_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    district_scores: dict[str, float]  # {district_name: score}

    # Aggregated district score -- weighted per Boston Fed research (2025):
    # NY, SF, Chicago, Atlanta = high weight (more predictive)
    # Others = equal weight baseline
    district_weighted_score: float = Field(ge=-1.0, le=1.0)

    # Divergence between national narrative and district reports
    # Positive = national more optimistic than districts
    # Negative = districts more optimistic than national
    national_district_divergence: float | None = None
