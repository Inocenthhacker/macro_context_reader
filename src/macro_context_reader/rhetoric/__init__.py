"""Layer 1 — Rhetoric / NLP.

FOMC communication scoring pipeline (PRD-101):
  - Tri-model ensemble: FOMC-RoBERTa + FinBERT-FOMC + Llama 3.3 70B
  - Matched-filter weighting via Sentence-BERT cosine similarity
  - Scraper for statements, minutes, press conferences, speeches

Concept Framework (PRD-102) in concept_framework/ subpackage.

Refs: PRD-101, PRD-102
"""

import shutil
from pathlib import Path


def clear_cache(doc_type: str | None = None) -> None:
    """Delete cached raw documents for re-fetching.

    Args:
        doc_type: If specified, clear only that type ('statement', 'minutes', etc.).
                  If None, clear all cached documents.
    """
    from macro_context_reader.rhetoric.scraper import CACHE_DIR

    if doc_type:
        target = CACHE_DIR / doc_type
    else:
        target = CACHE_DIR

    if target.exists():
        shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        print(f"Cleared cache: {target}")
