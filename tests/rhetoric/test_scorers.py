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

    @needs_torch
    def test_label_map_covers_positive_negative(self) -> None:
        """FINBERT_FOMC_LABEL_MAP must map Positive->hawkish, Negative->dovish."""
        from macro_context_reader.rhetoric.scorers.finbert_fomc import FINBERT_FOMC_LABEL_MAP
        assert FINBERT_FOMC_LABEL_MAP["positive"] == "hawkish"
        assert FINBERT_FOMC_LABEL_MAP["negative"] == "dovish"
        assert FINBERT_FOMC_LABEL_MAP["neutral"] == "neutral"


# ---------------------------------------------------------------------------
# Integration tests — require real models / API keys
# ---------------------------------------------------------------------------

HAWKISH_SENTENCE = "The Committee will continue raising rates to combat inflation."


class TestSoftmaxPrecision:
    def test_no_pydantic_error_on_edge_probs(self) -> None:
        """Regression: softmax output ~1.0000001 must not break Pydantic validation."""
        # Simulate what happens after np.clip + normalize
        import numpy as np
        raw = np.array([1.0000001, -0.0000001, 0.0])
        clamped = np.clip(raw, 0.0, 1.0)
        normalized = clamped / clamped.sum()

        # This must not raise ValidationError
        score = SentenceScore(
            sentence="test",
            sentence_idx=0,
            score_hawkish=float(normalized[0]),
            score_dovish=float(normalized[1]),
            score_neutral=float(normalized[2]),
            label="hawkish",
            confidence=float(normalized[0]),
        )
        assert score.score_hawkish <= 1.0
        assert score.score_dovish >= 0.0

    def test_all_zero_logits_safe(self) -> None:
        """Edge case: all-zero logits produce uniform 1/3 after softmax."""
        import numpy as np
        raw = np.array([0.333333, 0.333333, 0.333334])
        clamped = np.clip(raw, 0.0, 1.0)
        normalized = clamped / clamped.sum()

        score = SentenceScore(
            sentence="test",
            sentence_idx=0,
            score_hawkish=float(normalized[0]),
            score_dovish=float(normalized[1]),
            score_neutral=float(normalized[2]),
            label="neutral",
            confidence=float(normalized[2]),
        )
        assert abs(score.score_hawkish + score.score_dovish + score.score_neutral - 1.0) < 1e-6


@pytest.mark.integration
@needs_torch
def test_fomc_roberta_real_inference() -> None:
    """Load real FOMC-RoBERTa and verify hawkish sentence is classified correctly."""
    from macro_context_reader.rhetoric.scorers.fomc_roberta import FOMCRobertaScorer

    scorer = FOMCRobertaScorer(device="cpu", batch_size=1)
    results = scorer.score_sentences([HAWKISH_SENTENCE])

    assert len(results) == 1
    r = results[0]
    assert r.label == "hawkish", (
        f"Expected 'hawkish', got '{r.label}' "
        f"(H={r.score_hawkish:.3f}, D={r.score_dovish:.3f}, N={r.score_neutral:.3f})"
    )
    assert r.score_hawkish > 0.5, f"Hawkish prob too low: {r.score_hawkish:.3f}"


@pytest.mark.integration
@needs_torch
def test_finbert_fomc_real_inference() -> None:
    """Load real FinBERT-FOMC and verify label mapping is correct.

    Critical: FinBERT-FOMC uses a different id2label than FOMC-RoBERTa.
    This test catches mapping errors that would silently invert signals.
    """
    from macro_context_reader.rhetoric.scorers.finbert_fomc import FinBERTFOMCScorer

    scorer = FinBERTFOMCScorer(device="cpu", batch_size=1)
    results = scorer.score_sentences([HAWKISH_SENTENCE])

    assert len(results) == 1
    r = results[0]
    assert r.label == "hawkish", (
        f"Expected 'hawkish', got '{r.label}' — "
        f"label mapping may be inverted. "
        f"(H={r.score_hawkish:.3f}, D={r.score_dovish:.3f}, N={r.score_neutral:.3f}). "
        f"Check model.config.id2label against _label_map in finbert_fomc.py."
    )
    assert r.score_hawkish > r.score_dovish, "Hawkish prob should exceed dovish"


