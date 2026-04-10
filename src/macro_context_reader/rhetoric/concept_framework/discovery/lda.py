"""LDA topic modelling for concept candidate discovery."""

from __future__ import annotations

from typing import Any


def train_lda(corpus: list[str], n_topics: int = 30) -> Any:
    """Train LDA model on assembled corpus.

    TODO: n_topics unknown until empirical exploration — 30 is a prior.
    """
    raise NotImplementedError("TODO: PRD-102")


def extract_concept_candidates(lda_model: Any, top_n: int = 20) -> dict[str, list[str]]:
    """Returns {topic_label: [top_words]}. Human review required after this step."""
    raise NotImplementedError("TODO: PRD-102")
