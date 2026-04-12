"""Tests for rhetoric pipeline — PRD-101 CC-1.

Tests orchestration logic with fully mocked scorers and scraper.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from macro_context_reader.rhetoric.schemas import (
    DocumentScore,
    EnsembleScore,
    FOMCDocument,
    SentenceScore,
)


def _fake_doc(date_str: str = "2024-06-15", doc_type: str = "statement") -> FOMCDocument:
    return FOMCDocument(
        date=datetime.fromisoformat(date_str),
        doc_type=doc_type,
        url=f"https://fed.gov/{doc_type}/{date_str}",
        title=f"Test {doc_type} {date_str}",
        raw_text="The Committee decided to maintain rates. Inflation remains elevated. Growth is moderate.",
    )


def _fake_sentence_score(label: str = "hawkish", idx: int = 0) -> SentenceScore:
    return SentenceScore(
        sentence="test", sentence_idx=idx,
        score_hawkish=0.8 if label == "hawkish" else 0.1,
        score_dovish=0.8 if label == "dovish" else 0.1,
        score_neutral=0.8 if label == "neutral" else 0.1,
        label=label, confidence=0.8,
    )


def _fake_doc_score(name: str = "mock_scorer") -> DocumentScore:
    return DocumentScore(
        doc_date=datetime(2024, 6, 15), doc_type="statement",
        scorer_name=name, n_sentences=3, n_hawkish=1, n_dovish=1, n_neutral=1,
        net_score=0.0, mean_confidence=0.8,
    )


class TestPipelineOrchestration:
    def test_pipeline_produces_dataframe(self, tmp_path) -> None:
        from macro_context_reader.rhetoric import pipeline as pipe_mod

        doc = _fake_doc()
        fake_fetcher = MagicMock(return_value=[doc])

        fake_scorer = MagicMock()
        fake_scorer.name = "mock"
        fake_scorer.score_sentences.return_value = [
            _fake_sentence_score("hawkish", 0),
            _fake_sentence_score("dovish", 1),
            _fake_sentence_score("neutral", 2),
        ]
        fake_scorer.score_document_sentences.return_value = _fake_doc_score("mock")

        output = tmp_path / "test_scores.parquet"
        with patch.dict(pipe_mod.FETCHER_MAP, {"statement": fake_fetcher}), \
             patch.object(pipe_mod, "_load_scorers", return_value={"mock": fake_scorer}), \
             patch.object(pipe_mod, "preprocess_document", return_value=["S1.", "S2.", "S3."]), \
             patch.object(pipe_mod, "compute_matched_filter_weight", return_value=0.7):
            df = pipe_mod.run_full_pipeline(
                start_year=2024, doc_types=["statement"], output_path=output,
            )

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "ensemble_net" in df.columns
        assert "weighted_score" in df.columns

    def test_incremental_skips_existing(self, tmp_path) -> None:
        from macro_context_reader.rhetoric import pipeline as pipe_mod

        doc = _fake_doc()

        def make_scorer():
            s = MagicMock()
            s.name = "mock"
            s.score_sentences.return_value = [_fake_sentence_score()]
            s.score_document_sentences.return_value = _fake_doc_score()
            return s

        output = tmp_path / "scores.parquet"

        scorer1 = make_scorer()
        with patch.dict(pipe_mod.FETCHER_MAP, {"statement": MagicMock(return_value=[doc])}), \
             patch.object(pipe_mod, "_load_scorers", return_value={"mock": scorer1}), \
             patch.object(pipe_mod, "preprocess_document", return_value=["Sent."]), \
             patch.object(pipe_mod, "compute_matched_filter_weight", return_value=0.7):
            df1 = pipe_mod.run_full_pipeline(
                start_year=2024, doc_types=["statement"], output_path=output,
            )
        assert len(df1) == 1

        # Second run — doc already in parquet, scorer should NOT be called
        scorer2 = make_scorer()
        with patch.dict(pipe_mod.FETCHER_MAP, {"statement": MagicMock(return_value=[doc])}), \
             patch.object(pipe_mod, "_load_scorers", return_value={"mock": scorer2}), \
             patch.object(pipe_mod, "preprocess_document", return_value=["Sent."]), \
             patch.object(pipe_mod, "compute_matched_filter_weight", return_value=0.7):
            df2 = pipe_mod.run_full_pipeline(
                start_year=2024, doc_types=["statement"], output_path=output,
            )
        assert len(df2) == 1
        scorer2.score_sentences.assert_not_called()

    def test_empty_docs_returns_empty_df(self, tmp_path) -> None:
        from macro_context_reader.rhetoric import pipeline as pipe_mod

        with patch.dict(pipe_mod.FETCHER_MAP, {"statement": MagicMock(return_value=[])}), \
             patch.object(pipe_mod, "_load_scorers", return_value={}):
            df = pipe_mod.run_full_pipeline(
                start_year=2024, doc_types=["statement"],
                output_path=tmp_path / "empty.parquet",
            )
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
