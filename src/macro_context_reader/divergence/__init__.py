"""Divergence layer (PRD-300) — composite Layer 3 integrator.

Status: PRD-300 Approved 2026-04-15. Implementation in progress (CC-1..CC-7).

Currently exported:
- decomposition: HP filter + EMD decomposition (CC-1)
- regime_conditional: regime-conditional correlation diagnostic (CC-0d, prior work)

Future (placeholders):
- equilibrium: BBVA misalignment + GFCI proxy (CC-4/CC-5)
"""
from . import decomposition, regime_conditional

__all__ = ["decomposition", "regime_conditional"]
