"""Tests for Economic Sentiment pipeline — PRD-102 CC-1."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from macro_context_reader.economic_sentiment.schemas import (
    BeigeBookDocument,
    SectionSentiment,
    SentenceSentiment,
)


def _fake_doc(
    date_str: str = "2024-01-15",
    section_type: str = "national_summary",
    district: str | None = None,
) -> BeigeBookDocument:
    return BeigeBookDocument(
        publication_date=datetime.fromisoformat(date_str),
        section_type=section_type,
        district=district,
        url=f"https://fed.gov/beigebook/{date_str}",
        raw_text="Economic activity expanded moderately across all districts. Consumer spending was strong overall.",
    )


def _fake_section_sentiment(
    date_str: str = "2024-01-15",
    section_type: str = "national_summary",
    district: str | None = None,
    score: float = 0.3,
) -> SectionSentiment:
    return SectionSentiment(
        publication_date=datetime.fromisoformat(date_str),
        section_type=section_type,
        district=district,
        n_sentences=10,
        n_positive=6,
        n_negative=3,
        n_neutral=1,
        sentiment_score=score,
        mean_confidence=0.8,
    )


class TestPipelineOrchestration:
    def test_pipeline_produces_dataframe(self, tmp_path) -> None:
        from macro_context_reader.economic_sentiment import pipeline as pipe_mod

        national = _fake_doc("2024-01-15", "national_summary")
        boston = _fake_doc("2024-01-15", "district_report", "Boston")
        ny = _fake_doc("2024-01-15", "district_report", "New York")

        fake_scorer = MagicMock()
        fake_scorer.score_section.side_effect = [
            _fake_section_sentiment("2024-01-15", "national_summary", None, 0.3),
            _fake_section_sentiment("2024-01-15", "district_report", "Boston", 0.2),
            _fake_section_sentiment("2024-01-15", "district_report", "New York", 0.4),
        ]

        output = tmp_path / "test_sentiment.parquet"
        with patch.object(pipe_mod, "fetch_all_beige_books", return_value=[national, boston, ny]), \
             patch.object(pipe_mod, "FinBERTSentimentScorer", return_value=fake_scorer):
            df = pipe_mod.run_full_pipeline(
                start_year=2024, output_path=output,
            )

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "national_score" in df.columns
        assert "district_weighted_score" in df.columns
        assert "national_district_divergence" in df.columns
        assert "Boston_score" in df.columns
        assert "New_York_score" in df.columns

    def test_incremental_skips_existing(self, tmp_path) -> None:
        from macro_context_reader.economic_sentiment import pipeline as pipe_mod

        national = _fake_doc("2024-01-15", "national_summary")
        boston = _fake_doc("2024-01-15", "district_report", "Boston")

        output = tmp_path / "scores.parquet"

        # First run
        fake_scorer1 = MagicMock()
        fake_scorer1.score_section.side_effect = [
            _fake_section_sentiment("2024-01-15", "national_summary", None, 0.3),
            _fake_section_sentiment("2024-01-15", "district_report", "Boston", 0.2),
        ]
        with patch.object(pipe_mod, "fetch_all_beige_books", return_value=[national, boston]), \
             patch.object(pipe_mod, "FinBERTSentimentScorer", return_value=fake_scorer1):
            df1 = pipe_mod.run_full_pipeline(start_year=2024, output_path=output)
        assert len(df1) == 1

        # Second run — scorer should NOT be called
        fake_scorer2 = MagicMock()
        with patch.object(pipe_mod, "fetch_all_beige_books", return_value=[national, boston]), \
             patch.object(pipe_mod, "FinBERTSentimentScorer", return_value=fake_scorer2):
            df2 = pipe_mod.run_full_pipeline(start_year=2024, output_path=output)
        assert len(df2) == 1
        fake_scorer2.score_section.assert_not_called()

    def test_empty_docs_returns_empty_df(self, tmp_path) -> None:
        from macro_context_reader.economic_sentiment import pipeline as pipe_mod

        output = tmp_path / "empty.parquet"
        with patch.object(pipe_mod, "fetch_all_beige_books", return_value=[]), \
             patch.object(pipe_mod, "FinBERTSentimentScorer", return_value=MagicMock()):
            df = pipe_mod.run_full_pipeline(start_year=2024, output_path=output)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_pipeline_handles_scoring_failure(self, tmp_path) -> None:
        from macro_context_reader.economic_sentiment import pipeline as pipe_mod

        national = _fake_doc("2024-01-15", "national_summary")

        fake_scorer = MagicMock()
        fake_scorer.score_section.side_effect = RuntimeError("Model failed")

        output = tmp_path / "fail.parquet"
        with patch.object(pipe_mod, "fetch_all_beige_books", return_value=[national]), \
             patch.object(pipe_mod, "FinBERTSentimentScorer", return_value=fake_scorer):
            df = pipe_mod.run_full_pipeline(start_year=2024, output_path=output)

        # Should handle gracefully — empty result
        assert isinstance(df, pd.DataFrame)

    def test_multiple_publications(self, tmp_path) -> None:
        from macro_context_reader.economic_sentiment import pipeline as pipe_mod

        docs = [
            _fake_doc("2024-01-15", "national_summary"),
            _fake_doc("2024-01-15", "district_report", "Boston"),
            _fake_doc("2024-03-15", "national_summary"),
            _fake_doc("2024-03-15", "district_report", "New York"),
        ]

        fake_scorer = MagicMock()
        fake_scorer.score_section.side_effect = [
            _fake_section_sentiment("2024-01-15", "national_summary", None, 0.3),
            _fake_section_sentiment("2024-01-15", "district_report", "Boston", 0.2),
            _fake_section_sentiment("2024-03-15", "national_summary", None, -0.1),
            _fake_section_sentiment("2024-03-15", "district_report", "New York", 0.1),
        ]

        output = tmp_path / "multi.parquet"
        with patch.object(pipe_mod, "fetch_all_beige_books", return_value=docs), \
             patch.object(pipe_mod, "FinBERTSentimentScorer", return_value=fake_scorer):
            df = pipe_mod.run_full_pipeline(start_year=2024, output_path=output)

        assert len(df) == 2
        assert df.iloc[0]["publication_date"] < df.iloc[1]["publication_date"]