@pytest.mark.integration
def test_llama_deepinfra_real_call() -> None:
    """Make one real DeepInfra API call and verify JSON structure + cost.

    Requires DEEPINFRA_API_KEY in environment.
    """
    import os
    if not os.environ.get("DEEPINFRA_API_KEY"):
        pytest.skip("DEEPINFRA_API_KEY not set")

    from macro_context_reader.rhetoric.scorers.llama_deepinfra import LlamaDeepInfraScorer

    scorer = LlamaDeepInfraScorer(max_budget_usd=0.10)
    results = scorer.score_sentences([HAWKISH_SENTENCE])

    assert len(results) == 1
    r = results[0]
    assert r.label in ("hawkish", "dovish", "neutral"), f"Unexpected label: {r.label}"
    assert 0.0 <= r.confidence <= 1.0
    # Cost for 1 sentence should be negligible
    assert scorer.budget.spent_usd < 0.01, (
        f"Cost too high for 1 sentence: ${scorer.budget.spent_usd:.4f}"
    )


@pytest.mark.integration
@needs_torch
def test_fomc_roberta_label_mapping_empirical() -> None:
    """Validate that LABEL_MAP is correct per Shah et al. ACL 2023.

    Tests 4 clear cases:
    - Hawkish: 'The Committee will raise rates to combat inflation.' -> hawkish
    - Dovish: 'The Committee will cut rates to support employment.' -> dovish
    - Hawkish forward: 'Ongoing rate increases will be appropriate.' -> hawkish
    - Dovish risk: 'Downside risks to employment have increased.' -> dovish
    """
    from macro_context_reader.rhetoric.scorers.fomc_roberta import FOMCRobertaScorer

    scorer = FOMCRobertaScorer(device="cpu", batch_size=4)

    test_cases = [
        ("The Committee will continue to raise rates to combat inflation.", "hawkish"),
        ("The Committee will cut rates to support employment.", "dovish"),
        ("The Committee anticipates that ongoing increases in the target range will be appropriate.", "hawkish"),
        ("The Committee judges that downside risks to employment have increased.", "dovish"),
    ]

    sentences = [tc[0] for tc in test_cases]
    expected = [tc[1] for tc in test_cases]

    scores = scorer.score_sentences(sentences)
    actual = [s.label for s in scores]

    correct = sum(1 for a, e in zip(actual, expected) if a == e)
    assert correct >= 3, (
        f"FOMC-RoBERTa mapping fails empirical validation: {correct}/4 correct. "
        f"Expected {expected}, got {actual}. "
        f"This indicates LABEL_MAP is incorrect."
    )


@pytest.mark.integration
@needs_torch
def test_finbert_fomc_label_mapping_empirical() -> None:
    """Validate Positive->hawkish, Negative->dovish on known sentences.

    Must get at least 1/2 correct per class — catches silent all-neutral bug.
    """
    from macro_context_reader.rhetoric.scorers.finbert_fomc import FinBERTFOMCScorer

    scorer = FinBERTFOMCScorer(device="cpu", batch_size=4)

    hawkish_sentences = [
        "The Committee will continue to raise rates to combat inflation.",
        "Inflation remains elevated and requires further tightening.",
    ]
    dovish_sentences = [
        "The Committee will cut rates to support employment.",
        "Economic growth has weakened substantially, warranting accommodation.",
    ]

    h_scores = scorer.score_sentences(hawkish_sentences)
    d_scores = scorer.score_sentences(dovish_sentences)

    h_correct = sum(1 for s in h_scores if s.label == "hawkish")
    d_correct = sum(1 for s in d_scores if s.label == "dovish")

    assert h_correct >= 1, (
        f"FinBERT failed on hawkish sentences: {[s.label for s in h_scores]}. "
        f"Scores: {[(s.score_hawkish, s.score_dovish, s.score_neutral) for s in h_scores]}"
    )
    assert d_correct >= 1, (
        f"FinBERT failed on dovish sentences: {[s.label for s in d_scores]}. "
        f"Scores: {[(s.score_hawkish, s.score_dovish, s.score_neutral) for s in d_scores]}"
    )
