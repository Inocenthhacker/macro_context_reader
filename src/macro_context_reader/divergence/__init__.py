"""Divergence layer (PRD-300) — composite Layer 3 integrator.

Status: PRD-300 Approved 2026-04-15. Implementation in progress (CC-1..CC-7).

Currently exported:
- decomposition: HP filter + EMD decomposition (CC-1)
- regime_conditional: regime-conditional correlation diagnostic (CC-0d, prior work)
- alignment: master alignment table for calibration (CC-1.5.5)
- targets + calibration_experiment: target selection experiment (CC-2a, v1 — kept for reference)
- targets_v2 + calibration_experiment_v2: dual-target classification (CC-2a-v2, primary)

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
from macro_context_reader.divergence.targets import (
    build_targets_table,
    compute_target_A_fedwatch_surprise,
    compute_target_D_real_rate_diff_change,
    compute_target_E_eurusd_5d_return,
    compute_target_F_eurusd_21d_return,
    fetch_eurusd_daily,
)
from macro_context_reader.divergence.calibration_experiment import (
    FEATURES_FOR_CALIBRATION,
    METHODS,
    PRE_COMMITTED_METRIC,
    PRE_COMMITTED_THRESHOLD,
    TRAIN_END_DATE,
    EqualWeightedRegressor,
    evaluate_on_validation,
    prepare_features_targets,
    run_full_experiment,
    split_train_validation,
    walk_forward_cv_evaluation,
)
from macro_context_reader.divergence.calibration_experiment import (
    run_full_experiment as run_full_experiment_v1,  # v1 alias for clarity
)

# --- v2 — dual-target classification (primary going forward)
from macro_context_reader.divergence.targets_v2 import (
    REGIME_THRESHOLD_PCT,
    REGIME_WINDOW_DAYS,
    SURPRISE_THRESHOLD_BPS,
    build_targets_v2_table,
    compute_target_regime_class,
    compute_target_surprise_class,
)
from macro_context_reader.divergence.calibration_experiment_v2 import (
    CLASSIFIERS,
    FEATURES_FOR_CLASSIFICATION,
    HIT_RATE_THRESHOLD,
    MIN_NONZERO_SIGNALS_VAL,
    EqualWeightedClassifier,
    run_full_experiment_v2,
)

__all__ = [
    "decomposition",
    "regime_conditional",
    # alignment
    "build_master_alignment_table",
    "aggregate_minutes_per_meeting",
    "get_minutes_lag_per_meeting",
    "align_real_rate_to_meeting",
    "align_cleveland_fed_to_meeting",
    "align_fedwatch_to_meeting",
    # v1 targets (kept for reference)
    "build_targets_table",
    "compute_target_A_fedwatch_surprise",
    "compute_target_D_real_rate_diff_change",
    "compute_target_E_eurusd_5d_return",
    "compute_target_F_eurusd_21d_return",
    "fetch_eurusd_daily",
    # v1 calibration experiment
    "FEATURES_FOR_CALIBRATION",
    "METHODS",
    "PRE_COMMITTED_METRIC",
    "PRE_COMMITTED_THRESHOLD",
    "TRAIN_END_DATE",
    "EqualWeightedRegressor",
    "evaluate_on_validation",
    "prepare_features_targets",
    "run_full_experiment",
    "run_full_experiment_v1",
    "split_train_validation",
    "walk_forward_cv_evaluation",
    # v2 targets
    "SURPRISE_THRESHOLD_BPS",
    "REGIME_THRESHOLD_PCT",
    "REGIME_WINDOW_DAYS",
    "build_targets_v2_table",
    "compute_target_surprise_class",
    "compute_target_regime_class",
    # v2 calibration experiment
    "FEATURES_FOR_CLASSIFICATION",
    "CLASSIFIERS",
    "HIT_RATE_THRESHOLD",
    "MIN_NONZERO_SIGNALS_VAL",
    "EqualWeightedClassifier",
    "run_full_experiment_v2",
]
