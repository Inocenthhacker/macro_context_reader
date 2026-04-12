"""Tests for rhetoric scorers — PRD-101 CC-1.

All tests mock heavy dependencies (transformers, torch, openai).
Scorer module imports are guarded — tests skip if torch not installed.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from macro_context_reader.rhetoric.schemas import SentenceScore, DocumentScore

# Check if torch is available (not installed in minimal venv)
torch_available = False
try:
    import torch
    torch_available = True
except ImportError:
    pass

needs_torch = pytest.mark.skipif(not torch_available, reason="torch not installed")


# ---------------------------------------------------------------------------
# FOMC-RoBERTa tests
# ---------------------------------------------------------------------------

class TestFOMCRoberta:
    @needs_torch
    def test_scorer_name(self) -> None:
        from macro_context_reader.rhetoric.scorers.fomc_roberta import FOMCRobertaScorer
        scorer = FOMCRobertaScorer(device="cpu")
        assert scorer.name == "fomc_roberta"

    @needs_torch
    def test_document_score_net_range(self) -> None:
        from macro_context_reader.rhetoric.scorers.fomc_roberta import FOMCRobertaScorer
        scorer = FOMCRobertaScorer(device="cpu")

        # Mock score_sentences to return known values
        scorer.score_sentences = MagicMock(return_value=[
            SentenceScore(sentence="a", sentence_idx=0, score_hawkish=0.8,
                         score_dovish=0.1, score_neutral=0.1, label="hawkish", confidence=0.8),
            SentenceScore(sentence="b", sentence_idx=1, score_hawkish=0.1,
                         score_dovish=0.7, score_neutral=0.2, label="dovish", confidence=0.7),
            SentenceScore(sentence="c", sentence_idx=2, score_hawkish=0.1,
                         score_dovish=0.1, score_neutral=0.8, label="neutral", confidence=0.8),
        ])

        ds = scorer.score_document_sentences(
            ["a", "b", "c"], datetime(2024, 1, 31), "statement"
        )

        assert isinstance(ds, DocumentScore)
        assert ds.n_hawkish == 1
        assert ds.n_dovish == 1
        assert ds.n_neutral == 1
        assert -1.0 <= ds.net_score <= 1.0
        assert abs(ds.net_score - 0.0) < 0.01  # (1-1)/3 = 0


# ---------------------------------------------------------------------------
# Llama DeepInfra tests
# ---------------------------------------------------------------------------

class TestLlamaDeepInfra:
    def test_budget_tracker_limits(self) -> None:
        from macro_context_reader.rhetoric.scorers.llama_deepinfra import (
            BudgetTracker, BudgetExceededError,
        )
        bt = BudgetTracker(max_usd=0.001)
        # Large token count to exceed tiny budget
        with pytest.raises(BudgetExceededError):
            bt.record(100_000_000, 100_000_000)

    def test_budget_tracker_can_proceed(self) -> None:
        from macro_context_reader.rhetoric.scorers.llama_deepinfra import BudgetTracker
        bt = BudgetTracker(max_usd=5.0)
        assert bt.can_proceed(1000) is True
        bt.spent_usd = 4.5  # near limit
        assert bt.can_proceed(1_000_000) is False

    def test_classify_uses_cache(self, tmp_path) -> None:
        from macro_context_reader.rhetoric.scorers.llama_deepinfra import LlamaDeepInfraScorer
        scorer = LlamaDeepInfraScorer()

        with patch.object(scorer, "_cache_key") as mock_ck:
            cache_file = tmp_path / "test_cache.json"
            cache_file.write_text(json.dumps({"label": "HAWKISH", "confidence": 0.9}))
            mock_ck.return_value = cache_file
            result = scorer._classify_single("test sentence")

        assert result["label"] == "HAWKISH"
        assert result["confidence"] == 0.9

    def test_scorer_name(self) -> None:
        from macro_context_reader.rhetoric.scorers.llama_deepinfra import LlamaDeepInfraScorer
        scorer = LlamaDeepInfraScorer()
        assert scorer.name == "llama_deepinfra"

    def test_score_sentences_from_cache(self, tmp_path) -> None:
        from macro_context_reader.rhetoric.scorers.llama_deepinfra import LlamaDeepInfraScorer
        scorer = LlamaDeepInfraScorer()

        def fake_classify(sent):
            return {"label": "HAWKISH", "confidence": 0.85}

        scorer._classify_single = fake_classify
        results = scorer.score_sentences(["The Fed will raise rates."])
        assert len(results) == 1
        assert results[0].label == "hawkish"
        assert results[0].confidence == 0.85


# ---------------------------------------------------------------------------
# FinBERT-FOMC tests
# ---------------------------------------------------------------------------

class TestFinBERTFOMC:
    @needs_torch
    def test_scorer_name(self) -> None:
        from macro_context_reader.rhetoric.scorers.finbert_fomc import FinBERTFOMCScorer
        scorer = FinBERTFOMCScorer(device="cpu")
        assert scorer.name == "finbert_fomc"
