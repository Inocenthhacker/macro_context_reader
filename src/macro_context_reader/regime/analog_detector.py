"""
Historical Analog Regime Detector — PRD-050 / CC-2b (Status: Placeholder)

Metodă alternativă de clasificare a regimului macro, data-driven,
inspirată din Mulliner, Harvey, Xia & Fang (2025), "Regimes", SSRN 5164863.

Principiu: În loc de reguli fixe (CPI > 3.0 → INFLATION), identificăm
momentele istorice cele mai similare cu prezentul pe un vector de
indicatori macro, și derivăm regimul din distribuția regimurilor analogilor.

Metodologie:
  1. Construiești vectorul macro curent:
     v_t = [yield_curve_slope, CPI_yoy, HY_credit_spread,
            stock_bond_correlation, oil_price, copper_price]

  2. Calculezi distanța față de fiecare lună din istoric (1980–prezent):
     d(t, τ) = distanță(v_t, v_τ)

  3. Sortezi după distanță, iei top-K analogi (ex: K=10)

  4. Regimul curent = distribuție de probabilitate peste regimurile analogilor:
     {"inflation": 0.4, "growth": 0.35, "financial_stability": 0.25}
     Nu mai e un label binar — e o distribuție.

  5. "Anti-regimuri" = momentele cele mai diferite de prezent (distanță maximă)
     → ce NU se va întâmpla probabil (putere predictivă negativă)

DISTANȚĂ — două metode, comparate empiric:

  A) Distanța Mahalanobis cu sample covariance (DEFAULT pentru vectorul nostru):
     d_M = √[(v_t - v_τ)ᵀ · Σ⁻¹ · (v_t - v_τ)]
     Avantaj: ține cont de scale diferite și corelații dintre variabile
     Când: 6 variabile × 540 obs → raport 90 → sample covariance stabil

  B) Distanța Mahalanobis cu Ledoit-Wolf estimator (REZERVAT pentru extinderi):
     Când: vectorul crește la 20+ variabile → sample covariance devine instabil
     Ledoit-Wolf regularizează matricea de covarianță
     from sklearn.covariance import LedoitWolf

  NOTĂ: Distanța Euclidiană simplă NU e folosită — biased de scale diferite.
  Chiar și standardizată (z-score), ignoră corelațiile dintre variabile.
  Mahalanobis rezolvă ambele probleme simultan.

INTEGRARE CU PRD-050 (classifier.py):
  Cele două metode de clasificare rulează în paralel:
    A) Rule-based (classifier.py): reguli fixe pe thresholds YAML
    B) Analog-based (analog_detector.py): distanță Mahalanobis pe istoricul macro
  Metoda cu performance mai bun pe USMPD backtesting devine default.

SURSE DATE (toate FRED, gratuite, ~45 ani de date lunare = ~540 observații):
  T10Y2Y      → yield curve slope (10Y - 2Y)
  CPIAUCSL    → CPI YoY
  BAMLH0A0HYM2 → HY credit spread (bps)
  SP500 + DGS10 → stock-bond correlation (calculat rolling 12M)
  DCOILWTICO  → oil price
  PCOPPUSDM   → copper price

Referință: Mulliner, Harvey, Xia, Fang (2025) — "Regimes", SSRN 5164863
Referință distanță: Chiapparoli (2025) — "Macroeconomic Factor Timing", SSRN 5287108
DO NOT implement until PRD-050 is Approved and CC-1, CC-2 are Done.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

DistanceMethod = Literal["mahalanobis_sample", "mahalanobis_ledoitwolf"]
# NOTE: Euclidean exclus — biased de scale diferite și ignoră corelații


def build_macro_vector(
    fred_api_key: str,
    as_of_date: str | None = None,
) -> pd.Series:
    """
    Construiește vectorul macro curent pentru luna dată.

    Returns:
        pd.Series cu index = nume variabile, valori = valori macro normalizate
        {
          "yield_curve_slope": float,   # T10Y2Y, %
          "cpi_yoy": float,             # CPIAUCSL YoY %
          "hy_credit_spread": float,    # BAMLH0A0HYM2, bps
          "stock_bond_corr": float,     # rolling 12M, ∈ [-1, +1]
          "oil_price": float,           # DCOILWTICO, USD
          "copper_price": float,        # PCOPPUSDM, USD/lb
        }

    NOTE: valorile brute — normalizarea se face în compute_distances()
          prin matricea de covarianță, nu manual.
    TODO: PRD-050 / CC-2b
    """
    raise NotImplementedError("TODO: PRD-050 / CC-2b")


def build_historical_matrix(
    fred_api_key: str,
    start_year: int = 1980,
    end_date: str | None = None,
) -> pd.DataFrame:
    """
    Construiește matricea istorică — câte un vector macro per lună.

    Returns:
        pd.DataFrame shape (n_months, 6)
        Index: DatetimeIndex (lunar)
        Columns: aceleași 6 variabile ca build_macro_vector()

    ~45 ani × 12 luni = ~540 observații
    Raport obs/variabile = 540/6 = 90 → sample covariance stabil.

    NOTE: point-in-time — fiecare lună conține doar date disponibile
          la acea dată (nu revizii ulterioare). Critică pentru backtesting.
    TODO: PRD-050 / CC-2b
    """
    raise NotImplementedError("TODO: PRD-050 / CC-2b")


def compute_distances(
    v_current: pd.Series,
    historical_matrix: pd.DataFrame,
    method: DistanceMethod = "mahalanobis_sample",
) -> pd.Series:
    """
    Calculează distanța dintre vectorul curent și fiecare lună istorică.

    Metoda A — mahalanobis_sample (DEFAULT):
      cov = np.cov(historical_matrix.T)  ← sample covariance
      cov_inv = np.linalg.inv(cov)
      d = mahalanobis(v_current, v_tau, cov_inv) pentru fiecare τ

    Metoda B — mahalanobis_ledoitwolf (REZERVAT pentru 20+ variabile):
      from sklearn.covariance import LedoitWolf
      lw = LedoitWolf().fit(historical_matrix)
      cov_inv = lw.precision_
      d = mahalanobis(v_current, v_tau, cov_inv) pentru fiecare τ

    Returns:
        pd.Series cu index = date istorice, valori = distanțe
        Sortată ascending (distanță mică = analog apropiat)

    TODO: PRD-050 / CC-2b
    """
    raise NotImplementedError("TODO: PRD-050 / CC-2b")


def find_analogs(
    distances: pd.Series,
    top_k: int = 10,
) -> pd.DataFrame:
    """
    Identifică top-K analogi istorici (distanță minimă) și
    top-K anti-regimuri (distanță maximă).

    Returns:
        pd.DataFrame cu coloane:
        {
          "date": DatetimeIndex,
          "distance": float,
          "type": "analog" | "anti_regime",
          "rank": int,
        }

    Anti-regimurile = momentele cele mai diferite de prezent.
    Putere predictivă: ce s-a întâmplat în anti-regimuri
    e probabil ce NU se va întâmpla acum.
    Referință: Mulliner & Harvey (2025) — anti-regimuri au
    putere predictivă negativă demonstrată empiric.

    TODO: PRD-050 / CC-2b
    """
    raise NotImplementedError("TODO: PRD-050 / CC-2b")


def compute_regime_distribution(
    analogs: pd.DataFrame,
    regime_history: pd.DataFrame,
) -> dict[str, float]:
    """
    Derivă distribuția de probabilitate a regimului curent
    din regimurile analogilor istorici.

    Args:
        analogs: output din find_analogs() — top-K analogi
        regime_history: seria temporală de regimuri din PRD-050
                        (output din classifier.py per dată istorică)

    Returns:
        distribuție normalizată, sumă = 1.0:
        {
          "inflation": 0.40,
          "growth": 0.35,
          "financial_stability": 0.25,
        }

    Ponderare: analogii mai apropiați (distanță mai mică) primesc
    greutate mai mare în distribuție (inverse distance weighting).

    NOTE: acesta e output-ul critic care diferențiază metoda analog
    de metoda rule-based — nu un label binar ci o distribuție.
    TODO: PRD-050 / CC-2b
    """
    raise NotImplementedError("TODO: PRD-050 / CC-2b")


def detect_regime_analog(
    fred_api_key: str,
    method: DistanceMethod = "mahalanobis_sample",
    top_k: int = 10,
    start_year: int = 1980,
) -> dict:
    """
    Entry point principal — rulează întregul pipeline analog detection.

    Returns:
        {
          "regime_distribution": dict[str, float],  ← distribuție, nu label
          "top_analogs": pd.DataFrame,               ← top-K momente similare
          "anti_regimes": pd.DataFrame,              ← top-K momente diferite
          "dominant_regime": str,                    ← regimul cu prob maximă
          "dominant_confidence": float,              ← probabilitatea maximă
          "method": str,
          "as_of_date": str,
        }

    Consumat de PRD-050 classifier.py alături de rule-based output.
    Consumat de PRD-051 Regime Monitor pentru vizualizare analogi istorici.
    TODO: PRD-050 / CC-2b
    """
    raise NotImplementedError("TODO: PRD-050 / CC-2b")
