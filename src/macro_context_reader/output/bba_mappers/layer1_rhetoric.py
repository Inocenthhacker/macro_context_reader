"""BBA mapper for Layer 1 — FOMC-RoBERTa scores → Basic Belief Assignment."""

from __future__ import annotations


def map_rhetoric_to_bba(
    hawkish_score: float,
    dovish_score: float,
    neutral_score: float,
    reliability: float = 0.7,
) -> dict[str, float]:
    """
    Convertește scorul FOMC-RoBERTa în BBA pentru Stratul 1.

    Args:
        hawkish_score: scorul hawkish din FOMC-RoBERTa ∈ [0, 1]
        dovish_score: scorul dovish ∈ [0, 1]
        neutral_score: scorul neutral ∈ [0, 1]
        reliability: cât de predictiv e NLP-ul — calibrat pe USMPD

    Returns:
        dict cu mase pentru fiecare subset al frame-ului
        suma valorilor = 1.0

    TODO: reliability calibrată empiric pe backtesting USMPD.
          Masa ignoranță = 1 - suma maselor alocate direct.
    """
    raise NotImplementedError("TODO: PRD-500")
