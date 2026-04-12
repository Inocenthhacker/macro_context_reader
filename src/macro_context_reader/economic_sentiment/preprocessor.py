"""Beige Book text preprocessor — PRD-102 CC-1.

Reuses sentence segmentation from rhetoric module (spaCy en_core_web_sm).
Beige Book text needs identical treatment: dehyphenation, whitespace
normalization, sentence splitting, min-word filtering.

Refs: PRD-102 CC-1
"""

from __future__ import annotations

from macro_context_reader.economic_sentiment.schemas import BeigeBookDocument
from macro_context_reader.rhetoric.preprocessor import segment_sentences


def preprocess_beige_book(doc: BeigeBookDocument, min_words: int = 5) -> list[str]:
    """Segment Beige Book section text into sentences.

    Args:
        doc: Beige Book document (national or district).
        min_words: Minimum word count per sentence.

    Returns:
        List of cleaned sentences with >= min_words words each.
    """
    return segment_sentences(doc.raw_text, min_words=min_words)
