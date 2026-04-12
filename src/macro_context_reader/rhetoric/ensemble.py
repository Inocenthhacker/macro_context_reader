"""Ensemble scoring — PRD-101 CC-1.

Combines outputs from FOMC-RoBERTa and Llama DeepInfra into a single
EnsembleScore with matched-filter weighting.

FinBERT-FOMC removed 2026-04-12: 20% empirical accuracy on FOMC
hawkish/dovish classification. Sentiment != policy stance.
See debug_llama_disagreement.py for validation data.

Agreement confidence (2-model):
  HIGH:   both models agree on same label
  MEDIUM: one neutral, other directional (hawkish or dovish)
  LOW:    opposite directional labels (hawkish vs dovish) — critical flag

Refs: PRD-101 CC-1, PRD-101/CC-1-FIX7
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

# Empirical weights from debug_llama_disagreement.py (2026-04-12):
# - FOMC-RoBERTa: 100% on 5 test sentences (Shah et al. ACL 2023, purpose-trained)
# - Llama 3.3 70B: 80% on same tests (contextual reasoning, zero-shot)
# Weights reflect accuracy ratio + trust in domain-specific training
ENSEMBLE_WEIGHTS: dict[str, float] = {
    "fomc_roberta": 0.6,
    "llama_deepinfra": 0.4,
}


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


def _agreement_confidence_2model(
    scores_by_model: dict[str, list[SentenceScore]],
) -> Literal["HIGH", "MEDIUM", "LOW"]:
    """2-model agreement logic.

    HIGH:   both agree exactly (same label)
    MEDIUM: one neutral, other directional (hawkish or dovish)
    LOW:    opposite directional labels (hawkish vs dovish) — critical flag
    """
    model_names = list(scores_by_model.keys())
    if len(model_names) < 2:
        return "HIGH"

    n_sentences = len(scores_by_model[model_names[0]])
    if n_sentences == 0:
        return "LOW"

    n_agree = 0
    n_opposite = 0
    for i in range(n_sentences):
        labels = set()
        for name in model_names:
            if i < len(scores_by_model[name]):
                labels.add(scores_by_model[name][i].label)
        if len(labels) == 1:
            n_agree += 1
        elif "hawkish" in labels and "dovish" in labels:
            n_opposite += 1

    if n_opposite > 0 and n_opposite >= n_sentences * 0.3:
        return "LOW"
    if n_agree / n_sentences >= 0.70:
        return "HIGH"
    if n_agree / n_sentences >= 0.50:
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

    # Weighted ensemble: use ENSEMBLE_WEIGHTS for known scorers,
    # fall back to equal weight for any ad-hoc scorers
    total_weight = 0.0
    weighted_sum = 0.0
    for name, net in net_scores.items():
        w = ENSEMBLE_WEIGHTS.get(name, 1.0 / len(net_scores))
        weighted_sum += w * net
        total_weight += w
    ensemble_net = weighted_sum / total_weight if total_weight > 0 else 0.0

    agreement_rate = _compute_agreement_rate(sentence_scores)
    confidence = _agreement_confidence_2model(sentence_scores)

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
        agreement_confidence=confidence,
    )
