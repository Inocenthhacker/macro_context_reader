"""Tests for ensemble scoring — PRD-101 CC-1."""

from __future__ import annotations

from datetime import datetime

import pytest

from macro_context_reader.rhetoric.ensemble import (
    _compute_agreement_rate,
    _agreement_confidence,
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


class TestAgreementConfidence:
    def test_high(self) -> None:
        assert _agreement_confidence(0.75) == "HIGH"

    def test_medium(self) -> None:
        assert _agreement_confidence(0.55) == "MEDIUM"

    def test_low(self) -> None:
        assert _agreement_confidence(0.30) == "LOW"

    def test_boundary_70(self) -> None:
        assert _agreement_confidence(0.70) == "HIGH"

    def test_boundary_50(self) -> None:
        assert _agreement_confidence(0.50) == "MEDIUM"


class TestEnsembleScore:
    def test_ensemble_net_is_mean(self) -> None:
        doc = _make_doc()
        doc_scores = {
            "a": _make_doc_score("a", 0.6),
            "b": _make_doc_score("b", 0.2),
            "c": _make_doc_score("c", -0.1),
        }
        sentence_scores = {
            "a": [_make_sentence_score("hawkish")],
            "b": [_make_sentence_score("hawkish")],
            "c": [_make_sentence_score("hawkish")],
        }
        ens = compute_ensemble_score(doc, doc_scores, sentence_scores, cosine_similarity=0.8)

        expected_net = (0.6 + 0.2 + (-0.1)) / 3
        assert abs(ens.ensemble_net_score - expected_net) < 0.01
        assert abs(ens.weighted_net_score - expected_net * 0.8) < 0.01

    def test_cosine_sim_applied(self) -> None:
        doc = _make_doc()
        doc_scores = {"a": _make_doc_score("a", 0.5)}
        sentence_scores = {"a": [_make_sentence_score("hawkish")]}

        ens = compute_ensemble_score(doc, doc_scores, sentence_scores, cosine_similarity=0.3)
        assert abs(ens.weighted_net_score - 0.5 * 0.3) < 0.01

    def test_output_type(self) -> None:
        doc = _make_doc()
        doc_scores = {"a": _make_doc_score("a", 0.1)}
        sentence_scores = {"a": [_make_sentence_score("neutral")]}
        ens = compute_ensemble_score(doc, doc_scores, sentence_scores, cosine_similarity=0.9)
        assert isinstance(ens, EnsembleScore)
        assert ens.agreement_confidence in ("HIGH", "MEDIUM", "LOW")
