"""Economic Sentiment Pipeline — PRD-102 CC-1.

Orchestrator: scrape Beige Book -> preprocess -> FinBERT score -> aggregate.
Persists results as Parquet. Incremental: skips already-scored publications.

Output columns:
  - publication_date
  - national_score
  - district_weighted_score
  - national_district_divergence
  - n_sections, n_sentences_total
  - per-district scores (Boston_score, New_York_score, ...)

Refs: PRD-102 CC-1
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from macro_context_reader.economic_sentiment.aggregator import aggregate_publication
from macro_context_reader.economic_sentiment.schemas import (
    BeigeBookAggregateSentiment,
    BeigeBookDocument,
    SectionSentiment,
)
from macro_context_reader.economic_sentiment.scorers.finbert_sentiment import (
    FinBERTSentimentScorer,
)
from macro_context_reader.economic_sentiment.scraper import fetch_all_beige_books

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = Path("data/economic_sentiment/beige_book_sentiment.parquet")


def run_full_pipeline(
    start_year: int = 1970,
    end_date: datetime | None = None,
    force_refetch: bool = False,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> pd.DataFrame:
    """Full backfill pipeline for Beige Book economic sentiment.

    Steps:
      1. Fetch all Beige Book publications (national + districts)
      2. Group by publication_date
      3. Score each section with FinBERTSentimentScorer
      4. Aggregate per publication
      5. Output DataFrame + Parquet

    Args:
        start_year: Earliest year (default: 1970 for full backfill).
        end_date: Latest date (default: now).
        force_refetch: If True, re-scrape even if cached.
        output_path: Path for output Parquet.

    Returns:
        DataFrame with one row per publication date.
    """
    if end_date is None:
        end_date = datetime.now()

    # Load existing results for incremental processing
    existing_dates: set[str] = set()
    existing_df: pd.DataFrame | None = None
    if output_path.exists() and not force_refetch:
        existing_df = pd.read_parquet(output_path)
        existing_dates = set(
            pd.to_datetime(existing_df["publication_date"]).dt.strftime("%Y%m%d")
        )
        logger.info("Loaded %d existing scores from cache", len(existing_dates))

    # Fetch all documents
    all_docs = fetch_all_beige_books(start_year=start_year, end_date=end_date)
    logger.info("Total sections fetched: %d", len(all_docs))

    # Group by publication date
    by_date: dict[str, list[BeigeBookDocument]] = defaultdict(list)
    for doc in all_docs:
        date_key = doc.publication_date.strftime("%Y%m%d")
        by_date[date_key].append(doc)

    # Filter to new publications only
    new_dates = {k: v for k, v in by_date.items() if k not in existing_dates}
    logger.info(
        "New publications to score: %d (skipped %d cached)",
        len(new_dates), len(by_date) - len(new_dates),
    )

    if not new_dates:
        if existing_df is not None:
            return existing_df
        return pd.DataFrame()

    # Load scorer
    scorer = FinBERTSentimentScorer()
    logger.info("Loaded FinBERT sentiment scorer")

    # Score each publication
    results: list[dict] = []
    for i, (date_key, docs) in enumerate(sorted(new_dates.items())):
        pub_date = docs[0].publication_date
        logger.info(
            "Scoring [%d/%d] %s (%d sections)...",
            i + 1, len(new_dates), pub_date.date(), len(docs),
        )

        national_sentiment: SectionSentiment | None = None
        district_sentiments: list[SectionSentiment] = []
        n_sentences_total = 0

        for doc in docs:
            try:
                section_score = scorer.score_section(doc)
                n_sentences_total += section_score.n_sentences

                if doc.section_type == "national_summary":
                    national_sentiment = section_score
                else:
                    district_sentiments.append(section_score)
            except Exception as e:
                logger.error(
                    "Scoring failed for %s %s: %s",
                    doc.section_type, doc.district or "national", e,
                )

        if not district_sentiments and national_sentiment is None:
            logger.warning("No scorable sections for %s", pub_date.date())
            continue

        agg = aggregate_publication(national_sentiment, district_sentiments)

        row: dict = {
            "publication_date": agg.publication_date,
            "national_score": agg.national_score,
            "district_weighted_score": agg.district_weighted_score,
            "national_district_divergence": agg.national_district_divergence,
            "n_sections": len(docs),
            "n_sentences_total": n_sentences_total,
        }
        # Add per-district scores as columns
        for district, score in agg.district_scores.items():
            col_name = district.replace(" ", "_").replace(".", "") + "_score"
            row[col_name] = score

        results.append(row)

    new_df = pd.DataFrame(results)

    # Merge with existing
    if existing_df is not None and not new_df.empty:
        combined = pd.concat([existing_df, new_df], ignore_index=True)
    elif existing_df is not None:
        combined = existing_df
    else:
        combined = new_df

    if not combined.empty:
        combined = combined.sort_values("publication_date").reset_index(drop=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(output_path, index=False)
        logger.info("Saved %d total scores to %s", len(combined), output_path)

    return combined
