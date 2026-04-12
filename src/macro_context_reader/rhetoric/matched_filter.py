"""Matched-filter weighting via Sentence-BERT — PRD-101 CC-1.

Computes cosine similarity between a new document and the most recent
Powell press conference transcript. Documents semantically similar to
Powell's presser get amplified signal weight.

Based on Djourelova et al. (Chicago Fed 2025) — validated on 481 speeches.

Model: sentence-transformers/all-MiniLM-L6-v2 (~80MB, fast).

Refs: PRD-101 CC-1
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np

from macro_context_reader.rhetoric.schemas import FOMCDocument

logger = logging.getLogger(__name__)

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
_MODEL = None


def _get_model():
    """Lazy-load sentence transformer model."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    from sentence_transformers import SentenceTransformer
    logger.info("Loading sentence transformer %s...", MODEL_ID)
    _MODEL = SentenceTransformer(MODEL_ID)
    return _MODEL


def compute_embedding(text: str) -> np.ndarray:
    """Compute normalized embedding for a text."""
    model = _get_model()
    # Truncate very long texts to first 5000 chars for efficiency
    emb = model.encode(text[:5000], normalize_embeddings=True)
    return np.asarray(emb)


def compute_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two texts."""
    emb_a = compute_embedding(text_a)
    emb_b = compute_embedding(text_b)
    sim = float(np.dot(emb_a, emb_b))
    return max(0.0, min(1.0, sim))


def get_last_powell_presser(
    docs: list[FOMCDocument], before_date: datetime
) -> FOMCDocument | None:
    """Find the most recent press conference before a given date.

    Anti-leakage: reference is always BEFORE the document being scored.
    """
    pressers = [
        d for d in docs
        if d.doc_type == "press_conference" and d.date < before_date
    ]
    if not pressers:
        return None
    return max(pressers, key=lambda d: d.date)


def compute_matched_filter_weight(
    doc: FOMCDocument,
    reference_docs: list[FOMCDocument],
) -> float:
    """Compute cosine similarity between doc and last Powell presser.

    Returns 0.5 if no reference presser exists (neutral weight).
    """
    ref = get_last_powell_presser(reference_docs, before_date=doc.date)
    if ref is None:
        logger.warning("No reference presser found before %s", doc.date)
        return 0.5
    return compute_similarity(doc.raw_text, ref.raw_text)
