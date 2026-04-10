"""
Regime Classifier — PRD-050

Clasifică regimul macro dominant pe baza indicatorilor de triage.
Regulile sunt parametrizate în config/regime_thresholds.yaml — nu hardcodate.
Priority order: FINANCIAL_STABILITY > INFLATION > GROWTH

Tranziție de regim: confirmare pe N zile consecutive (N în YAML)
pentru a evita oscilații false.
"""

from __future__ import annotations

from macro_context_reader.regime import MacroRegime


def classify_regime(
    indicators: dict[str, float],
    config_path: str = "config/regime_thresholds.yaml",
) -> dict:
    """
    Clasifică regimul macro curent.

    Args:
        indicators: output din fetch_triage_indicators()
        config_path: path către YAML cu thresholds

    Returns:
        {
          "regime": MacroRegime,
          "confidence": float,          # ∈ [0, 1]
          "triggered_rules": list[str], # care reguli au fost îndeplinite
          "as_of_date": str,
        }

    TODO: implementare la activare PRD-050.
          Backtesting obligatoriu pe 2015–2025 înainte de producție:
          2021-2023 = INFLATION, 2019 = GROWTH, 2008/2020 = FINANCIAL_STABILITY
    """
    raise NotImplementedError("TODO: PRD-050")


def get_current_regime(
    fred_api_key: str,
    config_path: str = "config/regime_thresholds.yaml",
) -> dict:
    """
    Entry point principal: fetch indicators → classify → return regime.
    Consumat de PRD-300 (Divergence) și PRD-500 (DST Output).

    TODO: implementare la activare PRD-050.
    """
    raise NotImplementedError("TODO: PRD-050")
