"""Regime Consensus — PRD-050 CC-3.

Aggregates HMM state prediction with Mahalanobis analog detection
to produce a final regime classification with confidence level.

Logic:
  - HMM provides: current_state + state probabilities
  - Analog provides: top-5 historical matches + their HMM states
  - If HMM current_state matches dominant state of top-3 analogs -> HIGH confidence
  - If mixed but majority agree -> MEDIUM confidence
  - If they diverge -> LOW confidence + conflicting_signals=True

Refs: PRD-050 CC-3
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Literal

import numpy as np
import pandas as pd

from macro_context_reader.regime.analog_detector import MahalanobisAnalogDetector
from macro_context_reader.regime.hmm_classifier import HMMRegimeClassifier
from macro_context_reader.regime.schemas import AnalogMatch, RegimeClassification

logger = logging.getLogger(__name__)


def _determine_confidence(
    hmm_state: int,
    hmm_max_prob: float,
    analog_states: list[int | None],
) -> tuple[Literal["HIGH", "MEDIUM", "LOW"], bool, str | None]:
    """Determine confidence from HMM + analog agreement.

    Returns:
        (confidence, conflicting_signals, analog_consensus_label)
    """
    valid_states = [s for s in analog_states if s is not None]

    if not valid_states:
        # No analog info — rely on HMM probability alone
        if hmm_max_prob >= 0.7:
            return "MEDIUM", False, None
        return "LOW", False, None

    counter = Counter(valid_states)
    dominant_analog_state, dominant_count = counter.most_common(1)[0]
    agreement_ratio = dominant_count / len(valid_states)

    if dominant_analog_state == hmm_state and agreement_ratio >= 0.6:
        return "HIGH", False, None
    elif dominant_analog_state == hmm_state:
        return "MEDIUM", False, None
    else:
        return "LOW", True, None


def classify_regime_consensus(
    date: pd.Timestamp,
    features: pd.DataFrame,
    hmm: HMMRegimeClassifier,
    detector: MahalanobisAnalogDetector,
    eurusd: pd.Series | None = None,
    k_analogs: int = 5,
) -> RegimeClassification:
    """Produce consensus regime classification combining HMM + Analog.

    Args:
        date: Target date for classification.
        features: Full standardized feature matrix.
        hmm: Fitted HMM classifier.
        detector: Fitted Mahalanobis detector.
        eurusd: Optional EUR/USD series for analog forward returns.
        k_analogs: Number of analogs to find.

    Returns:
        RegimeClassification with all fields populated.
    """
    # HMM prediction for target date
    if date not in features.index:
        idx = features.index.get_indexer([date], method="nearest")[0]
        date = features.index[idx]

    date_iloc = features.index.get_loc(date)
    # Predict on full sequence up to date for proper HMM state estimation
    features_to_date = features.iloc[: date_iloc + 1]
    states, probs = hmm.predict(features_to_date)

    current_state = int(states[-1])
    current_probs = probs[-1].tolist()
    hmm_label = hmm.get_label(current_state)

    # Analog detection
    analogs = detector.find_analogs(
        query_date=date,
        features=features,
        k=k_analogs,
        eurusd=eurusd,
    )

    # Enrich analogs with HMM states
    all_states_full, _ = hmm.predict(features)
    state_map = dict(zip(features.index, all_states_full))

    enriched_analogs = []
    for a in analogs:
        ts = pd.Timestamp(a.date)
        analog_state = state_map.get(ts)
        analog_label = hmm.get_label(analog_state) if analog_state is not None else None
        enriched_analogs.append(AnalogMatch(
            date=a.date,
            distance=a.distance,
            rank=a.rank,
            hmm_state=int(analog_state) if analog_state is not None else None,
            hmm_label=analog_label,
            eurusd_forward_90d_pct=a.eurusd_forward_90d_pct,
        ))

    # Consensus
    analog_hmm_states = [a.hmm_state for a in enriched_analogs[:3]]
    confidence, conflicting, analog_label = _determine_confidence(
        current_state, max(current_probs), analog_hmm_states
    )

    # Build analog consensus label from dominant state of top-3
    valid_top3 = [a for a in enriched_analogs[:3] if a.hmm_state is not None]
    if valid_top3:
        top3_counter = Counter(a.hmm_label for a in valid_top3)
        analog_consensus_label = top3_counter.most_common(1)[0][0]
    else:
        analog_consensus_label = None

    return RegimeClassification(
        date=date.to_pydatetime(),
        hmm_state=current_state,
        hmm_label=hmm_label,
        hmm_state_probs=current_probs,
        top_analogs=enriched_analogs,
        analog_consensus_label=analog_consensus_label,
        final_confidence=confidence,
        conflicting_signals=conflicting,
    )


def get_current_regime(
    features: pd.DataFrame | None = None,
    hmm: HMMRegimeClassifier | None = None,
    detector: MahalanobisAnalogDetector | None = None,
) -> RegimeClassification:
    """Entry point: classify current regime.

    If models not provided, loads from default disk paths.
    If features not provided, builds from FRED (requires FRED_API_KEY).
    """
    from macro_context_reader.regime.indicators import build_regime_features
    from macro_context_reader.regime.hmm_classifier import DEFAULT_MODEL_PATH
    from macro_context_reader.regime.analog_detector import DEFAULT_COV_PATH

    if features is None:
        features = build_regime_features()

    if hmm is None:
        hmm = HMMRegimeClassifier()
        if DEFAULT_MODEL_PATH.exists():
            hmm.load()
        else:
            logger.info("No saved HMM model found, fitting from scratch...")
            hmm.fit(features)
            hmm.save()

    if detector is None:
        detector = MahalanobisAnalogDetector()
        if DEFAULT_COV_PATH.exists():
            detector.load()
        else:
            logger.info("No saved covariance found, fitting from scratch...")
            detector.fit(features)
            detector.save()

    date = pd.Timestamp(features.index[-1])
    return classify_regime_consensus(date, features, hmm, detector)


def get_regime_history(
    features: pd.DataFrame,
    hmm: HMMRegimeClassifier,
) -> pd.DataFrame:
    """Return full regime history as DataFrame.

    Returns:
        DataFrame with columns: date, hmm_state, hmm_label, max_prob
    """
    states, probs = hmm.predict(features)
    return pd.DataFrame({
        "date": features.index,
        "hmm_state": states,
        "hmm_label": [hmm.get_label(s) for s in states],
        "max_prob": probs.max(axis=1),
    })
