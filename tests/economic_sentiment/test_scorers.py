"""Tests for FinBERT sentiment scorer — PRD-102 CC-1."""

from __future__ import annotations

import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from macro_context_reader.economic_sentiment.schemas import (
    BeigeBookDocument,
    SectionSentiment,
    SentenceSentiment,
)

torch_available = False
try:
    import torch
    torch_available = True
except ImportError:
    pass

needs_torch = pytest.mark.skipif(not torch_available, reason="torch not installed")


class TestFinBERTSentimentScorer:
    @needs_torch
    def test_scorer_name(self) -> None:
        from macro_context_reader.economic_sentiment.scorers.finbert_sentiment import (
            FinBERTSentimentScorer,
        )
        scorer = FinBERTSentimentScorer(device="cpu")
        assert scorer.name == "finbert_sentiment"

    @needs_torch
    def test_label_map_direct(self) -> None:
        """Verify DIRECT mapping: positive->positive, negative->negative."""
        from macro_context_reader.economic_sentiment.scorers.finbert_sentiment import (
            LABEL_MAP_DIRECT,
        )
        assert LABEL_MAP_DIRECT["positive"] == "positive"
        assert LABEL_MAP_DIRECT["negative"] == "negative"
        assert LABEL_MAP_DIRECT["neutral"] == "neutral"

    @needs_torch
    def test_score_section_empty_text(self) -> None:
        from macro_context_reader.economic_sentiment.scorers.finbert_sentiment import (
            FinBERTSentimentScorer,
        )
        scorer = FinBERTSentimentScorer(device="cpu")

        # Mock the model to avoid loading
        scorer._load_model = MagicMock()
        scorer.score_sentences = MagicMock(return_value=[])

        doc = BeigeBookDocument(
            publication_date=datetime(2024, 1, 15),
            section_type="national_summary",
            district=None,
            url="https://example.com",
            raw_text="Hi.",  # Too short after filtering
        )
        result = scorer.score_section(doc)
        assert isinstance(result, SectionSentiment)
        assert result.n_sentences == 0
        assert result.sentiment_score == 0.0


class TestSentenceSentimentSchema:
    def test_valid_sentiment(self) -> None:
        s = SentenceSentiment(
            sentence="Manufacturing expanded.",
            sentence_idx=0,
            score_positive=0.8,
            score_negative=0.1,
            score_neutral=0.1,
            label="positive",
            confidence=0.8,
        )
        assert s.label == "positive"

    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(Exception):
            SentenceSentiment(
                sentence="test",
                sentence_idx=0,
                score_positive=1.5,  # out of range
                score_negative=0.0,
                score_neutral=0.0,
                label="positive",
                confidence=0.8,
            )


class TestSectionSentimentSchema:
    def test_sentiment_score_range(self) -> None:
        s = SectionSentiment(
            publication_date=datetime(2024, 1, 15),
            section_type="national_summary",
            district=None,
            n_sentences=10,
            n_positive=7,
            n_negative=1,
            n_neutral=2,
            sentiment_score=0.6,
            mean_confidence=0.8,
        )
        assert -1.0 <= s.sentiment_score <= 1.0

    def test_rejects_score_out_of_range(self) -> None:
        with pytest.raises(Exception):
            SectionSentiment(
                publication_date=datetime(2024, 1, 15),
                section_type="national_summary",
                district=None,
                n_sentences=10,
                n_positive=10,
                n_negative=0,
                n_neutral=0,
                sentiment_score=1.5,  # out of range
                mean_confidence=0.8,
            )


# ---------------------------------------------------------------------------
# Integration tests — require real FinBERT model
# ---------------------------------------------------------------------------

@pytest.mark.integration
@needs_torch
def test_finbert_sentiment_empirical() -> None:
    """Validate FinBERT sentiment classification on economic text.

    This is the CORRECT use case for FinBERT: economic condition
    sentiment, not monetary policy stance.
    """
    from macro_context_reader.economic_sentiment.scorers.finbert_sentiment import (
        FinBERTSentimentScorer,
    )

    scorer = FinBERTSentimentScorer(device="cpu", batch_size=4)

    positive = [
        "Manufacturing activity expanded strongly across the district.",
        "Consumer spending remained robust.",
    ]
    negative = [
        "Manufacturing activity contracted sharply.",
        "Consumer spending weakened significantly.",
    ]

    pos_scores = scorer.score_sentences(positive)
    neg_scores = scorer.score_sentences(negative)

    pos_correct = sum(1 for s in pos_scores if s.label == "positive")
    neg_correct = sum(1 for s in neg_scores if s.label == "negative")

    assert pos_correct >= 1, (
        f"FinBERT failed on positive economic text: {[s.label for s in pos_scores]}. "
        f"Scores: {[(s.score_positive, s.score_negative, s.score_neutral) for s in pos_scores]}"
    )
    assert neg_correct >= 1, (
        f"FinBERT failed on negative economic text: {[s.label for s in neg_scores]}. "
        f"Scores: {[(s.score_positive, s.score_negative, s.score_neutral) for s in neg_scores]}"
    )
