"""
Semantic expansion of concept seed words via trained embeddings.

ARCHITECTURAL DECISION (confirmed 2026-04-05):
Embeddings model = Word2Vec or FastText trained locally on Beige Book corpus.
Rationale: no pre-trained model exists for central bank language;
FinMTEB (EMNLP 2025) shows 7-9pp drop for general models on financial text.
Fallback for empirical comparison: sentence-transformers/all-MiniLM-L6-v2.
"""

from __future__ import annotations

from typing import Any


def train_embeddings(corpus: list[str], method: str = "word2vec") -> Any:
    """Train Word2Vec or FastText embeddings on the supplied corpus.

    method: 'word2vec' | 'fasttext' — decided empirically.
    """
    raise NotImplementedError("TODO: PRD-102")


def expand_concept(seed_words: list[str], model: Any, top_n: int = 15) -> list[str]:
    """Returns semantically similar words from trained embeddings."""
    raise NotImplementedError("TODO: PRD-102")
