"""BBA mapper for Layer 3 — divergence signal → Basic Belief Assignment."""

from __future__ import annotations


def map_divergence_to_bba(
    composite_divergence_score: float,
    trend_signal: float,
    changepoint_detected: bool,
    reliability: float = 0.72,
) -> dict[str, float]:
    """
    Convertește composite_divergence_score din PRD-300 în BBA.

    Args:
        composite_divergence_score: scorul agregat de divergență ∈ [-1, 1]
        trend_signal: direcția trendului structural
        changepoint_detected: True → masă mai mare pe subsetul direcțional
        reliability: calibrat pe USMPD

    Returns:
        dict cu mase pentru fiecare subset al frame-ului, suma = 1.0

    TODO: reliability TBD empiric.
    """
    raise NotImplementedError("TODO: PRD-500")
