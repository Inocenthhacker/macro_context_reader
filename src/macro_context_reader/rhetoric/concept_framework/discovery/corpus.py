"""Corpus assembly for LDA and Word2Vec/FastText training."""

from __future__ import annotations


def build_corpus(source: str = "beige_book", start_year: int = 1990) -> list[str]:
    """Assembles text list for LDA and Word2Vec training.

    TODO: start_year decided empirically (1990 vs 2000 vs 2010).
    """
    raise NotImplementedError("TODO: PRD-102")
