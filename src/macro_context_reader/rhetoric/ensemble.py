"""Ensemble scoring — PRD-101 CC-1.

Combines outputs from multiple scorers (FOMC-RoBERTa, FinBERT-FOMC,
Llama DeepInfra) into a single EnsembleScore with matched-filter weighting.

Agreement confidence:
  HIGH:   >= 70% sentences where all models agree on label
  MEDIUM: >= 50% agreement
  LOW:    < 50% agreement

Refs: PRD-101 CC-1
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from macro_context_reader.rhetoric.schemas import (
    DocumentScore,
    EnsembleScore,
    FOMCDocument,
    SentenceScore,
)

logger = logging.getLogger(__name__)


def _compute_agreement_rate(
    scores_by_model: dict[str, list[SentenceScore]],
) -> float:
    """Fraction of sentences where ALL models assign the same label."""
    model_names = list(scores_by_model.keys())
    if len(model_names) < 2:
        return 1.0

    n_sentences = len(scores_by_model[model_names[0]])
    if n_sentences == 0:
        return 0.0

    agree_count = 0
    for i in range(n_sentences):
        labels = set()
        for name in model_names:
            if i < len(scores_by_model[name]):
                labels.add(scores_by_model[name][i].label)
        if len(labels) == 1:
            agree_count += 1

    return agree_count / n_sentences


def _agreement_confidence(rate: float) -> Literal["HIGH", "MEDIUM", "LOW"]:
    if rate >= 0.70:
        return "HIGH"
    elif rate >= 0.50:
        return "MEDIUM"
    return "LOW"


def compute_ensemble_score(
    doc: FOMCDocument,
    doc_scores: dict[str, DocumentScore],
    sentence_scores: dict[str, list[SentenceScore]],
    cosine_similarity: float,
) -> EnsembleScore:
    """Combine multiple scorer outputs into a single ensemble score.

    Args:
        doc: The source document.
        doc_scores: DocumentScore per scorer name.
        sentence_scores: Raw SentenceScore lists per scorer name (for agreement).
        cosine_similarity: Matched-filter weight from last Powell presser.

    Returns:
        EnsembleScore with weighted and unweighted aggregations.
    """
    net_scores = {name: ds.net_score for name, ds in doc_scores.items()}
    ensemble_net = sum(net_scores.values()) / len(net_scores) if net_scores else 0.0

    agreement_rate = _compute_agreement_rate(sentence_scores)

    return EnsembleScore(
        doc_date=doc.date,
        doc_type=doc.doc_type,
        doc_url=doc.url,
        doc_title=doc.title,
        n_sentences=max(ds.n_sentences for ds in doc_scores.values()) if doc_scores else 0,
        scores_per_model=net_scores,
        ensemble_net_score=round(ensemble_net, 4),
        cosine_similarity=round(cosine_similarity, 4),
        weighted_net_score=round(ensemble_net * cosine_similarity, 4),
        agreement_rate=round(agreement_rate, 4),
        agreement_confidence=_agreement_confidence(agreement_rate),
    )
