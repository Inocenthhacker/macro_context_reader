"""Decomposition layer for PRD-300 — separates deep current from surface wave.

Two parallel methods, empirical selection in PRD-300/CC-7 backtesting:
- HP filter: parametric (Hodrick-Prescott + Ravn-Uhlig), window=63d per Gebauer ECB 2025
- EMD: data-driven (Huang et al. 1998), last IMF = deep current
"""
from .compare import compare_methods, compare_metadata
from .emd import emd_decompose
from .hp_filter import hp_decompose
from .schemas import DecompositionResult

__all__ = [
    "DecompositionResult",
    "hp_decompose",
    "emd_decompose",
    "compare_methods",
    "compare_metadata",
]
