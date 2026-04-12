"""FOMC-RoBERTa scorer — PRD-101 CC-1.

Wrapper for gtfintechlab/FOMC-RoBERTa (Shah, Paturi & Chava, ACL 2023).
Three-way classification: hawkish / dovish / neutral.

Refs: PRD-101 CC-1, https://huggingface.co/gtfintechlab/FOMC-RoBERTa
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from macro_context_reader.rhetoric.schemas import DocumentScore, SentenceScore

logger = logging.getLogger(__name__)

MODEL_ID = "gtfintechlab/FOMC-RoBERTa"
# FOMC-RoBERTa label mapping: 0=hawkish, 1=dovish, 2=neutral
LABEL_MAP = {0: "hawkish", 1: "dovish", 2: "neutral"}


class FOMCRobertaScorer:
    """FOMC-RoBERTa sentence scorer."""

    name: str = "fomc_roberta"

    def __init__(self, batch_size: int = 32, device: str | None = None) -> None:
        self.batch_size = batch_size
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self._tokenizer = None
        self._model = None

    def _load_model(self) -> None:
        if self._model is not None:
            return
        logger.info("Loading %s on %s...", MODEL_ID, self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        self._model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
        self._model.to(self.device)
        self._model.eval()

    def score_sentences(self, sentences: list[str]) -> list[SentenceScore]:
        """Score a batch of sentences."""
        self._load_model()
        results: list[SentenceScore] = []

        for start in range(0, len(sentences), self.batch_size):
            batch = sentences[start : start + self.batch_size]
            inputs = self._tokenizer(
                batch, padding=True, truncation=True, max_length=512,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                logits = self._model(**inputs).logits
                probs = torch.softmax(logits, dim=-1).cpu().numpy()

            for i, (sent, prob) in enumerate(zip(batch, probs)):
                # Normalize first, then clip for floating-point precision safety
                prob = prob / prob.sum()
                prob = np.clip(prob, 0.0, 1.0)
                h, d, n = float(prob[0]), float(prob[1]), float(prob[2])
                assert 0.0 <= h <= 1.0, f"h out of range: {h}"
                assert 0.0 <= d <= 1.0, f"d out of range: {d}"
                assert 0.0 <= n <= 1.0, f"n out of range: {n}"
                label_idx = int(prob.argmax())
                results.append(SentenceScore(
                    sentence=sent,
                    sentence_idx=start + i,
                    score_hawkish=h,
                    score_dovish=d,
                    score_neutral=n,
                    label=LABEL_MAP[label_idx],
                    confidence=float(prob[label_idx]),
                ))

        return results

    def score_document_sentences(
        self, sentences: list[str], doc_date: datetime, doc_type: str
    ) -> DocumentScore:
        """Score all sentences and produce aggregate DocumentScore."""
        scores = self.score_sentences(sentences)
        n_h = sum(1 for s in scores if s.label == "hawkish")
        n_d = sum(1 for s in scores if s.label == "dovish")
        n_n = sum(1 for s in scores if s.label == "neutral")
        n_total = len(scores)
        return DocumentScore(
            doc_date=doc_date,
            doc_type=doc_type,
            scorer_name=self.name,
            n_sentences=n_total,
            n_hawkish=n_h,
            n_dovish=n_d,
            n_neutral=n_n,
            net_score=(n_h - n_d) / n_total if n_total > 0 else 0.0,
            mean_confidence=sum(s.confidence for s in scores) / n_total if n_total else 0.0,
        )
