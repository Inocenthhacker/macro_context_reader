"""Tests for Beige Book sentiment aggregator — PRD-102 CC-1."""

from __future__ import annotations

from datetime import datetime

import pytest

from macro_context_reader.economic_sentiment.aggregator import (
    DISTRICT_WEIGHTS,
    aggregate_publication,
)
from macro_context_reader.economic_sentiment.schemas import (
    BeigeBookAggregateSentiment,
    SectionSentiment,
)


def _make_section(
    district: str | None = None,
    score: float = 0.0,
    section_type: str = "district_report",
) -> SectionSentiment:
    return SectionSentiment(
        publication_date=datetime(2024, 1, 15),
        section_type=section_type,
        district=district,
        n_sentences=10,
        n_positive=5,
        n_negative=3,
        n_neutral=2,
        sentiment_score=score,
        mean_confidence=0.8,
    )


class TestDistrictWeights:
    def test_all_12_districts(self) -> None:
        assert len(DISTRICT_WEIGHTS) == 12

    def test_ny_sf_highest(self) -> None:
        assert DISTRICT_WEIGHTS["New York"] >= max(
            w for d, w in DISTRICT_WEIGHTS.items() if d not in ("New York", "San Francisco")
        )
        assert DISTRICT_WEIGHTS["San Francisco"] >= max(
            w for d, w in DISTRICT_WEIGHTS.items() if d not in ("New York", "San Francisco")
        )

    def test_no_zero_weights(self) -> None:
        assert all(w > 0 for w in DISTRICT_WEIGHTS.values())


class TestAggregatePublication:
    def test_basic_aggregation(self) -> None:
        national = _make_section(district=None, score=0.3, section_type="national_summary")
        districts = [
            _make_section(district="Boston", score=0.2),
            _make_section(district="New York", score=0.4),
            _make_section(district="San Francisco", score=0.1),
        ]
        result = aggregate_publication(national, districts)
        assert isinstance(result, BeigeBookAggregateSentiment)
        assert result.national_score == 0.3
        assert len(result.district_scores) == 3
        assert result.national_district_divergence is not None

    def test_weighted_score_favors_ny_sf(self) -> None:
        """NY and SF have higher weights, so aggregate should be pulled toward them."""
        districts = [
            _make_section(district="Boston", score=-0.5),
            _make_section(district="New York", score=0.8),
            _make_section(district="San Francisco", score=0.8),
        ]
        result = aggregate_publication(None, districts)
        # NY (1.5) + SF (1.5) pulling positive vs Boston (1.0) pulling negative
        # Weighted: (1.0*-0.5 + 1.5*0.8 + 1.5*0.8) / (1.0+1.5+1.5) = 1.9/4.0 = 0.475
        assert result.district_weighted_score > 0.0

    def test_no_national_returns_none_score(self) -> None:
        districts = [_make_section(district="Boston", score=0.5)]
        result = aggregate_publication(None, districts)
        assert result.national_score is None
        assert result.national_district_divergence is None

    def test_divergence_positive_when_national_more_optimistic(self) -> None:
        national = _make_section(district=None, score=0.5, section_type="national_summary")
        districts = [_make_section(district="Boston", score=-0.2)]
        result = aggregate_publication(national, districts)
        assert result.national_district_divergence > 0

    def test_divergence_negative_when_districts_more_optimistic(self) -> None:
        national = _make_section(district=None, score=-0.3, section_type="national_summary")
        districts = [_make_section(district="Boston", score=0.4)]
        result = aggregate_publication(national, districts)
        assert result.national_district_divergence < 0

    def test_all_12_districts(self) -> None:
        """Full 12-district aggregation."""
        national = _make_section(district=None, score=0.1, section_type="national_summary")
        districts = [
            _make_section(district=d, score=-0.5 + 0.08 * i)
            for i, d in enumerate([
                "Boston", "New York", "Philadelphia", "Cleveland",
                "Richmond", "Atlanta", "Chicago", "St. Louis",
                "Minneapolis", "Kansas City", "Dallas", "San Francisco",
            ])
        ]
        result = aggregate_publication(national, districts)
        assert len(result.district_scores) == 12
        assert -1.0 <= result.district_weighted_score <= 1.0

    def test_uniform_scores_equal_weighted(self) -> None:
        """If all districts have the same score, weighted = that score."""
        districts = [_make_section(district=d, score=0.3) for d in DISTRICT_WEIGHTS]
        result = aggregate_publication(None, districts)
        assert abs(result.district_weighted_score - 0.3) < 0.01

    def test_empty_districts(self) -> None:
        """Edge case: only national, no districts."""
        national = _make_section(district=None, score=0.5, section_type="national_summary")
        result = aggregate_publication(national, [])
        assert result.district_weighted_score == 0.0
        assert len(result.district_scores) == 0
