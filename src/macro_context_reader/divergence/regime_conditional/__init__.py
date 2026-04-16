"""
Regime-conditional analysis subpackage.

Currently contains:
  - diagnostic: descriptive correlation/lead-lag statistics for human inspection
    (used by 12 tests + 1 notebook, classified DIAGNOSTIC by PRD-300-AUDIT/CC-2)

Planned (PRD-300/CC-3):
  - fitter: regime-conditional weight calibration for composite divergence score
  - router: runtime weight selection based on current macro regime
"""
from macro_context_reader.divergence.regime_conditional.diagnostic import *  # noqa: F401,F403
from macro_context_reader.divergence.regime_conditional.diagnostic import (  # noqa: F401
    _bootstrap_pearson_ci,
    _permutation_pvalue,
)

# Explicit re-exports for static analysis / IDE autocomplete.
__all__ = [
    "MIN_OBS_PER_REGIME",
    "RegimeCorrelation",
    "RegimeConditionalResults",
    "load_aligned_data",
    "compute_lead_lag",
    "compute_conditional_correlations",
    "_bootstrap_pearson_ci",
    "_permutation_pvalue",
]
