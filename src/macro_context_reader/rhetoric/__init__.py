"""Layer 1 — Rhetoric / NLP.

FOMC communication scoring pipeline (PRD-101):
  - Tri-model ensemble: FOMC-RoBERTa + FinBERT-FOMC + Llama 3.3 70B
  - Matched-filter weighting via Sentence-BERT cosine similarity
  - Scraper for statements, minutes, press conferences, speeches

Concept Framework (PRD-102) in concept_framework/ subpackage.

Refs: PRD-101, PRD-102
"""
