"""Divergence layer (PRD-300) — composite Layer 3 integrator.

Status: PRD-300 Approved 2026-04-15. Implementation in progress (CC-1..CC-7).

Currently exported:
- decomposition: HP filter + EMD decomposition (CC-1)
- regime_conditional: regime-conditional correlation diagnostic (CC-0d, prior work)
- alignment: master alignment table for calibration (CC-1.5.5)

Future (placeholders):
- equilibrium: BBVA misalignment + GFCI proxy (CC-4/CC-5)
"""
from . import decomposition, regime_conditional
from macro_context_reader.divergence.alignment import (
    aggregate_minutes_per_meeting,
    align_cleveland_fed_to_meeting,
    align_fedwatch_to_meeting,
    align_real_rate_to_meeting,
    build_master_alignment_table,
    get_minutes_lag_per_meeting,
)

__all__ = [
    "decomposition",
    "regime_conditional",
    "build_master_alignment_table",
    "aggregate_minutes_per_meeting",
    "get_minutes_lag_per_meeting",
    "align_real_rate_to_meeting",
    "align_cleveland_fed_to_meeting",
    "align_fedwatch_to_meeting",
]
