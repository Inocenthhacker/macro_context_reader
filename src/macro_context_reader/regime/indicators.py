"""
Triage Indicators — PRD-050
Calculează indicatorii de sistem necesari pentru clasificarea regimului macro.
Analog cu parametrii vitali în protocolul ABCDE medical.

FRED tickers folosiți:
  CPIAUCSL     → CPI Urban Consumers
  PAYEMS       → Nonfarm Payroll Employment
  UNRATE       → Unemployment Rate
  VIXCLS       → CBOE Volatility Index
  BAMLH0A0HYM2 → ICE BofA HY Credit Spread
  DGS10, DGS2  → Yield curve slope
"""

from __future__ import annotations


def fetch_triage_indicators(
    fred_api_key: str,
    as_of_date: str | None = None,
) -> dict[str, float]:
    """
    Descarcă și calculează indicatorii de triage din FRED.

    Args:
        fred_api_key: FRED API key din .env
        as_of_date: ISO date string — dacă None, folosește ultima dată disponibilă
                    IMPORTANT: nu folosi date viitoare în backtesting (look-ahead bias)

    Returns:
        {
          "cpi_yoy": float,             # CPI YoY %
          "cpi_trend_3m": float,        # pozitiv = CPI accelerează
          "nfp_3m_avg": float,          # mii locuri de muncă, rolling 3 luni
          "unemployment_rate": float,
          "unemployment_trend": float,  # pozitiv = șomaj în creștere
          "vix": float,
          "hy_credit_spread": float,    # bps
          "credit_spread_trend": float, # pozitiv = spread în lărgire
          "yield_curve_slope": float,   # DGS10 - DGS2, bps
        }

    TODO: implementare la activare PRD-050.
          Atenție la point-in-time: CPI e publicat cu ~2 săptămâni lag.
    """
    raise NotImplementedError("TODO: PRD-050")
