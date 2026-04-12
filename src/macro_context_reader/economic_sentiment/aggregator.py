"""Beige Book sentiment aggregator — PRD-102 CC-1.

Combines national summary + 12 district report scores into a single
aggregate per publication. Preserves both perspectives.

District weights from Boston Fed research (November 2025):
"The Beige Book's Value for Forecasting Recessions"
  NY, SF identified as most predictive for financial markets
  Chicago, Atlanta strong for macroeconomic indicators
  Kansas City, Minneapolis less predictive

Refs: PRD-102 CC-1
"""

from __future__ import annotations

import logging

from macro_context_reader.economic_sentiment.schemas import (
    BeigeBookAggregateSentiment,
    SectionSentiment,
)

logger = logging.getLogger(__name__)

# District weights -- Boston Fed research (November 2025)
# "The Beige Book's Value for Forecasting Recessions"
DISTRICT_WEIGHTS: dict[str, float] = {
    "New York": 1.5,
    "San Francisco": 1.5,
    "Chicago": 1.3,
    "Atlanta": 1.3,
    "Boston": 1.0,
    "Philadelphia": 1.0,
    "Cleveland": 1.0,
    "Richmond": 1.0,
    "St. Louis": 1.0,
    "Dallas": 1.0,
    "Kansas City": 0.8,
    "Minneapolis": 0.8,
}
# Total raw weight = 13.4; normalization applied in aggregate_publication


def aggregate_publication(
    national: SectionSentiment | None,
    districts: list[SectionSentiment],
) -> BeigeBookAggregateSentiment:
    """Combine national summary + district reports into one aggregate.

    Output preserves BOTH perspectives:
      - national_score: from national summary section
      - district_scores: individual per-district scores
      - district_weighted_score: weighted mean (Boston Fed weights)
      - national_district_divergence: national - district_weighted
        Signal: when national narrative differs from district ground truth

    Args:
        national: SectionSentiment for national summary (may be None).
        districts: List of SectionSentiment for district reports.

    Returns:
        BeigeBookAggregateSentiment with all perspectives.
    """
    district_map = {}
    for d in districts:
        if d.district is not None:
            district_map[d.district] = d.sentiment_score

    # Weighted district aggregate
    weighted_sum = 0.0
    weight_total = 0.0
    for dist, score in district_map.items():
        w = DISTRICT_WEIGHTS.get(dist, 1.0)
        weighted_sum += w * score
        weight_total += w

    district_weighted = weighted_sum / weight_total if weight_total > 0 else 0.0

    # Divergence
    divergence = None
    if national is not None:
        divergence = national.sentiment_score - district_weighted

    pub_date = national.publication_date if national else districts[0].publication_date

    return BeigeBookAggregateSentiment(
        publication_date=pub_date,
        national_score=national.sentiment_score if national else None,
        district_scores=district_map,
        district_weighted_score=round(district_weighted, 4),
        national_district_divergence=round(divergence, 4) if divergence is not None else None,
    )
