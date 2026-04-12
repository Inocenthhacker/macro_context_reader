"""FinBERT-FOMC scorer — PRD-101 CC-1.

Wrapper for ZiweiChen/FinBERT-FOMC.
Label mapping verified from model config:
  0=hawkish, 1=neutral, 2=dovish

IMPORTANT: This mapping differs from FOMC-RoBERTa (0=H, 1=D, 2=N).
Always verify against model.config.id2label after loading.

Refs: PRD-101 CC-1, Kim et al. (ICAIF 2024)
"""

from __future__ import annotations

import logging
from datetime import datetime

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from macro_context_reader.rhetoric.schemas import DocumentScore, SentenceScore

logger = logging.getLogger(__name__)

MODEL_ID = "ZiweiChen/FinBERT-FOMC"


class FinBERTFOMCScorer:
    """FinBERT-FOMC sentence scorer."""

    name: str = "finbert_fomc"

    def __init__(self, batch_size: int = 32, device: str | None = None) -> None:
        self.batch_size = batch_size
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self._tokenizer = None
        self._model = None
        self._label_map: dict[int, str] = {}

    def _load_model(self) -> None:
        if self._model is not None:
            return
        logger.info("Loading %s on %s...", MODEL_ID, self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        self._model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
        self._model.to(self.device)
        self._model.eval()

        # Build label map from model config
        id2label = self._model.config.id2label
        logger.info("FinBERT-FOMC id2label: %s", id2label)

        self._label_map = {}
        for idx, raw_label in id2label.items():
            normalized = raw_label.lower().strip()
            if "hawk" in normalized:
                self._label_map[int(idx)] = "hawkish"
            elif "dov" in normalized:
                self._label_map[int(idx)] = "dovish"
            else:
                self._label_map[int(idx)] = "neutral"
        logger.info("Resolved label map: %s", self._label_map)

    def _prob_for_label(self, probs, target: str) -> float:
        """Sum probabilities across all indices mapped to target label."""
        return sum(
            float(probs[idx])
            for idx, label in self._label_map.items()
            if label == target
        )

    def score_sentences(self, sentences: list[str]) -> list[SentenceScore]:
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
                h = self._prob_for_label(prob, "hawkish")
                d = self._prob_for_label(prob, "dovish")
                n = self._prob_for_label(prob, "neutral")
                label_idx = int(prob.argmax())
                label = self._label_map[label_idx]
                results.append(SentenceScore(
                    sentence=sent,
                    sentence_idx=start + i,
                    score_hawkish=h,
                    score_dovish=d,
                    score_neutral=n,
                    label=label,
                    confidence=float(prob[label_idx]),
                ))

        return results

    def score_document_sentences(
        self, sentences: list[str], doc_date: datetime, doc_type: str
    ) -> DocumentScore:
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
