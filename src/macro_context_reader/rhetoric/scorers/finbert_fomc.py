"""FinBERT-FOMC scorer — PRD-101 CC-1.

NOTE: NOT USED in FOMC Rhetoric Ensemble (removed 2026-04-12).
Empirical accuracy on FOMC hawkish/dovish classification: 20% (1/5).
Structural limitation: trained on general financial sentiment,
inverts on policy-change language where "eased" sentiment !=
"dovish" policy stance (e.g., "inflation has eased" is hawkish
context for Fed even though sentiment is negative).

Reused in: macro_context_reader.economic_sentiment module for
Beige Book and descriptive economic text analysis, where sentiment
correctly maps to economic conditions (not policy stance).

Wrapper for ZiweiChen/FinBERT-FOMC.

Label mapping (FinBERT-FOMC ZiweiChen):
  Model native: {0: 'Neutral', 1: 'Positive', 2: 'Negative'}
  Mapped to:    {0: 'neutral', 1: 'hawkish',  2: 'dovish'}

  Rationale: In monetary policy context, Positive economic sentiment
  (strong growth, healthy labor market) historically justifies tightening
  (hawkish stance), while Negative sentiment (weak growth, labor concerns)
  justifies easing (dovish stance). This interpretation is validated
  empirically via integration test on known hawkish/dovish sentences.

Refs: PRD-101 CC-1, Kim et al. (ICAIF 2024),
      debug_llama_disagreement.py (2026-04-12)
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from macro_context_reader.rhetoric.schemas import DocumentScore, SentenceScore

logger = logging.getLogger(__name__)

MODEL_ID = "ZiweiChen/FinBERT-FOMC"

# Mapping from FinBERT-FOMC native labels to monetary policy stance.
# Positive economic sentiment -> justifies tightening (hawkish)
# Negative economic sentiment -> justifies easing (dovish)
FINBERT_FOMC_LABEL_MAP = {
    "positive": "hawkish",
    "negative": "dovish",
    "neutral": "neutral",
}


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
            if normalized in FINBERT_FOMC_LABEL_MAP:
                self._label_map[int(idx)] = FINBERT_FOMC_LABEL_MAP[normalized]
            elif "hawk" in normalized:
                self._label_map[int(idx)] = "hawkish"
            elif "dov" in normalized:
                self._label_map[int(idx)] = "dovish"
            elif "pos" in normalized:
                self._label_map[int(idx)] = "hawkish"
            elif "neg" in normalized:
                self._label_map[int(idx)] = "dovish"
            else:
                self._label_map[int(idx)] = "neutral"

        logger.info("Resolved label map: %s", self._label_map)

        # Fail fast if mapping doesn't produce all three classes
        mapped_labels = set(self._label_map.values())
        if "hawkish" not in mapped_labels or "dovish" not in mapped_labels:
            raise ValueError(
                f"FinBERT label mapping failed: {self._label_map}. "
                f"Model id2label was: {id2label}. "
                "Cannot proceed — all sentences would be classified as neutral."
            )

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
                # Normalize first, then clip for floating-point precision safety
                prob = prob / prob.sum()
                prob = np.clip(prob, 0.0, 1.0)
                h = self._prob_for_label(prob, "hawkish")
                d = self._prob_for_label(prob, "dovish")
                n = self._prob_for_label(prob, "neutral")
                assert 0.0 <= h <= 1.0, f"h out of range: {h}"
                assert 0.0 <= d <= 1.0, f"d out of range: {d}"
                assert 0.0 <= n <= 1.0, f"n out of range: {n}"
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
