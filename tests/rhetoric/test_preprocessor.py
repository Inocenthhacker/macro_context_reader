"""Tests for FOMC text preprocessor — PRD-101 CC-1.

Tests use a mock spaCy-like segmenter to avoid model download in CI.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from macro_context_reader.rhetoric.preprocessor import (
    _dehyphenate,
    _normalize_whitespace,
)


def test_dehyphenate_line_break() -> None:
    assert _dehyphenate("con-\ntext") == "context"
    assert _dehyphenate("infla-\n tion") == "inflation"


def test_dehyphenate_preserves_real_hyphens() -> None:
    assert _dehyphenate("well-known") == "well-known"
    assert _dehyphenate("data-driven approach") == "data-driven approach"


def test_normalize_whitespace() -> None:
    assert _normalize_whitespace("  hello   world  \n\n  ") == "hello world"
    assert _normalize_whitespace("a\n\n\nb") == "a b"


def test_segment_sentences_filters_short() -> None:
    """Sentences with fewer than min_words should be filtered out."""
    # Mock spaCy to avoid model download
    mock_nlp = MagicMock()
    mock_nlp.max_length = 1000000

    class FakeSent:
        def __init__(self, t):
            self.text = t

    mock_doc = MagicMock()
    mock_doc.sents = [
        FakeSent("The Committee decided to raise rates by 25 basis points."),
        FakeSent("Hello."),  # too short (1 word)
        FakeSent("See appendix."),  # too short (2 words)
        FakeSent("Inflation remains elevated above the two percent target set by the FOMC."),
    ]
    mock_nlp.return_value = mock_doc

    with patch("macro_context_reader.rhetoric.preprocessor._get_nlp", return_value=mock_nlp):
        from macro_context_reader.rhetoric.preprocessor import segment_sentences
        result = segment_sentences("dummy text", min_words=5)

    assert len(result) == 2
    assert "Committee decided" in result[0]
    assert "Inflation remains" in result[1]


def test_preprocess_document_returns_list() -> None:
    mock_nlp = MagicMock()
    mock_nlp.max_length = 1000000

    class FakeSent:
        def __init__(self, t):
            self.text = t

    mock_doc = MagicMock()
    mock_doc.sents = [
        FakeSent("The economy grew at a moderate pace in the first quarter."),
    ]
    mock_nlp.return_value = mock_doc

    with patch("macro_context_reader.rhetoric.preprocessor._get_nlp", return_value=mock_nlp):
        from macro_context_reader.rhetoric.preprocessor import preprocess_document
        result = preprocess_document("dummy text")

    assert isinstance(result, list)
    assert len(result) == 1
