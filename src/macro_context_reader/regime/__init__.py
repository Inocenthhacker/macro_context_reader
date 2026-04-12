"""
Macro Regime Classifier — PRD-050 (Status: In Progress)
Layer: Infrastructure / Cross-cutting — runs BEFORE layers 1-4.

Inspired by ABCDE medical triage protocol (Thim, 2012):
identify the dominant regime before interpreting isolated symptoms.

Two classification methods run in parallel:
  A) HMM-based (hmm_classifier.py): latent states via Gaussian HMM
  B) Analog-based (analog_detector.py): Mahalanobis distance to historical periods

Consensus aggregation in consensus.py produces final classification.

Blocks: PRD-300 (Divergence), PRD-500 (DST Output)
"""

from __future__ import annotations

from enum import Enum


class MacroRegime(Enum):
    INFLATION           = "inflation"
    GROWTH              = "growth"
    FINANCIAL_STABILITY = "financial_stability"
    UNKNOWN             = "unknown"


# Lazy imports to avoid circular dependency
def __getattr__(name: str):
    if name == "get_current_regime":
        from macro_context_reader.regime.consensus import get_current_regime
        return get_current_regime
    if name == "get_regime_history":
        from macro_context_reader.regime.consensus import get_regime_history
        return get_regime_history
    if name == "classify_regime":
        from macro_context_reader.regime.classifier import classify_regime
        return classify_regime
    if name == "get_regime_weights":
        from macro_context_reader.regime.router import get_regime_weights
        return get_regime_weights
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MacroRegime",
    "classify_regime",
    "get_current_regime",
    "get_regime_history",
    "get_regime_weights",
]
