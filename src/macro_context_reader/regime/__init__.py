"""
Macro Regime Classifier — PRD-050 (Status: Draft)
Layer: Infrastructure / Cross-cutting — rulează ÎNAINTEA straturilor 1-4.

Inspirat din protocolul ABCDE de triage medical (Thim, 2012):
identifici sistemul dominant înainte de a interpreta simptomele izolate.

Trei regimuri: INFLATION | GROWTH | FINANCIAL_STABILITY
Priority order: FINANCIAL_STABILITY > INFLATION > GROWTH

Blochează: PRD-300 (Divergence), PRD-500 (DST Output)
DO NOT implement until PRD-050 is Approved.
"""

from __future__ import annotations

from enum import Enum


class MacroRegime(Enum):
    INFLATION           = "inflation"
    GROWTH              = "growth"
    FINANCIAL_STABILITY = "financial_stability"
    UNKNOWN             = "unknown"


# Lazy imports to avoid circular dependency (classifier/router import MacroRegime from here)
def __getattr__(name: str):
    if name == "classify_regime":
        from macro_context_reader.regime.classifier import classify_regime
        return classify_regime
    if name == "get_current_regime":
        from macro_context_reader.regime.classifier import get_current_regime
        return get_current_regime
    if name == "get_regime_weights":
        from macro_context_reader.regime.router import get_regime_weights
        return get_regime_weights
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MacroRegime",
    "classify_regime",
    "get_current_regime",
    "get_regime_weights",
]
