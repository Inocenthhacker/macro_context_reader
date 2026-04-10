"""Position sizing signal — derivat din intervalul Bel/Pl al fuziunii DST."""

from __future__ import annotations


def compute_position_signal(
    bel: float,
    pl: float,
) -> dict:
    """
    Derivă semnalul de position sizing din intervalul [Bel, Pl].

    Regula (calibrată empiric — thresholds TBD pe backtesting):
      gap = Pl - Bel
      gap < 0.15   → "full"    — semnal clar, size normal
      0.15–0.35    → "reduced" — semnal moderat, size 50%
      > 0.35       → "none"    — conflict ridicat, nu intri

    Args:
        bel: limita inferioară de credibilitate ∈ [0, 1]
        pl: limita superioară de plauzibilitate ∈ [0, 1]

    Returns:
        {"signal": "full"|"reduced"|"none", "gap": float, "confidence": float}

    TODO: thresholds calibrate pe backtesting USMPD.
          Confidence = 1 - gap (normalizat) ca proxy simplu.
    """
    raise NotImplementedError("TODO: PRD-500")
