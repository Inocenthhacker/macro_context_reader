"""Tests for Beige Book preprocessor — PRD-102 CC-1."""

from __future__ import annotations

from datetime import datetime

from macro_context_reader.economic_sentiment.preprocessor import preprocess_beige_book
from macro_context_reader.economic_sentiment.schemas import BeigeBookDocument


def _make_doc(text: str) -> BeigeBookDocument:
    return BeigeBookDocument(
        publication_date=datetime(2024, 1, 15),
        section_type="national_summary",
        district=None,
        url="https://example.com",
        raw_text=text,
    )


def test_segments_sentences() -> None:
    doc = _make_doc(
        "Economic activity expanded at a moderate pace. "
        "Consumer spending was strong across most districts. "
        "Manufacturing output contracted slightly."
    )
    sentences = preprocess_beige_book(doc)
    assert len(sentences) >= 2


def test_filters_short_fragments() -> None:
    doc = _make_doc("GDP grew. That was good. Economic activity expanded at a solid pace overall.")
    sentences = preprocess_beige_book(doc, min_words=5)
    # "GDP grew." and "That was good." should be filtered (< 5 words)
    assert all(len(s.split()) >= 5 for s in sentences)


def test_handles_empty_text() -> None:
    doc = _make_doc("")
    sentences = preprocess_beige_book(doc)
    assert sentences == []


def test_dehyphenation() -> None:
    doc = _make_doc("Manufac-\nturing activity expanded moderately across all twelve districts.")
    sentences = preprocess_beige_book(doc)
    assert len(sentences) >= 1
    assert "Manufacturing" in sentences[0] or "manufacturing" in sentences[0].lower()
