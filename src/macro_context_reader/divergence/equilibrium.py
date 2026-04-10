"""
EUR/USD Equilibrium & Misalignment Layer — PRD-300 / REQ-9, REQ-10, REQ-11

Referință: Martínez, Neut, Ramírez (2025), "Equilibrium of the EUR/USD Exchange
Rate: A Long-Term Perspective", BBVA Research, March 2025.
https://www.bbvaresearch.com/wp-content/uploads/2025/03/Equilibrium-of-the-EUR-USD-exchange-rate-A-long-term-perspective.pdf

CONTRIBUȚII CHEIE ALE PAPER-ULUI:

1. DESCOMPUNERE EUR/USD (REQ-10):
   Nu tratăm EUR/USD ca un scalar unic. Îl descompunem în:
     usd_strength_component ← Fed policy + GFCI
     eur_weakness_component ← pierdere statut rezervă globală
   Implicație: dacă USD e supraapreciat din cauza GFCI subdued,
   corecția vine când GFCI se normalizează — mai rapidă și mai predictibilă.
   Dacă EUR e slab structural, corecția e mai lentă și necesită catalizator BCE.

2. TREI SCENARII DE ECHILIBRU (REQ-9):
   Central scenario (1.20):
     Presupune normalizarea GFCI și a condițiilor financiare globale.
     Consistent cu modelele bazate pe diferențiale de productivitate US-EU.

   Subdued financial conditions (1.10):
     GFCI rămâne suprimat din cauza riscului geopolitic și fragmentării financiare.
     Fed restrictiv pe termen lung + China slowdown + EM outflows.

   Trade tensions escalate (1.05):
     Tensiuni comerciale suplimentare + GFCI suprimat.
     USD se apreciază suplimentar ca safe haven.

   NOTE: scenariile sunt forward-looking — calibrate pe evoluția GFCI și politica Fed.
   Nu sunt puncte fixe — se actualizează trimestrial cu noile date BBVA/FRED.

3. MISALIGNMENT INDICATOR (REQ-9):
   misalignment_pct = (eurusd_current - eurusd_equilibrium) / eurusd_equilibrium
   Semnal de trading:
     misalignment_pct < -0.08  → EUR structural ieftin → tailwind bullish EUR
     misalignment_pct > +0.08  → EUR structural scump → headwind bullish EUR
     |misalignment_pct| < 0.05 → la echilibru → semnal neutru

4. GFCI CA INDICATOR SUPLIMENTAR (REQ-11):
   GFCI (Global Financial Conditions Index) e factorul dominant al forței USD
   dincolo de politica Fed. Proxy gratuit: Chicago Fed NFCI (FRED: NFCI).
   NFCI negativ = condiții financiare laxe → USD mai slab structural
   NFCI pozitiv = condiții financiare strânse → USD mai puternic structural
   Integrare cu PRD-050/CC-2b: NFCI devine a 7-a variabilă în vectorul macro
   pentru analog_detector.py (Mulliner & Harvey metodologie).

INTEGRARE CU RESTUL SISTEMULUI:
  PRD-300 / decomposition.py: misalignment_pct intră ca semnal în deep_current
  PRD-050 / analog_detector.py: NFCI (GFCI proxy) adăugat în build_macro_vector()
  PRD-500 / bba_mappers: misalignment_pct ajustează BBA pentru Stratul 3

DO NOT implement until PRD-300 is Approved.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

EquilibriumScenario = Literal["central", "subdued_gfci", "trade_tensions"]

# Valorile de echilibru din BBVA Research (2025) — actualizate trimestrial
EQUILIBRIUM_RATES: dict[str, float] = {
    "central":         1.20,
    "subdued_gfci":    1.10,
    "trade_tensions":  1.05,
}

# GFCI proxy: Chicago Fed NFCI
# FRED ticker: NFCI (săptămânal, disponibil din 1971)
GFCI_PROXY_FRED_TICKER = "NFCI"


def get_current_equilibrium(
    scenario: EquilibriumScenario = "central",
) -> float:
    """
    Returnează rata de echilibru EUR/USD pentru scenariul dat.

    Args:
        scenario: "central" | "subdued_gfci" | "trade_tensions"
                  Selectat în funcție de regimul curent din PRD-050

    Returns:
        float — rata de echilibru EUR/USD (ex: 1.20)

    NOTE: valorile sunt din BBVA Research (2025) — actualizate trimestrial.
          La activarea PRD-300, verifică dacă BBVA a publicat update.
    TODO: PRD-300
    """
    raise NotImplementedError("TODO: PRD-300")


def compute_misalignment(
    eurusd_current: float,
    scenario: EquilibriumScenario = "central",
) -> dict[str, float]:
    """
    Calculează misalignment-ul EUR/USD față de echilibrul pe termen lung.

    Args:
        eurusd_current: rata EUR/USD curentă (ex: 1.085)
        scenario: scenariul de echilibru folosit

    Returns:
        {
          "eurusd_current": float,
          "eurusd_equilibrium": float,
          "misalignment_pct": float,    ← negativ = EUR ieftin, pozitiv = EUR scump
          "misalignment_signal": str,   ← "bullish_eur" | "bearish_eur" | "neutral"
          "scenario": str,
        }

    Logică semnal:
      misalignment_pct < -0.08  → "bullish_eur"  (EUR structural ieftin)
      misalignment_pct > +0.08  → "bearish_eur"  (EUR structural scump)
      |misalignment_pct| < 0.05 → "neutral"

    NOTE: pragurile ±0.08 și ±0.05 sunt prior-uri — calibrate empiric.
    TODO: PRD-300
    """
    raise NotImplementedError("TODO: PRD-300")


def decompose_eurusd_movement(
    eurusd_series: pd.Series,
    dxy_series: pd.Series,
    eur_basket_series: pd.Series,
) -> pd.DataFrame:
    """
    Descompune mișcările EUR/USD în componente USD și EUR (BBVA metodologie).

    Logică:
      DXY (USD Index) capturează forța USD față de coș de valute
      EUR basket (EUR față de non-USD valute) capturează forța/slăbiciunea EUR
      Dacă EUR/USD scade și DXY crește → USD strength dominant
      Dacă EUR/USD scade și DXY stabil → EUR weakness dominant

    Args:
        eurusd_series: EUR/USD zilnic (FRED: DEXUSEU)
        dxy_series: USD Index (FRED: DTWEXBGS)
        eur_basket_series: EUR față de coș non-USD (calculat din ECB data)

    Returns:
        pd.DataFrame cu coloane:
        {
          "date": DatetimeIndex,
          "eurusd_move": float,         ← mișcarea totală
          "usd_strength_contrib": float, ← contribuția forței USD
          "eur_weakness_contrib": float, ← contribuția slăbiciunii EUR
          "dominant_driver": str,        ← "usd_strength" | "eur_weakness" | "mixed"
        }

    NOTE: dominant_driver influențează viteza așteptată a corecției spre echilibru:
          usd_strength → corecție mai rapidă (GFCI dependent)
          eur_weakness → corecție mai lentă (structurală)
    TODO: PRD-300
    """
    raise NotImplementedError("TODO: PRD-300")


def fetch_gfci_proxy(
    fred_api_key: str,
    start_date: str = "2000-01-01",
) -> pd.Series:
    """
    Descarcă NFCI (National Financial Conditions Index) de la FRED ca proxy GFCI.

    FRED ticker: NFCI (săptămânal, Chicago Fed)
    Interpretare:
      NFCI < 0  → condiții financiare laxe → USD mai slab structural
      NFCI > 0  → condiții financiare strânse → USD mai puternic structural
      NFCI > +1 → stress financiar semnificativ

    NOTE: NFCI e un proxy pentru GFCI. GFCI-ul oficial Goldman Sachs nu e gratuit.
          NFCI Chicago Fed e public, gratuit, săptămânal din 1971.
          Corelație istorică NFCI ↔ GFCI: >0.85 pe date 2000-2024.

    Returns:
        pd.Series cu index DatetimeIndex și valori NFCI
    TODO: PRD-300
    """
    raise NotImplementedError("TODO: PRD-300")


def compute_equilibrium_scenario_from_regime(
    macro_regime: str,
    nfci_current: float,
) -> EquilibriumScenario:
    """
    Selectează scenariul de echilibru relevant bazat pe regimul macro curent
    și nivelul NFCI.

    Logică:
      FINANCIAL_STABILITY (PRD-050) OR nfci_current > 0.5
        → "trade_tensions" (cel mai conservator)
      INFLATION OR GROWTH AND nfci_current > 0.0
        → "subdued_gfci"
      GROWTH AND nfci_current < 0.0
        → "central" (condiții financiare laxe → echilibru la 1.20)

    Args:
        macro_regime: output din PRD-050 get_current_regime()
        nfci_current: valoarea curentă NFCI din fetch_gfci_proxy()

    Returns:
        EquilibriumScenario — scenariul selectat automat
    TODO: PRD-300
    """
    raise NotImplementedError("TODO: PRD-300")


def get_equilibrium_signal(
    fred_api_key: str,
    macro_regime: str | None = None,
) -> dict:
    """
    Entry point principal — produce semnalul complet de misalignment și echilibru.

    Pipeline:
      1. fetch_gfci_proxy() → NFCI curent
      2. compute_equilibrium_scenario_from_regime() → scenariu relevant
      3. get_current_equilibrium() → rata de echilibru
      4. compute_misalignment() → misalignment_pct și semnal
      5. fetch eurusd current din FRED (DEXUSEU)

    Returns:
        {
          "misalignment_pct": float,
          "misalignment_signal": str,   ← "bullish_eur"|"bearish_eur"|"neutral"
          "eurusd_current": float,
          "eurusd_equilibrium": float,
          "active_scenario": str,
          "nfci_current": float,
          "nfci_regime": str,           ← "loose"|"neutral"|"tight"|"stress"
          "dominant_driver": str,       ← "usd_strength"|"eur_weakness"|"mixed"
          "as_of_date": str,
        }

    Consumat de PRD-300 composite_divergence_score și PRD-051 Regime Monitor.
    TODO: PRD-300
    """
    raise NotImplementedError("TODO: PRD-300")
