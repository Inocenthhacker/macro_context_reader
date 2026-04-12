"""Tests for ensemble scoring — PRD-101 CC-1, PRD-101/CC-1-FIX7."""

from __future__ import annotations

from datetime import datetime

import pytest

from macro_context_reader.rhetoric.ensemble import (
    ENSEMBLE_WEIGHTS,
    _compute_agreement_rate,
    _agreement_confidence_2model,
    compute_ensemble_score,
)
from macro_context_reader.rhetoric.schemas import (
    DocumentScore,
    EnsembleScore,
    FOMCDocument,
    SentenceScore,
)


def _make_sentence_score(label: str, idx: int = 0) -> SentenceScore:
    return SentenceScore(
        sentence="test",
        sentence_idx=idx,
        score_hawkish=0.8 if label == "hawkish" else 0.1,
        score_dovish=0.8 if label == "dovish" else 0.1,
        score_neutral=0.8 if label == "neutral" else 0.1,
        label=label,
        confidence=0.8,
    )


def _make_doc_score(scorer_name: str, net: float) -> DocumentScore:
    return DocumentScore(
        doc_date=datetime(2024, 1, 31),
        doc_type="statement",
        scorer_name=scorer_name,
        n_sentences=10,
        n_hawkish=5,
        n_dovish=3,
        n_neutral=2,
        net_score=net,
        mean_confidence=0.8,
    )


def _make_doc() -> FOMCDocument:
    return FOMCDocument(
        date=datetime(2024, 1, 31),
        doc_type="statement",
        url="https://example.com",
        title="Test Statement",
        raw_text="Test content",
    )


class TestAgreementRate:
    def test_perfect_agreement(self) -> None:
        scores = {
            "model_a": [_make_sentence_score("hawkish", 0), _make_sentence_score("dovish", 1)],
            "model_b": [_make_sentence_score("hawkish", 0), _make_sentence_score("dovish", 1)],
        }
        assert _compute_agreement_rate(scores) == 1.0

    def test_zero_agreement(self) -> None:
        scores = {
            "model_a": [_make_sentence_score("hawkish", 0)],
            "model_b": [_make_sentence_score("dovish", 0)],
        }
        assert _compute_agreement_rate(scores) == 0.0

    def test_partial_agreement(self) -> None:
        scores = {
            "model_a": [_make_sentence_score("hawkish", 0), _make_sentence_score("hawkish", 1)],
            "model_b": [_make_sentence_score("hawkish", 0), _make_sentence_score("dovish", 1)],
        }
        assert _compute_agreement_rate(scores) == 0.5

    def test_single_model(self) -> None:
        scores = {"model_a": [_make_sentence_score("hawkish", 0)]}
        assert _compute_agreement_rate(scores) == 1.0

    def test_empty_scores(self) -> None:
        scores = {"model_a": [], "model_b": []}
        assert _compute_agreement_rate(scores) == 0.0


class TestAgreementConfidence2Model:
    def test_both_agree_is_high(self) -> None:
        scores = {
            "a": [_make_sentence_score("hawkish", 0), _make_sentence_score("hawkish", 1)],
            "b": [_make_sentence_score("hawkish", 0), _make_sentence_score("hawkish", 1)],
        }
        assert _agreement_confidence_2model(scores) == "HIGH"

    def test_one_neutral_one_directional_is_medium(self) -> None:
        scores = {
            "a": [_make_sentence_score("hawkish", 0), _make_sentence_score("neutral", 1)],
            "b": [_make_sentence_score("hawkish", 0), _make_sentence_score("hawkish", 1)],
        }
        # 50% agree -> MEDIUM
        assert _agreement_confidence_2model(scores) == "MEDIUM"

    def test_opposite_directional_is_low(self) -> None:
        # All sentences have hawk vs dove -> LOW
        scores = {
            "a": [_make_sentence_score("hawkish", 0), _make_sentence_score("hawkish", 1),
                  _make_sentence_score("hawkish", 2)],
            "b": [_make_sentence_score("dovish", 0), _make_sentence_score("dovish", 1),
                  _make_sentence_score("dovish", 2)],
        }
        assert _agreement_confidence_2model(scores) == "LOW"

    def test_single_model_is_high(self) -> None:
        scores = {"a": [_make_sentence_score("hawkish", 0)]}
        assert _agreement_confidence_2model(scores) == "HIGH"

    def test_empty_is_low(self) -> None:
        scores = {"a": [], "b": []}
        assert _agreement_confidence_2model(scores) == "LOW"


