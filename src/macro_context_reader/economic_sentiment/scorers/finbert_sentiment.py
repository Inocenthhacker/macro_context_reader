"""FinBERT-FOMC applied to economic sentiment — CORRECT USE CASE — PRD-102 CC-1.

FinBERT native labels: {0: 'Neutral', 1: 'Positive', 2: 'Negative'}
Economic sentiment mapping (DIRECT, no inversion):
  Positive -> positive (economy strong, growth healthy)
  Negative -> negative (economy weak, contraction)
  Neutral  -> neutral

This mapping is the NATURAL use case for FinBERT. Contrast with FOMC
Rhetoric where Positive had to be mapped to "hawkish" (policy stance),
creating conceptual inversion for policy-change language. In economic
sentiment, no inversion needed -- sentiment = economic condition directly.

Empirical justification: FinBERT trained on Reuters TRC2 financial news,
where "manufacturing slowed" correctly scored negative (economic weakness).

Refs: PRD-102 CC-1, Kim et al. (ICAIF 2024)
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from macro_context_reader.economic_sentiment.preprocessor import preprocess_beige_book
from macro_context_reader.economic_sentiment.schemas import (
    BeigeBookDocument,
    SectionSentiment,
    SentenceSentiment,
)

logger = logging.getLogger(__name__)

MODEL_ID = "ZiweiChen/FinBERT-FOMC"

# DIRECT mapping (no inversion needed for economic sentiment):
LABEL_MAP_DIRECT: dict[str, str] = {
    "positive": "positive",
    "negative": "negative",
    "neutral": "neutral",
}


class FinBERTSentimentScorer:
    """FinBERT-FOMC for economic sentiment (Beige Book, descriptive text)."""

    name: str = "finbert_sentiment"

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
        logger.info("Loading %s on %s (economic sentiment mode)...", MODEL_ID, self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        self._model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
        self._model.to(self.device)
        self._model.eval()

        # Build label map from model config
        id2label = self._model.config.id2label
        logger.info("FinBERT id2label: %s", id2label)

        self._label_map = {}
        for idx, raw_label in id2label.items():
            normalized = raw_label.lower().strip()
            if normalized in LABEL_MAP_DIRECT:
                self._label_map[int(idx)] = LABEL_MAP_DIRECT[normalized]
            elif "pos" in normalized:
                self._label_map[int(idx)] = "positive"
            elif "neg" in normalized:
                self._label_map[int(idx)] = "negative"
            else:
                self._label_map[int(idx)] = "neutral"

        logger.info("Resolved sentiment label map: %s", self._label_map)

        mapped = set(self._label_map.values())
        if "positive" not in mapped or "negative" not in mapped:
            raise ValueError(
                f"FinBERT sentiment label mapping failed: {self._label_map}. "
                f"Model id2label was: {id2label}."
            )

    def _prob_for_label(self, probs, target: str) -> float:
        """Sum probabilities across all indices mapped to target label.

        Clamps result to [0.0, 1.0] to guard against float32→float64
        precision artifacts (softmax can produce values like 1.0+5e-8).
        """
        total = sum(
            float(probs[idx])
            for idx, label in self._label_map.items()
            if label == target
        )
        return min(max(total, 0.0), 1.0)

    def score_sentences(self, sentences: list[str]) -> list[SentenceSentiment]:
        """Score sentences for economic sentiment (positive/negative/neutral)."""
        self._load_model()
        results: list[SentenceSentiment] = []

        for start in range(0, len(sentences), self.batch_size):
            batch = sentences[start : start + self.batch_size]
            inputs = self._tokenizer(
                batch, padding=True, truncation=True, max_length=512,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                logits = self._model(**inputs).logits
                probs = torch.softmax(logits, dim=-1).cpu().numpy()

            # Clamp to [0, 1] first to handle float32 precision artifacts
            # (softmax can produce values like 1.0000000531 — 5.31e-08 above 1.0)
            probs = np.clip(probs, 0.0, 1.0)
            # Renormalize row-wise so probabilities sum to exactly 1.0
            probs = probs / probs.sum(axis=-1, keepdims=True)

            for i, (sent, prob) in enumerate(zip(batch, probs)):
                p = self._prob_for_label(prob, "positive")
                neg = self._prob_for_label(prob, "negative")
                n = self._prob_for_label(prob, "neutral")
                label_idx = int(prob.argmax())
                label = self._label_map[label_idx]
                results.append(SentenceSentiment(
                    sentence=sent,
                    sentence_idx=start + i,
                    score_positive=p,
                    score_negative=neg,
                    score_neutral=n,
                    label=label,
                    confidence=float(prob[label_idx]),
                ))

        return results

    def score_section(self, doc: BeigeBookDocument) -> SectionSentiment:
        """Score a complete Beige Book section (national or district)."""
        sentences = preprocess_beige_book(doc)
        if not sentences:
            return SectionSentiment(
                publication_date=doc.publication_date,
                section_type=doc.section_type,
                district=doc.district,
                n_sentences=0,
                n_positive=0,
                n_negative=0,
                n_neutral=0,
                sentiment_score=0.0,
                mean_confidence=0.0,
            )

        scores = self.score_sentences(sentences)

        n_pos = sum(1 for s in scores if s.label == "positive")
        n_neg = sum(1 for s in scores if s.label == "negative")
        n_neu = sum(1 for s in scores if s.label == "neutral")
        n_total = len(scores)

        sentiment_score = (n_pos - n_neg) / n_total if n_total > 0 else 0.0

        return SectionSentiment(
            publication_date=doc.publication_date,
            section_type=doc.section_type,
            district=doc.district,
            n_sentences=n_total,
            n_positive=n_pos,
            n_negative=n_neg,
            n_neutral=n_neu,
            sentiment_score=sentiment_score,
            mean_confidence=sum(s.confidence for s in scores) / n_total,
        )
