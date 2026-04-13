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


@pytest.mark.integration
@needs_torch
def test_probabilities_sum_to_one() -> None:
    """All sentence scores sum to exactly 1.0 after clamp+renormalize."""
    from macro_context_reader.economic_sentiment.scorers.finbert_sentiment import (
        FinBERTSentimentScorer,
    )

    scorer = FinBERTSentimentScorer(device="cpu", batch_size=4)
    sentences = [
        "Economic activity declined modestly in the region.",
        "Employment grew strongly across all sectors.",
        "Prices were mixed, with some categories rising and others flat.",
    ]
    results = scorer.score_sentences(sentences)
    for r in results:
        total = r.score_positive + r.score_negative + r.score_neutral
        assert abs(total - 1.0) < 1e-6, f"Probs sum to {total}, expected 1.0"


@pytest.mark.integration
@needs_torch
def test_no_probability_exceeds_one() -> None:
    """Softmax clamp ensures no individual probability > 1.0."""
    from macro_context_reader.economic_sentiment.scorers.finbert_sentiment import (
        FinBERTSentimentScorer,
    )

    scorer = FinBERTSentimentScorer(device="cpu", batch_size=4)
    sentences = [
        "Retail revenues increased slightly, while tourism activity grew at an above-average pace.",
        "Commercial real estate activity weakened further modestly.",
    ] * 5  # 10 sentences total
    results = scorer.score_sentences(sentences)
    for r in results:
        assert 0.0 <= r.score_positive <= 1.0
        assert 0.0 <= r.score_negative <= 1.0
        assert 0.0 <= r.score_neutral <= 1.0


@pytest.mark.integration
@needs_torch
def test_pydantic_validation_passes_on_realistic_beige_book_input() -> None:
    """Regression test: real Beige Book sentences that previously triggered Pydantic error."""
    from macro_context_reader.economic_sentiment.scorers.finbert_sentiment import (
        FinBERTSentimentScorer,
    )

    scorer = FinBERTSentimentScorer(device="cpu", batch_size=4)
    sentences = [
        "Federal Reserve Bank of Boston Summary of Economic Activity Economic activity declined slightly on average",
        "Labor Markets Employment was flat on average, and wage growth remained moderate.",
        "However, contacts from the Boston area noted slightly weaker sales in November",
    ]
    # If Pydantic validation fails, this raises ValidationError
    results = scorer.score_sentences(sentences)
    assert len(results) == 3