class TestEnsembleWeights:
    def test_weights_sum_to_one(self) -> None:
        assert abs(sum(ENSEMBLE_WEIGHTS.values()) - 1.0) < 1e-9

    def test_ensemble_excludes_finbert(self) -> None:
        assert "finbert_fomc" not in ENSEMBLE_WEIGHTS

    def test_contains_expected_scorers(self) -> None:
        assert "fomc_roberta" in ENSEMBLE_WEIGHTS
        assert "llama_deepinfra" in ENSEMBLE_WEIGHTS


class TestEnsembleScore:
    def test_ensemble_net_is_weighted(self) -> None:
        """Ensemble net uses ENSEMBLE_WEIGHTS, not simple mean."""
        doc = _make_doc()
        doc_scores = {
            "fomc_roberta": _make_doc_score("fomc_roberta", 0.6),
            "llama_deepinfra": _make_doc_score("llama_deepinfra", 0.2),
        }
        sentence_scores = {
            "fomc_roberta": [_make_sentence_score("hawkish")],
            "llama_deepinfra": [_make_sentence_score("hawkish")],
        }
        ens = compute_ensemble_score(doc, doc_scores, sentence_scores, cosine_similarity=0.8)

        # Weighted: (0.6*0.6 + 0.4*0.2) / (0.6+0.4) = 0.44
        expected_net = (0.6 * 0.6 + 0.4 * 0.2) / 1.0
        assert abs(ens.ensemble_net_score - expected_net) < 0.01
        assert abs(ens.weighted_net_score - expected_net * 0.8) < 0.01

    def test_cosine_sim_applied(self) -> None:
        doc = _make_doc()
        doc_scores = {"fomc_roberta": _make_doc_score("fomc_roberta", 0.5)}
        sentence_scores = {"fomc_roberta": [_make_sentence_score("hawkish")]}

        ens = compute_ensemble_score(doc, doc_scores, sentence_scores, cosine_similarity=0.3)
        assert abs(ens.weighted_net_score - 0.5 * 0.3) < 0.01

    def test_output_type(self) -> None:
        doc = _make_doc()
        doc_scores = {"fomc_roberta": _make_doc_score("fomc_roberta", 0.1)}
        sentence_scores = {"fomc_roberta": [_make_sentence_score("neutral")]}
        ens = compute_ensemble_score(doc, doc_scores, sentence_scores, cosine_similarity=0.9)
        assert isinstance(ens, EnsembleScore)
        assert ens.agreement_confidence in ("HIGH", "MEDIUM", "LOW")

    def test_fallback_equal_weight_for_unknown_scorers(self) -> None:
        """Ad-hoc scorers not in ENSEMBLE_WEIGHTS get equal fallback weight."""
        doc = _make_doc()
        doc_scores = {
            "custom_a": _make_doc_score("custom_a", 0.4),
            "custom_b": _make_doc_score("custom_b", 0.2),
        }
        sentence_scores = {
            "custom_a": [_make_sentence_score("hawkish")],
            "custom_b": [_make_sentence_score("hawkish")],
        }
        ens = compute_ensemble_score(doc, doc_scores, sentence_scores, cosine_similarity=1.0)
        # Equal weight fallback: (0.5*0.4 + 0.5*0.2) / 1.0 = 0.3
        expected = (0.5 * 0.4 + 0.5 * 0.2) / 1.0
        assert abs(ens.ensemble_net_score - expected) < 0.01
