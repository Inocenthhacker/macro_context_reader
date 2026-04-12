"""Base interface for sentence scorers — PRD-101 CC-1.

All scorers implement the SentenceScorer protocol.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from macro_context_reader.rhetoric.schemas import DocumentScore, SentenceScore


@runtime_checkable
class SentenceScorer(Protocol):
    """Protocol for all FOMC rhetoric scorers."""

    name: str

    def score_sentences(self, sentences: list[str]) -> list[SentenceScore]:
        """Score a list of sentences, returning classification for each."""
        ...

    def score_document_sentences(
        self, sentences: list[str], doc_date, doc_type: str
    ) -> DocumentScore:
        """Score all sentences and aggregate into DocumentScore."""
        ...
