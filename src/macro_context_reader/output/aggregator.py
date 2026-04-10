"""
Main aggregator — orchestrează întregul pipeline DST.

Pipeline:
  4 straturi → 4 BBA mappers → regulă de combinare → Bel/Pl → position signal
"""

from __future__ import annotations

from typing import Literal

CombinationRule = Literal["dempster", "yager", "pcr5"]


def aggregate(
    rhetoric_scores: dict,
    market_scores: dict,
    divergence_scores: dict,
    positioning_scores: dict,
    rule: CombinationRule = "pcr5",
) -> dict:
    """
    Produce output final USD_bias cu interval de credibilitate.

    Args:
        rhetoric_scores: output Layer 1 (hawkish_score, dovish_score, neutral_score)
        market_scores: output Layer 2 (fedwatch_surprise, real_rate_differential)
        divergence_scores: output Layer 3 (composite_divergence_score, trend_signal, changepoint_detected)
        positioning_scores: output Layer 4 (cot_lev_percentile, tactical_score)
        rule: regula de combinare DST — ales empiric pe backtesting USMPD

    Returns:
        {
          "USD_bias": "bearish" | "hawkish" | "neutral",
          "Bel": float,           ← limita inferioară ∈ [0, 1]
          "Pl": float,            ← limita superioară ∈ [0, 1]
          "conflict_K": float,    ← conflict inter-strat ∈ [0, 1]
          "position_signal": str, ← derivat din gap Pl-Bel
          "dominant_conflict_pair": tuple,  ← care două straturi se contrazic
        }
    """
    raise NotImplementedError("TODO: PRD-500")
