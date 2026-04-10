"""
Standalone Calculator — PRD-051

Calculează regimul macro direct din FRED, fără a depinde de PRD-050.
Duplicare intenționată a logicii din PRD-050/classifier.py:
INDEPENDENCE > DRY pentru un modul standalone.

Folosit în mod STANDALONE când PRD-050 nu e instalat/disponibil.
"""

from __future__ import annotations


def calculate_regime_standalone(
    fred_api_key: str,
    config_path: str = "config/regime_thresholds.yaml",
) -> dict:
    """
    Calculează regimul direct din FRED.

    Output identic cu get_current_regime() din PRD-050 pentru compatibilitate.

    Args:
        fred_api_key: FRED API key din .env
        config_path: path către YAML cu thresholds (același ca PRD-050)

    Returns:
        {
          "regime": str,         # "inflation"|"growth"|"financial_stability"
          "confidence": float,
          "indicators": dict,    # valorile brute ale indicatorilor
          "triggered_rules": list[str],
          "as_of_date": str,
          "mode": "standalone"
        }

    TODO: PRD-051 — implementare la activare.
    """
    raise NotImplementedError("TODO: PRD-051")
