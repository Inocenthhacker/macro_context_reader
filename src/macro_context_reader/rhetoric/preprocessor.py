"""FOMC Text Preprocessor — PRD-101 CC-1.

Sentence segmentation, dehyphenation, whitespace normalization.
Uses spaCy en_core_web_sm for sentence boundaries.

Refs: PRD-101 CC-1
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_NLP = None


def _get_nlp():
    """Lazy-load spaCy model (download if missing)."""
    global _NLP
    if _NLP is not None:
        return _NLP
    try:
        import spacy
        try:
            _NLP = spacy.load("en_core_web_sm")
        except OSError:
            logger.info("Downloading spaCy en_core_web_sm model...")
            from spacy.cli import download
            download("en_core_web_sm")
            _NLP = spacy.load("en_core_web_sm")
        return _NLP
    except ImportError:
        raise ImportError(
            "spaCy is required for sentence segmentation. "
            "Install: pip install spacy && python -m spacy download en_core_web_sm"
        )


def _dehyphenate(text: str) -> str:
    """Fix line-break hyphenation: 'con-\\ntext' -> 'context'."""
    return re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace/newlines into single space."""
    return re.sub(r"\s+", " ", text).strip()


def segment_sentences(text: str, min_words: int = 5) -> list[str]:
    """Split text into sentences using spaCy.

    Args:
        text: Raw document text.
        min_words: Minimum word count per sentence (filters headers/captions).

    Returns:
        List of cleaned sentences with >= min_words words each.
    """
    text = _dehyphenate(text)
    text = _normalize_whitespace(text)

    nlp = _get_nlp()
    # Increase max_length for long documents
    nlp.max_length = max(nlp.max_length, len(text) + 1000)
    doc = nlp(text)

    sentences = []
    for sent in doc.sents:
        clean = sent.text.strip()
        if len(clean.split()) >= min_words:
            sentences.append(clean)

    return sentences


def preprocess_document(raw_text: str, min_words: int = 5) -> list[str]:
    """Full preprocessing pipeline: dehyphenate, normalize, segment.

    Args:
        raw_text: Raw text from scraper.
        min_words: Minimum words per sentence.

    Returns:
        List of clean, filtered sentences.
    """
    return segment_sentences(raw_text, min_words=min_words)
