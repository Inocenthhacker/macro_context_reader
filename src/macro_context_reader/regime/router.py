"""
Regime Router — PRD-050

Mapează regimul curent la reliability weights per strat arhitectural.
Weights-urile sunt consumate de PRD-500 BBA mappers pentru ajustarea
masei de credință în fuziunea DST.

NOTE: DEFAULT_REGIME_WEIGHTS sunt prior-uri rezonabile bazate pe logica
economică — calibrate empiric pe USMPD la activare PRD-050.
"""

from __future__ import annotations

from macro_context_reader.regime import MacroRegime

DEFAULT_REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "inflation": {
        "layer1_nlp":         0.85,
        "layer2_market":      0.75,
        "layer3_divergence":  0.80,
        "layer4_positioning": 0.60,
    },
    "growth": {
        "layer1_nlp":         0.60,
        "layer2_market":      0.80,
        "layer3_divergence":  0.70,
        "layer4_positioning": 0.60,
    },
    "financial_stability": {
        "layer1_nlp":         0.00,
        "layer2_market":      0.00,
        "layer3_divergence":  0.00,
        "layer4_positioning": 0.00,
    },
    "unknown": {
        "layer1_nlp":         0.50,
        "layer2_market":      0.50,
        "layer3_divergence":  0.50,
        "layer4_positioning": 0.50,
    },
}


def get_regime_weights(
    regime: MacroRegime,
    weights_override: dict | None = None,
) -> dict[str, float]:
    """
    Returnează reliability weights per strat pentru regimul curent.

    Args:
        regime: regimul curent din classify_regime()
        weights_override: override manual — util pentru backtesting/testing

    Returns:
        {"layer1_nlp": float, "layer2_market": float,
         "layer3_divergence": float, "layer4_positioning": float}

    TODO: implementare la activare PRD-050.
          weights_override permite calibrarea empirică fără modificarea codului.
    """
    raise NotImplementedError("TODO: PRD-050")
