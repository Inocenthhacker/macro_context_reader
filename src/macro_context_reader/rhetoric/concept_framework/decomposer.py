"""Main entry point — concept decomposition into normalized weight vector."""

from __future__ import annotations


def predict_decomposition(text: str, source: str = "beige_book") -> dict[str, float]:
    """Main output: {concept: normalized_weight}, values sum to 1.0.

    Feeds Stratul 3 alongside FOMC-RoBERTa scalar.
    """
    raise NotImplementedError("TODO: PRD-102")
