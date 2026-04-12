"""FOMC Rhetoric Scoring Pipeline — PRD-101 CC-1.

Orchestrator: scrape → preprocess → score (3 models) → matched-filter → ensemble.
Persists results as Parquet. Incremental: skips already-scored documents.

Refs: PRD-101 CC-1
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from macro_context_reader.rhetoric.ensemble import compute_ensemble_score
from macro_context_reader.rhetoric.matched_filter import compute_matched_filter_weight
from macro_context_reader.rhetoric.preprocessor import preprocess_document
from macro_context_reader.rhetoric.schemas import EnsembleScore, FOMCDocument
from macro_context_reader.rhetoric.scraper import (
    fetch_fomc_minutes,
    fetch_fomc_statements,
    fetch_press_conferences,
    fetch_speeches,
)

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = Path("data/rhetoric/fomc_scores.parquet")

FETCHER_MAP = {
    "statement": fetch_fomc_statements,
    "minutes": fetch_fomc_minutes,
    "press_conference": fetch_press_conferences,
    "speech": fetch_speeches,
}


def _load_scorers(scorer_names: list[str] | None = None):
    """Lazy-load requested scorers."""
    scorers = {}
    names = scorer_names or ["fomc_roberta", "finbert_fomc", "llama_deepinfra"]

    if "fomc_roberta" in names:
        from macro_context_reader.rhetoric.scorers.fomc_roberta import FOMCRobertaScorer
        scorers["fomc_roberta"] = FOMCRobertaScorer()
    if "finbert_fomc" in names:
        from macro_context_reader.rhetoric.scorers.finbert_fomc import FinBERTFOMCScorer
        scorers["finbert_fomc"] = FinBERTFOMCScorer()
    if "llama_deepinfra" in names:
        from macro_context_reader.rhetoric.scorers.llama_deepinfra import LlamaDeepInfraScorer
        scorers["llama_deepinfra"] = LlamaDeepInfraScorer()

    return scorers


def run_full_pipeline(
    start_year: int = 2015,
    end_date: datetime | None = None,
    doc_types: list[str] | None = None,
    scorer_names: list[str] | None = None,
    force_refetch: bool = False,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> pd.DataFrame:
    """Run the complete rhetoric scoring pipeline.

    Args:
        start_year: Earliest year to scrape.
        end_date: Latest date (default: now).
        doc_types: Which document types to process (default: all).
        scorer_names: Which scorers to use (default: all three).
        force_refetch: If True, re-scrape even if cached.
        output_path: Path for output Parquet.

    Returns:
        DataFrame with one row per document, all scoring columns.
    """
    if end_date is None:
        end_date = datetime.now()
    if doc_types is None:
        doc_types = ["statement", "minutes", "press_conference", "speech"]

    # Load existing results for incremental processing
    existing_urls: set[str] = set()
    if output_path.exists() and not force_refetch:
        existing_df = pd.read_parquet(output_path)
        existing_urls = set(existing_df["doc_url"].tolist())
        logger.info("Loaded %d existing scores from cache", len(existing_urls))
    else:
        existing_df = None

    # Fetch documents
    all_docs: list[FOMCDocument] = []
    for dtype in doc_types:
        fetcher = FETCHER_MAP.get(dtype)
        if fetcher is None:
            logger.warning("Unknown doc_type: %s", dtype)
            continue
        docs = fetcher(start_year=start_year)
        # Filter by end_date
        docs = [d for d in docs if d.date <= end_date]
        all_docs.extend(docs)
    logger.info("Fetched %d total documents", len(all_docs))

    # Filter to new documents only
    new_docs = [d for d in all_docs if d.url not in existing_urls]
    logger.info("New documents to score: %d (skipped %d cached)",
                len(new_docs), len(all_docs) - len(new_docs))

    if not new_docs:
        if existing_df is not None:
            return existing_df
        return pd.DataFrame()

    # Load scorers
    scorers = _load_scorers(scorer_names)
    logger.info("Loaded scorers: %s", list(scorers.keys()))

    # Score each document
    results: list[dict] = []
    for i, doc in enumerate(new_docs):
        logger.info(
            "Scoring [%d/%d] %s %s...",
            i + 1, len(new_docs), doc.doc_type, doc.date.strftime("%Y-%m-%d"),
        )

        sentences = preprocess_document(doc.raw_text)
        if not sentences:
            logger.warning("No sentences after preprocessing: %s", doc.url)
            continue

        # Score with each model
        doc_scores = {}
        sentence_scores = {}
        for name, scorer in scorers.items():
            try:
                ss = scorer.score_sentences(sentences)
                ds = scorer.score_document_sentences(sentences, doc.date, doc.doc_type)
                doc_scores[name] = ds
                sentence_scores[name] = ss
            except Exception as e:
                logger.error("Scorer %s failed on %s: %s", name, doc.url, e)

        if not doc_scores:
            continue

        # Matched-filter weight
        cosine_sim = compute_matched_filter_weight(doc, all_docs)

        # Ensemble
        ens = compute_ensemble_score(doc, doc_scores, sentence_scores, cosine_sim)

        row = {
            "date": ens.doc_date,
            "doc_type": ens.doc_type,
            "doc_url": ens.doc_url,
            "doc_title": ens.doc_title,
            "n_sentences": ens.n_sentences,
            "ensemble_net": ens.ensemble_net_score,
            "cosine_sim": ens.cosine_similarity,
            "weighted_score": ens.weighted_net_score,
            "agreement_rate": ens.agreement_rate,
            "confidence": ens.agreement_confidence,
        }
        # Add per-model net scores
        for name, net in ens.scores_per_model.items():
            row[f"{name}_net"] = net
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
        combined = combined.sort_values("date").reset_index(drop=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(output_path, index=False)
        logger.info("Saved %d total scores to %s", len(combined), output_path)

    return combined
