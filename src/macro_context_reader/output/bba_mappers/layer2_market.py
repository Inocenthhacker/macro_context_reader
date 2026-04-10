"""BBA mapper for Layer 2 — market pricing signals → Basic Belief Assignment."""

from __future__ import annotations


def map_market_to_bba(
    fedwatch_surprise: float,
    real_rate_differential: float,
    reliability: float = 0.75,
) -> dict[str, float]:
    """
    Convertește semnalele din Stratul 2 în BBA.

    Args:
        fedwatch_surprise: deviația față de prețuirea anterioară a piețe ∈ [-1, 1]
        real_rate_differential: US_real_rate - EUR_real_rate
        reliability: cât de predictiv e market pricing — calibrat pe USMPD

    Returns:
        dict cu mase pentru fiecare subset al frame-ului, suma = 1.0

    TODO: reliability TBD empiric.
    """
    raise NotImplementedError("TODO: PRD-500")
